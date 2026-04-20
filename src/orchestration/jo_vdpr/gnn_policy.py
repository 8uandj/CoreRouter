"""
gnn_policy.py — Deep Graph Reinforcement Learning (DGRL) v3 (Phase 7)

Sửa lỗi nghiêm trọng của Phase 6:
    - [BUG FIX] Ma trận kề (Adjacency) trả về dạng tĩnh thuần túy (chỉ cáp quang vật lý).
      Phase 6 đã động hoá A theo MSD residual, phá hủy tính ổn định phổ đồ thị và khiến
      Critic không hội tụ (explained_variance ≈ 0 sau 290K steps).
    - [PRINCIPLE] Adjacency mô tả CẤU TRÚC, Node Features mô tả TRẠNG THÁI.
      GAT sẽ tự học attention weights từ msd_free_ratio (dim 3 của node feat) —
      không cần bóp méo cấu trúc đồ thị để "gợi ý" cho Agent.

Kiến trúc v3:
    Input (B, 10, 4) + adj_static (10, 10)
      → GAT Layer 1 [concat, 4 heads, 64 dim]
      → Dropout(0.1) + LayerNorm          ← ổn định gradient
      → GAT Layer 2 [mean-pool, 4 heads, 64 dim]
      + Residual skip (Linear in_d → 64)
      → Flatten (B, 10*64)
      + Request Encoder (MLP 8→32→16)
      → Fusion MLP (640+16 → 512 → 256)  ← features_dim
"""

import torch
import torch.nn as nn
import torch.nn.functional as F

from sb3_contrib.common.maskable.policies import MaskableActorCriticPolicy
from stable_baselines3.common.torch_layers import BaseFeaturesExtractor
from gymnasium import spaces

from src.orchestration.jo_vdpr.topology import (
    LATENCY_MATRIX, NUM_NODES, get_adjacency_matrix
)


# ═══════════════════════════════════════════════════════════════
#  1. GAT Layer — không thay đổi logic, cải tiến masking
# ═══════════════════════════════════════════════════════════════
class GATLayer(nn.Module):
    """
    Multi-head Graph Attention Layer với soft masking.

    Args:
        in_features  : chiều đầu vào mỗi node
        out_features : chiều đầu ra mỗi head
        num_heads    : số heads
        concat       : True → concat heads (B,N,H*F); False → mean (B,N,F)
        dropout      : dropout trên attention weights

    I/O:
        h   : (B, N, in_features)
        adj : (B, N, N) hoặc (N, N) — trọng số [0,1], tĩnh hoặc bất kỳ
        → (B, N, out_features*H hoặc out_features)
    """
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

        Wh   = self.W(h).view(B, N, self.num_heads, self.out_features)       # (B,N,H,F)
        Whi  = Wh.unsqueeze(2).expand(-1, -1, N, -1, -1)                     # (B,N,N,H,F)
        Whj  = Wh.unsqueeze(1).expand(-1, N, -1, -1, -1)                     # (B,N,N,H,F)
        pair = torch.cat([Whi, Whj], dim=-1)                                  # (B,N,N,H,2F)

        a4   = self.a.unsqueeze(0).unsqueeze(0).unsqueeze(0)                  # (1,1,1,H,2F)
        e    = F.leaky_relu((pair * a4).sum(-1), 0.2).permute(0, 3, 1, 2)    # (B,H,N,N)

        # ── Soft masking: cạnh không kết nối → -∞ ──────────────────
        if adj.dim() == 2:
            adj = adj.unsqueeze(0).unsqueeze(0)   # (1,1,N,N)
        elif adj.dim() == 3:
            adj = adj.unsqueeze(1)                # (B,1,N,N)
        adj_c = adj.clamp(0.0, 1.0)
        e     = e + (adj_c - 1.0) * 1e9           # mask disconnected edges

        alpha = self.attn_drop(F.softmax(e, dim=-1))                          # (B,H,N,N)
        out   = torch.matmul(alpha, Wh.permute(0, 2, 1, 3))                  # (B,H,N,F)
        out   = out.permute(0, 2, 1, 3)                                       # (B,N,H,F)

        if self.concat:
            return F.elu(out.contiguous().view(B, N, -1))   # (B,N,H*F)
        return F.elu(out.mean(2))                            # (B,N,F)


