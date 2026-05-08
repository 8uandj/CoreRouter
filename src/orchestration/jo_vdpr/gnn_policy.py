"""
gnn_policy.py — Deep Graph Reinforcement Learning (DGRL) v10 (Phase 10)

Nâng cấp so với v9:
    [NEW] Node Feature Dimension = 6 (Chứa Alert Flag & Geo Latency).
    [NEW] Dynamic Adjacency passing: Chấp nhận adj_matrix từ bên ngoài để tương thích tốt với Multi-Topology (vietnam, nsfnet, geant2).
"""

import torch
import torch.nn as nn
import torch.nn.functional as F
import numpy as np

from sb3_contrib.common.maskable.policies import MaskableActorCriticPolicy
from stable_baselines3.common.torch_layers import BaseFeaturesExtractor
from gymnasium import spaces

class GATLayer(nn.Module):
    def __init__(self, in_features: int, out_features: int,
                 num_heads: int = 4, concat: bool = True,
                 dropout: float = 0.1):
        super().__init__()
        self.out_features = out_features
        self.num_heads    = num_heads
        self.concat       = concat
        self.attn_drop    = nn.Dropout(dropout)

        self.W = nn.Linear(in_features, out_features * num_heads, bias=False)
        self.a = nn.Parameter(torch.empty(num_heads, 2 * out_features))
        nn.init.xavier_uniform_(self.a.unsqueeze(0))

    def forward(self, h: torch.Tensor, adj: torch.Tensor) -> torch.Tensor:
        B, N, _ = h.shape

        Wh   = self.W(h).view(B, N, self.num_heads, self.out_features)
        Whi  = Wh.unsqueeze(2).expand(-1, -1, N, -1, -1)
        Whj  = Wh.unsqueeze(1).expand(-1, N, -1, -1, -1)
        pair = torch.cat([Whi, Whj], dim=-1)

        a4   = self.a.unsqueeze(0).unsqueeze(0).unsqueeze(0)
        e    = F.leaky_relu((pair * a4).sum(-1), 0.2).permute(0, 3, 1, 2)

        if adj.dim() == 2:
            adj = adj.unsqueeze(0).unsqueeze(0)
        elif adj.dim() == 3:
            adj = adj.unsqueeze(1)
        adj_c = adj.clamp(0.0, 1.0)
        e     = e + (adj_c - 1.0) * 1e9

        alpha = self.attn_drop(F.softmax(e, dim=-1))
        out   = torch.matmul(alpha, Wh.permute(0, 2, 1, 3))
        out   = out.permute(0, 2, 1, 3)

        if self.concat:
            return F.elu(out.contiguous().view(B, N, -1))
        return F.elu(out.mean(2))


class GNNFeaturesExtractor(BaseFeaturesExtractor):
    """
    Phase 10 Feature Extractor — hỗ trợ observation động dựa trên Topology.
    NODE_FEAT_DIM = 6
    """
    NODE_FEAT_DIM  = 6
    REQ_DIM        = 3
    TRAFFIC_DIM    = 5
    GLOBAL_CTX_DIM = 5

    def __init__(self, observation_space: spaces.Box,
                 num_nodes:    int,
                 adj_matrix:   np.ndarray,
                 gat_hidden:   int = 64,
                 gat_heads:    int = 4,
                 features_dim: int = 256):
        super().__init__(observation_space, features_dim=features_dim)
        self.num_nodes  = num_nodes
        self.gat_hidden = gat_hidden

        adj_t    = torch.tensor(adj_matrix, dtype=torch.float32)
        deg      = adj_t.sum(1, keepdim=True).clamp(min=1e-9).sqrt()
        adj_norm = adj_t / (deg * deg.T)
        self.register_buffer('adj', adj_norm)

        self.gat1     = GATLayer(self.NODE_FEAT_DIM, gat_hidden,
                                 num_heads=gat_heads, concat=True,  dropout=0.1)
        mid_d         = gat_hidden * gat_heads
        self.ln1      = nn.LayerNorm(mid_d)

        self.gat2     = GATLayer(mid_d, gat_hidden,
                                 num_heads=gat_heads, concat=False, dropout=0.0)

        self.skip     = nn.Linear(self.NODE_FEAT_DIM, gat_hidden, bias=False)

        self.req_enc = nn.Sequential(
            nn.Linear(self.REQ_DIM + self.TRAFFIC_DIM, 32),
            nn.ReLU(),
            nn.Linear(32, 16),
            nn.ReLU()
        )

        self.global_enc = nn.Sequential(
            nn.Linear(self.GLOBAL_CTX_DIM, 16),
            nn.ReLU(),
            nn.Linear(16, 8),
            nn.ReLU()
        )

        graph_dim   = num_nodes * gat_hidden
        self.fusion = nn.Sequential(
            nn.Linear(graph_dim + 16 + 8, 512),
            nn.LayerNorm(512),
            nn.ReLU(),
            nn.Dropout(0.05),
            nn.Linear(512, features_dim),
            nn.ReLU()
        )

    def forward(self, obs: torch.Tensor) -> torch.Tensor:
        B = obs.size(0)
        N = self.num_nodes

        node_end   = N * self.NODE_FEAT_DIM
        req_end    = node_end + self.REQ_DIM + self.TRAFFIC_DIM
        node_feat  = obs[:, :node_end].view(B, N, self.NODE_FEAT_DIM)
        req_part   = obs[:, node_end:req_end]
        global_ctx = obs[:, req_end:]

        adj = self.adj.unsqueeze(0).expand(B, -1, -1)

        h1    = self.ln1(self.gat1(node_feat, adj))
        h2    = self.gat2(h1, adj)
        h_out = h2 + self.skip(node_feat)

        graph_embed  = h_out.contiguous().view(B, -1)
        req_embed    = self.req_enc(req_part)
        global_embed = self.global_enc(global_ctx)

        return self.fusion(torch.cat([graph_embed, req_embed, global_embed], -1))


class GNNActorCriticPolicy(MaskableActorCriticPolicy):
    """PPO Policy v10 — Dynamic-Topology GAT + Proactive Context."""
    def __init__(self, observation_space, action_space, lr_schedule,
                 num_nodes:    int,
                 adj_matrix:   np.ndarray,
                 gat_hidden:   int = 64,
                 gat_heads:    int = 4,
                 features_dim: int = 256,
                 **kwargs):
        kwargs.pop('net_arch', None)
        super().__init__(
            observation_space, action_space, lr_schedule,
            features_extractor_class=GNNFeaturesExtractor,
            features_extractor_kwargs=dict(
                num_nodes=num_nodes, 
                adj_matrix=adj_matrix,
                gat_hidden=gat_hidden,
                gat_heads=gat_heads, 
                features_dim=features_dim,
            ),
            net_arch=dict(pi=[256, 128], vf=[256, 128]),
            **kwargs
        )
