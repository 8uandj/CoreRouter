"""
gnn_policy.py — Deep Graph Reinforcement Learning (DGRL)
Triển khai Graph Attention Network (GAT) làm Policy Backbone cho PPO.

Kiến trúc:
  Input: Node Feature Matrix (num_nodes x node_feat_dim) + Adjacency Matrix
      → 2 x GAT Layer (Attention-weighted message passing)
      → Flatten + Linear → pi (actor) & vf (critic)

Ưu điểm so với MLP thuần:
  - "Hiểu" cấu trúc đồ thị mạng: Node gần nhau có attention weight cao hơn.
  - Có khả năng generalize sang topologies khác nhau.
  - Tự học được "trọng tâm" của đồ thị theo từng bước thời gian.
"""

import torch
import torch.nn as nn
import torch.nn.functional as F
import numpy as np
from typing import Callable, Dict, List, Optional, Tuple, Type, Union

from stable_baselines3.common.policies import ActorCriticPolicy
from stable_baselines3.common.torch_layers import BaseFeaturesExtractor
from gymnasium import spaces


# ═══════════════════════════════════════════════════════════════
#  1. Graph Attention Network (GAT) Layer
# ═══════════════════════════════════════════════════════════════
class GATLayer(nn.Module):
    """
    Multi-head Graph Attention Layer.
    Tính attention weight giữa các cặp node dựa trên đặc trưng của chúng,
    sau đó tổng hợp (aggregate) thông tin từ các node lân cận.
    """
    def __init__(self, in_features: int, out_features: int, num_heads: int = 4,
                 dropout: float = 0.0, concat: bool = True):
        super(GATLayer, self).__init__()
        self.in_features  = in_features
        self.out_features = out_features
        self.num_heads    = num_heads
        self.concat       = concat
        self.dropout      = nn.Dropout(dropout)

        # Learnable weights
        self.W = nn.Linear(in_features, out_features * num_heads, bias=False)
        self.a = nn.Parameter(torch.empty(num_heads, 2 * out_features))
        nn.init.xavier_uniform_(self.a)

    def forward(self, h: torch.Tensor, adj: torch.Tensor) -> torch.Tensor:
        """
        h   : (batch, N, in_features)  — Node features
        adj : (batch, N, N) or (N, N)   — Adjacency matrix (normalized)
        Returns: (batch, N, out_features*num_heads) if concat else (batch, N, out_features)
        """
        batch = h.size(0)
        N     = h.size(1)

        # Linear projection: (B, N, out*H)
        Wh = self.W(h).view(batch, N, self.num_heads, self.out_features)
        # → (B, N, H, F)

        # Attention scores dùng broadcasting
        # (B, N, 1, H, F) vs (B, 1, N, H, F) → (B, N, N, H, 2F)
        Whi = Wh.unsqueeze(2).expand(-1, -1, N, -1, -1)  # (B,N,N,H,F)
        Whj = Wh.unsqueeze(1).expand(-1, N, -1, -1, -1)  # (B,N,N,H,F)
        pair = torch.cat([Whi, Whj], dim=-1)              # (B,N,N,H,2F)

        # a : (H, 2F) → (1,1,1,H,2F)
        a_vec = self.a.unsqueeze(0).unsqueeze(0).unsqueeze(0)
        e = F.leaky_relu((pair * a_vec).sum(dim=-1), negative_slope=0.2)  # (B,N,N,H)
        e = e.permute(0, 3, 1, 2)  # (B,H,N,N)

        # Mask với adjacency (chỉ attend các node kết nối)
        if adj.dim() == 2:
            adj = adj.unsqueeze(0).unsqueeze(0)  # (1,1,N,N)
        else:
            adj = adj.unsqueeze(1)               # (B,1,N,N)

        INF = -1e9
        e = e + (1.0 - adj.clamp(0, 1)) * INF   # Mask disconnected

        alpha = F.softmax(e, dim=-1)             # (B,H,N,N)
        alpha = self.dropout(alpha)

        # Aggregation: h' = alpha @ Wh
        # Wh: (B,N,H,F) → (B,H,N,F)
        Wh_p = Wh.permute(0, 2, 1, 3)           # (B,H,N,F)
        out = torch.matmul(alpha, Wh_p)          # (B,H,N,F)
        out = out.permute(0, 2, 1, 3)            # (B,N,H,F)

        if self.concat:
            out = out.contiguous().view(batch, N, -1)  # (B,N,H*F)
        else:
            out = out.mean(dim=2)                      # (B,N,F)

        return F.elu(out)