# ═══════════════════════════════════════════════════════════════
#  2. GNN Feature Extractor v3 — Static Adjacency
# ═══════════════════════════════════════════════════════════════
class GNNFeaturesExtractor(BaseFeaturesExtractor):
    """
    Phase 7 Feature Extractor.

    Observation layout (48 dims, 10 nodes x 4 feats + 8 request):
        [0..39]  : node features × 10
                   [cpu_norm, ram_norm, msd_used_norm, msd_free_norm]
        [40..42] : request (cpu_req, ram_req, msd_req)
        [43..47] : traffic class one-hot

    Nguyên tắc thiết kế:
        adj (tĩnh) = cáp quang vật lý (Geodesic threshold)
        msd_free   = Node Feature dim 3 → GAT tự học attention weight
                     → Agent tự né node full-MSD qua gradient,
                       KHÔNG thông qua bóp méo adjacency.
    """
    NODE_FEAT_DIM = 4
    REQ_DIM       = 3
    TRAFFIC_DIM   = 5

    def __init__(self, observation_space: spaces.Box,
                 num_nodes:    int = NUM_NODES,
                 gat_hidden:   int = 64,
                 gat_heads:    int = 4,
                 features_dim: int = 256):
        super().__init__(observation_space, features_dim=features_dim)
        self.num_nodes  = num_nodes
        self.gat_hidden = gat_hidden

        # ── Static Adjacency (chỉ thay đổi khi cáp quang đứt) ──────
        adj_np   = get_adjacency_matrix(threshold_ms=15.0)[:num_nodes, :num_nodes]
        adj_t    = torch.tensor(adj_np, dtype=torch.float32)
        # D^{-1/2} A D^{-1/2} normalisation
        deg      = adj_t.sum(1, keepdim=True).clamp(min=1e-9).sqrt()
        adj_norm = adj_t / (deg * deg.T)
        self.register_buffer('adj', adj_norm)          # (N, N), không trainable

        # ── GAT stack ───────────────────────────────────────────────
        # Layer 1: concat → (B, N, H*F)
        self.gat1     = GATLayer(self.NODE_FEAT_DIM, gat_hidden,
                                 num_heads=gat_heads, concat=True,  dropout=0.1)
        mid_d         = gat_hidden * gat_heads         # 256
        # LayerNorm sau layer 1 để ổn định training sâu
        self.ln1      = nn.LayerNorm(mid_d)

        # Layer 2: mean-pool → (B, N, F)
        self.gat2     = GATLayer(mid_d, gat_hidden,
                                 num_heads=gat_heads, concat=False, dropout=0.0)

        # Residual projection input → gat_hidden
        self.skip     = nn.Linear(self.NODE_FEAT_DIM, gat_hidden, bias=False)

        # ── Request encoder ─────────────────────────────────────────
        self.req_enc  = nn.Sequential(
            nn.Linear(self.REQ_DIM + self.TRAFFIC_DIM, 32),
            nn.ReLU(),
            nn.Linear(32, 16),
            nn.ReLU()
        )

        # ── Fusion MLP ──────────────────────────────────────────────
        graph_dim     = num_nodes * gat_hidden          # 10 * 64 = 640
        self.fusion   = nn.Sequential(
            nn.Linear(graph_dim + 16, 512),
            nn.LayerNorm(512),
            nn.ReLU(),
            nn.Dropout(0.05),
            nn.Linear(512, features_dim),
            nn.ReLU()
        )

    def forward(self, obs: torch.Tensor) -> torch.Tensor:
        B = obs.size(0)
        N = self.num_nodes

        # Tách features
        node_feat = obs[:, :N * self.NODE_FEAT_DIM].view(B, N, self.NODE_FEAT_DIM)
        req_part  = obs[:, N * self.NODE_FEAT_DIM:]               # (B, 8)

        # Static adj broadcast
        adj = self.adj.unsqueeze(0).expand(B, -1, -1)             # (B, N, N)

        # GAT forward
        h1  = self.ln1(self.gat1(node_feat, adj))                 # (B, N, H*F)
        h2  = self.gat2(h1, adj)                                   # (B, N, F)

        # Residual: project input → gat_hidden, add
        h_out = h2 + self.skip(node_feat)                          # (B, N, gat_hidden)

        graph_embed = h_out.contiguous().view(B, -1)               # (B, N*gat_hidden)
        req_embed   = self.req_enc(req_part)                       # (B, 16)

        return self.fusion(torch.cat([graph_embed, req_embed], -1))


# ═══════════════════════════════════════════════════════════════
#  3. GNN Actor-Critic Policy
# ═══════════════════════════════════════════════════════════════
class GNNActorCriticPolicy(MaskableActorCriticPolicy):
    """PPO Policy v3 — Static-Adj GAT, LayerNorm, Dropout."""
    def __init__(self, observation_space, action_space, lr_schedule,
                 num_nodes:    int = NUM_NODES,
                 gat_hidden:   int = 64,
                 gat_heads:    int = 4,
                 features_dim: int = 256,
                 **kwargs):
        kwargs.pop('net_arch', None)
        super().__init__(
            observation_space, action_space, lr_schedule,
            features_extractor_class=GNNFeaturesExtractor,
            features_extractor_kwargs=dict(
                num_nodes=num_nodes, gat_hidden=gat_hidden,
                gat_heads=gat_heads, features_dim=features_dim,
            ),
            net_arch=dict(pi=[256, 128], vf=[256, 128]),
            **kwargs
        )
