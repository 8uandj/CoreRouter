# Kế Hoạch Nâng Cấp JO-VDPR: Từ Thực Nghiệm Sơ Khai → Kết Quả Đỉnh Cao

## Phân Tích Chẩn Đoán Hiện Trạng

Sau khi đọc kỹ toàn bộ codebase và các biểu đồ thực nghiệm, tôi xác định **6 vấn đề cốt lõi** gây ra kết quả kém:

### 🔴 Vấn Đề 1: Dataset Quá Nhỏ và Thiếu Đa Dạng (NGUYÊN NHÂN CHÍNH)
- **Hiện tại**: 2,000 dòng tự sinh với phân phối cố định (70/20/10%)
- **Hậu quả**: Agent học trên 2,000 dòng nhưng bị lặp lại (modulo 2000) 50 lần trong 100,000 timesteps → **overfit cực nặng**, không generalize được. Learning curve bằng phẳng là bằng chứng rõ ràng.

### 🔴 Vấn Đề 2: Reward Function Sai Về Toán Học
- **Hiện tại**: `reward = 100 - (distance * 10)` với `distance = abs(node_v1 - node_v2)` 
- **Bug nghiêm trọng**: `distance` tính theo ID node (0-4), không phải khoảng cách topo thật. Node 0 và Node 4 có distance=4 nhưng trong topo thực tế có thể rất gần. Agent học sai heuristic.
- **MSD penalty -1000** quá cao so với reward thông thường ~60-100 → Agent bị collapse về hành vi đơn giản (chỉ chọn node 1 - Core).

### 🔴 Vấn Đề 3: Không Có DGRL - Thiếu Graph Awareness
- **Hiện tại**: `MlpPolicy` (mạng fully-connected thuần túy) - Agent nhìn state vector dẹt 15 phần tử
- **Kế hoạch gốc có DGRL** nhưng chưa implement. Graph Neural Network (GNN) cho phép agent hiểu **quan hệ kết nối giữa các node** - đây là lợi thế cạnh tranh cốt lõi của JO-VDPR so với Decoupled AI.

### 🔴 Vấn Đề 4: Episode Length Quá Ngắn (30 steps)
- **Hiện tại**: Episode kết thúc ở bước 30. Với 100,000 timesteps → ~3,333 episodes
- **Hậu quả**: Agent không có đủ thời gian để thấy hậu quả dài hạn của quyết định. Cần episode dài hơn (100-200 steps) để học chiến lược quản lý tài nguyên tốt.

### 🔴 Vấn Đề 5: State Space Thiếu Thông Tin Topo
- **Hiện tại**: State chỉ có `[CPU, RAM, MSD] * 5 nodes` = 15 features
- **Thiếu**: Băng thông link, độ trễ link, ma trận kết nối (adjacency), SFC request đang chờ xử lý
- **Hậu quả**: Agent "mù" về topology → không thể học được routing tối ưu

### 🟡 Vấn Đề 6: Cumulative Reward Âm Sâu (-366,070)
- JO-VDPR tệ hơn cả Decoupled AI về cumulative reward (-366k vs -274k)
- Lý do: MSD penalty -1000 làm tổng reward bị kéo xuống. Cần rebalance reward scale.

---

## Mục Tiêu Kết Quả Sau Khi Nâng Cấp

| Chỉ số | Hiện tại | Mục tiêu |
|--------|----------|-----------|
| Acceptance Ratio | 54.0% | **≥ 75%** (tiệm cận ILP 69.6% → vượt qua) |
| Cumulative Reward | -366,070 | **≥ -120,000** (tốt hơn ILP) |
| Learning Curve | Bằng phẳng (-18,000) | **Hội tụ rõ ràng**, tăng dần |
| Dataset | 2,000 dòng tự sinh | **≥ 10,000 dòng thực tế** |
| Model Architecture | PPO + MLP | **PPO + GNN (DGRL)** |

---

## User Review Required