# ═══════════════════════════════════════════════════════════════
#  2. GNN Feature Extractor (tích hợp vào SB3)
# ═══════════════════════════════════════════════════════════════
class GNNFeaturesExtractor(BaseFeaturesExtractor):
    """
    Trích xuất đặc trưng từ observation bằng 2 lớp GAT.

    Observation shape: (23,)  = 5 nodes × 3 features + 3 request + 5 traffic_class
        node_features : (5, 3) — [cpu_used_norm, ram_used_norm, msd_used_norm]
        request_feat  : (3,)   — [cpu_req, ram_req, msd_req]
        traffic_class : (5,)   — One-hot

    Adjacency matrix được tính từ LATENCY_MATRIX (cạnh tồn tại khi latency < ngưỡng).
    """
    # Latency matrix từ env (ms)
    LATENCY_MATRIX = torch.tensor([
        [ 0,   2,   5,   8, 200],
        [ 2,   0,   2,   5, 198],
        [ 5,   2,   0,   2, 195],
        [ 8,   5,   2,   0, 192],
        [200, 198, 195, 192,   0],
    ], dtype=torch.float32)

    # Chỉ connect nodes có latency < 20ms (nội bộ DC)
    LATENCY_THRESHOLD = 20.0

    def __init__(self, observation_space: spaces.Box,
                 num_nodes: int = 5,
                 node_feat_dim: int = 3,   # cpu, ram, msd per node
                 gat_hidden: int = 64,
                 gat_heads: int = 4,
                 num_gat_layers: int = 2,
                 features_dim: int = 256):
        super().__init__(observation_space, features_dim=features_dim)

        self.num_nodes    = num_nodes
        self.node_feat_d  = node_feat_dim
        self.req_feat_d   = 3   # cpu_req, ram_req, msd_req
        self.traffic_d    = 5   # one-hot traffic class

        # Adjacency matrix (không thay đổi trong training)
        adj_raw = (self.LATENCY_MATRIX < self.LATENCY_THRESHOLD).float()
        # Thêm self-loop
        adj_raw = adj_raw + torch.eye(num_nodes)
        # Normalize D^{-1/2} A D^{-1/2}
        deg = adj_raw.sum(dim=1, keepdim=True).sqrt().clamp(min=1e-9)
        self.register_buffer('adj', adj_raw / (deg * deg.T))

        # GAT layers: node_feat_dim → gat_hidden*heads → gat_hidden
        self.gat_layers = nn.ModuleList()
        in_d = node_feat_dim
        for i in range(num_gat_layers):
            if i < num_gat_layers - 1:
                self.gat_layers.append(GATLayer(in_d, gat_hidden, num_heads=gat_heads, concat=True))
                in_d = gat_hidden * gat_heads
            else:
                # Final layer: mean-aggregate để giảm chiều
                self.gat_layers.append(GATLayer(in_d, gat_hidden, num_heads=gat_heads, concat=False))
                in_d = gat_hidden

        # Graph embedding sau khi flatten: num_nodes * gat_hidden
        graph_embed_dim = num_nodes * in_d

        # Request + traffic class feature
        req_embed_dim = 16
        self.req_encoder = nn.Sequential(
            nn.Linear(self.req_feat_d + self.traffic_d, req_embed_dim),
            nn.ReLU()
        )

        # Final fusion MLP → features_dim
        self.fusion = nn.Sequential(
            nn.Linear(graph_embed_dim + req_embed_dim, 512),
            nn.ReLU(),
            nn.Linear(512, features_dim),
            nn.ReLU()
        )

    def forward(self, observations: torch.Tensor) -> torch.Tensor:
        """
        observations: (batch, 23)
        """
        B = observations.size(0)

        # Tách node features: index 0..14 (5 nodes × 3 feats)
        node_part = observations[:, :self.num_nodes * self.node_feat_d]  # (B, 15)
        node_feat = node_part.view(B, self.num_nodes, self.node_feat_d)  # (B, 5, 3)

        # Request + traffic class: index 15..22
        req_part  = observations[:, self.num_nodes * self.node_feat_d:]  # (B, 8)

        # GAT forward pass
        adj = self.adj.unsqueeze(0).expand(B, -1, -1)  # (B, 5, 5)
        h = node_feat
        for gat in self.gat_layers:
            h = gat(h, adj)  # (B, 5, hidden)

        # Flatten graph output: (B, 5*hidden)
        graph_embed = h.contiguous().view(B, -1)

        # Encode request
        req_embed = self.req_encoder(req_part)  # (B, 16)

        # Fusion
        fused = torch.cat([graph_embed, req_embed], dim=-1)
        return self.fusion(fused)  # (B, features_dim)


# ═══════════════════════════════════════════════════════════════
#  3. GNN Actor-Critic Policy cho SB3
# ═══════════════════════════════════════════════════════════════
class GNNActorCriticPolicy(ActorCriticPolicy):
    """
    PPO Policy sử dụng GNN Feature Extractor thay vì MLP thuần.
    Tương thích hoàn toàn với stable_baselines3 PPO.
    """
    def __init__(self, observation_space, action_space, lr_schedule,
                 num_nodes: int = 5,
                 gat_hidden: int = 64,
                 gat_heads: int = 4,
                 features_dim: int = 256,
                 **kwargs):
        # Loại bỏ net_arch nếu được truyền vào (GNN tự xử lý)
        kwargs.pop('net_arch', None)

        self._gnn_num_nodes  = num_nodes
        self._gnn_gat_hidden = gat_hidden
        self._gnn_gat_heads  = gat_heads
        self._gnn_feat_dim   = features_dim

        super().__init__(
            observation_space,
            action_space,
            lr_schedule,
            features_extractor_class=GNNFeaturesExtractor,
            features_extractor_kwargs=dict(
                num_nodes=num_nodes,
                gat_hidden=gat_hidden,
                gat_heads=gat_heads,
                features_dim=features_dim,
            ),
            net_arch=dict(pi=[256, 128], vf=[256, 128]),
            **kwargs
        )