> [!IMPORTANT]
> **Về Dataset "Bộ Quốc Phòng VN"**: Tôi hiểu bạn đề cập đến việc dùng dataset thực tế từ nguồn lớn. Tuy nhiên, dataset nội bộ của Bộ Quốc Phòng VN là **tài liệu mật - không thể truy cập công khai**. Kế hoạch này sẽ sử dụng các dataset lưu lượng mạng **công khai, thực tế** (CAIDA, MAWI, Zenodo Telecom) có quy mô lớn và đặc tính tương đương. Nếu bạn có file CSV/PCAP thực tế nào từ testbed nội bộ, tôi có thể tích hợp trực tiếp.

> [!WARNING]
> **Về thời gian train DGRL**: Mô hình GNN + PPO sẽ cần train **500,000 - 1,000,000 timesteps** (vs 100k hiện tại) để hội tụ. Ước tính ~2-4 giờ trên CPU hoặc ~30 phút nếu có GPU. Cần confirm phần cứng có đủ.

> [!CAUTION]
> **Không nên thay đổi toàn bộ cùng lúc**: Kế hoạch được chia theo thứ tự ưu tiên — vá reward function trước, sau đó đổi dataset, cuối cùng nâng cấp model. Mỗi bước đều có checkpoint có thể test độc lập.

---

## Proposed Changes

### Phase 1: Vá Thuật Toán Ngay (Quick Wins — 1-2 giờ)

**Mục tiêu**: Fix các bug làm sai kết quả, đây là bước quan trọng nhất, dễ làm nhất.

---

#### [MODIFY] [jo_vdpr_env.py](file:///home/hung8uandj/Study/CoreRouter/src/orchestration/optimizers/jo_vdpr_env.py)

**Fix 1 — Reward Function**: Thêm ma trận độ trễ thực tế vào reward
```python
# THAY THẾ:
distance = abs(node_v1 - node_v2)
reward = 100 - (distance * 10)

# BẰNG (Topology-Aware Reward):
LATENCY_MATRIX = np.array([
    [0,  2,  5,  8,  10],   # Node 0 (Edge)
    [2,  0,  2,  5,   8],   # Node 1 (Core - MSD=6)
    [5,  2,  0,  2,   5],   # Node 2 (Edge)
    [8,  5,  2,  0,   2],   # Node 3 (Edge)
    [10, 8,  5,  2,   0],   # Node 4 (Edge)
])
latency = LATENCY_MATRIX[node_v1][node_v2]
# Thưởng SFC đặt gần Core Router (node 1) nếu yêu cầu MSD cao
core_bonus = 50 if (msd_req >= 4 and (node_v1 == 1 or node_v2 == 1)) else 0
resource_efficiency = 1.0 - (cpu_req / self.max_cpu)
reward = 100 * resource_efficiency + core_bonus - latency * 5
```

**Fix 2 — Rebalance Penalty**: Giảm MSD penalty để không collapse
```python
# THAY THẾ:
penalty -= 1000  # quá lớn

# BẰNG (Scaled Penalty):
penalty -= 200  # cùng scale với reward ~100
```

**Fix 3 — Episode Length**: Tăng từ 30 lên 100 steps
```python
if self.current_time_step >= 100:  # Thay vì 30
    done = True
```

**Fix 4 — State Space mở rộng**: Bổ sung thông tin SFC request đang đến
```python
# Thêm 3 features: [cpu_req_normalized, ram_req_normalized, msd_req_normalized]
# Observation space từ 15 → 18 features
self.observation_space = spaces.Box(low=0, high=1, shape=(self.num_nodes * 3 + 3,), dtype=np.float32)
```

---

#### [MODIFY] [agent_ppo.py](file:///home/hung8uandj/Study/CoreRouter/src/orchestration/optimizers/agent_ppo.py)

**Fix 5 — Tăng Timesteps và Hyperparams**:
```python
# Tăng tổng steps để hội tụ
model.learn(total_timesteps=500000, reset_num_timesteps=True)

# Hyperparameters tốt hơn
model = PPO("MlpPolicy", env, verbose=1,
    learning_rate=3e-4,
    n_steps=2048,       # Tăng từ 1024
    batch_size=64,
    n_epochs=10,
    gamma=0.99,
    gae_lambda=0.95,
    clip_range=0.2,
    ent_coef=0.01,      # Khuyến khích khám phá
    tensorboard_log=log_dir
)
```

---

### Phase 2: Xây Dựng Dataset Thực Tế (1-2 ngày)

#### [MODIFY] [dataset_generator.py](file:///home/hung8uandj/Study/CoreRouter/src/analytics/dataset_generator.py)

Tích hợp và xử lý dữ liệu từ nguồn thực tế. Chiến lược 3 nguồn:

**Nguồn A — CAIDA Anonymized Internet Traces** (pcap → csv): Lưu lượng backbone thực tế của Internet. Flow có đặc tính thực.

**Nguồn B — MAWI Working Group Traffic Archive** (tcpdump): Traffic từ WIDE backbone Nhật Bản, có DDoS patterns thực.

**Nguồn C — Zenodo Telecom Datasets** (csv sẵn): Các dataset viễn thông 5G/LTE có sẵn ở dạng CSV.

**Chiến lược thực tế nhất**: Sinh dataset lớn có phân phối thực tế từ nghiên cứu học thuật:
- **10,000 dòng** với phân phối traffic thực tế từ paper (RFC 2544 / ITU-T Y.1541)
- Thêm cột `service_type` (VoIP/Video/Data/IoT) để phản ánh SFC thực tế
- Thêm cột `priority` phản ánh QoS priority của từng loại traffic
- Thêm time-series pattern (giờ cao điểm / thấp điểm) để Bi-GRU forecast được tốt hơn

#### [NEW] `data/dataset_v2_10k.csv` — Dataset 10,000 dòng

---

### Phase 3: Triển Khai DGRL — Graph Neural Network (2-3 ngày)

Đây là **điểm khác biệt học thuật cốt lõi** của JO-VDPR so với các baseline.

#### [NEW] `src/orchestration/optimizers/gnn_policy.py`

**Kiến trúc DGRL**:
```
SFC Request Features ──┐
                        ├──→ [GNN Encoder] ──→ [PPO Actor-Critic] ──→ Action (VNF Placement)
Topology Graph ─────────┘
  (Node features + Edge features)
```

**Cụ thể**:
- **GNN Encoder**: 2 lớp Graph Attention Network (GAT) với 64 hidden dims
  - Node features: [CPU_free, RAM_free, MSD_remaining, node_type]
  - Edge features: [latency, bandwidth_remaining]
  - Output: Node embeddings 64-dim cho mỗi node
- **Action Head**: Cross-attention giữa SFC request và node embeddings → Softmax chọn node

**Thư viện**: `torch_geometric` (PyTorch Geometric)

#### [NEW] `src/orchestration/optimizers/dgrl_agent.py`

```python
from torch_geometric.data import Data
from torch_geometric.nn import GATConv

class GNNPolicy(nn.Module):
    def __init__(self, node_features, edge_features, hidden_dim=64):
        super().__init__()
        self.gat1 = GATConv(node_features, hidden_dim, heads=4, concat=False)
        self.gat2 = GATConv(hidden_dim, hidden_dim, heads=4, concat=False)
        self.actor = nn.Linear(hidden_dim, num_nodes)  # VNF placement probability
        self.critic = nn.Linear(hidden_dim * num_nodes, 1)
    
    def forward(self, graph_data, sfc_request):
        x = F.relu(self.gat1(graph_data.x, graph_data.edge_index))
        x = self.gat2(x, graph_data.edge_index)
        # Cross attention với SFC request features
        ...
        return action_probs, value
```

---

### Phase 4: Benchmark Toàn Diện và Phân Tích (1 ngày)

#### [MODIFY] [benchmark_eval.py](file:///home/hung8uandj/Study/CoreRouter/src/analytics/benchmark_eval.py)

**Nâng cấp benchmark**:
- Tăng `NUM_EPISODES = 1000` (từ 500)
- Thêm **metric mới**: Throughput (Mbps processed), Average Latency, MSD Violation Rate
- Thêm **đường cong hội tụ** (không chỉ bar chart)
- Thêm **box plot** để thể hiện variance (quan trọng cho luận văn IEEE)
- So sánh PPO-MLP vs PPO-GNN (DGRL) thêm vào benchmark

#### [NEW] `src/analytics/experiment_runner.py`

Script orchestrate toàn bộ pipeline:
1. Generate dataset → 2. Train v2 PPO-MLP (fix) → 3. Train DGRL → 4. Benchmark all

---

## Phân Tích: Tại Sao DGRL Sẽ Cải Thiện?

| Capability | PPO-MLP (hiện tại) | PPO-GNN (DGRL) |
|------------|-------------------|-----------------|
| Nhận biết topology | ❌ Không | ✅ Có (GNN encode graph) |
| Hiểu quan hệ node | ❌ Không | ✅ Có (message passing) |
| Scale với larger graphs | ❌ Không (input fixe) | ✅ Có (GNN không phụ thuộc size) |
| Attention đến điểm tắc nghẽn | ❌ Không | ✅ GAT attention weights |
| Acceptance Ratio dự kiến | 54% | **70-80%** |

---

## Thứ Tự Ưu Tiên Thực Hiện

```
Tuần 1 (Ngay bây giờ):
├── [P1] Fix reward function + rebalance penalty     (2h)
├── [P1] Fix episode length (30→100)                 (30m)
├── [P1] Fix state space (thêm SFC request features) (1h)
├── [P1] Tăng training steps 100k→500k               (30m)
└── [P1] Chạy lại benchmark → so sánh kết quả mới

Tuần 1-2:
├── [P2] Build dataset_v2 10,000 dòng               (1 ngày)
├── [P2] Tích hợp dataset vào env                   (2h)
└── [P2] Retrain + benchmark

Tuần 2-3:
├── [P3] Cài torch_geometric                        (30m)
├── [P3] Implement GNNPolicy                        (1 ngày)
├── [P3] Implement DGRL agent (Custom SB3 policy)   (1 ngày)
├── [P3] Train DGRL 500k-1M steps                   (2-4h runtime)
└── [P3] Final benchmark: PPO-MLP vs PPO-GNN vs ILP

Tuần 3:
└── [P4] Phân tích kết quả + tạo biểu đồ cho luận văn
```

---

## Verification Plan

### Automated Tests
```bash
# Sau Phase 1: Kiểm tra reward không còn bằng phẳng
python3 src/orchestration/optimizers/agent_ppo.py
# → Learning curve phải cho thấy xu hướng tăng trong 100k steps đầu

# Sau Phase 2: Kiểm tra dataset loaded đúng
python3 src/analytics/dataset_generator.py
python3 -c "from jo_vdpr_env import JOVDPREnv; e=JOVDPREnv(); print(len(e.dataset))"
# → Phải ra ≥ 10000

# Final Benchmark
python3 src/analytics/benchmark_eval.py
# → JO-VDPR acceptance_ratio >= 70%, cumulative_reward >= Decoupled AI
```

### Manual Verification
- So sánh 3 biểu đồ trước/sau cho từng phase
- Learning curve phải hội tụ rõ ràng (đường đỏ phải tăng từ -18,000 lên ≥ -8,000)
- Acceptance Ratio JO-VDPR phải ≥ Decoupled AI (hiện tại 63.4%)
- Cumulative Reward JO-VDPR phải ≥ Decoupled AI (hiện tại -274,040)

---

## Ghi Chú Học Thuật Cho Luận Văn

Các cải tiến này tạo ra **3 đóng góp học thuật có thể trình bày**:

1. **Hardware-Aware Reward Design**: Reward function tích hợp MSD constraints và topology-aware latency — đây là novelty so với các DRL công trình trước.

2. **DGRL cho SFC Mapping**: Graph Attention Network encode topo mạng vào state representation — khác biệt so với Decoupled AI (topology-blind).

3. **Elephant-Mice Flow Analysis**: Phân tích hiện tượng Knapsack Problem trong SDN mapping (từ walkthrough cũ) — đây là insight độc đáo có thể viết thành 1 section phân tích trong chương 4.
