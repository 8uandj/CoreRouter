# Quy tắc lập trình & Định dạng Code (Conventions)

## 1. Python Code
- **Type Hinting:** Bắt buộc sử dụng Type Hint đầy đủ cho mọi functions và methods (e.g., `def calculate_latency(path: List[int]) -> float:`).
- **Docstring:** Sử dụng chuẩn Google format. Viết mô tả rõ ràng về input/output, đặc biệt đối với các hàm liên quan đến RL environment.
- **Logging:** TUYỆT ĐỐI KHÔNG dùng `print()` trong production code. Sử dụng thư viện `logging` tiêu chuẩn (cấu hình trong file utils hoặc đầu file).
- **PEP8:** Tuân thủ chuẩn PEP8 về thụt lề, khoảng trắng và đặt tên.
- **Naming Conventions:**
  - Classes: `PascalCase`
  - Functions/Variables: `snake_case`
  - Constants: `UPPER_SNAKE_CASE`
  - Cố gắng giữ tên biến giống với ký hiệu toán học trong bài báo/luận văn nếu có thể (VD: `lambda_msd`, `tau_target`).

## 2. Quy tắc khi xử lý Logic Nghiệp Vụ (Business Logic Rules)
- **Tôn trọng MSD (Maximum Segment Depth):** Bất cứ logic routing hay placement nào cũng phải đi kèm check: `if len(srv6_sids) > node.msd_limit: return ERROR`. Đây là luật bất di bất dịch của phần cứng.
- **Sử dụng Ma trận tĩnh cho GAT:** Khi viết code cho Graph Neural Network, KHÔNG truyền ma trận Adjacency Matrix động (thay đổi theo mỗi step). Phải truyền ma trận tĩnh (mô tả kết nối cáp quang vật lý) để giữ vững eigenvalues cho mạng nơ-ron học.
- **Không gian Hành động Nguyên tử (Atomic Action):** AI Agent phải xuất ra cặp quyết định `[v_place, v_route]` đồng thời trong không gian `MultiDiscrete([N, N])`. Không tách rời việc Placement và Routing thành 2 bước rời rạc để tránh The Two-Stage Flaw.
- **Xử lý Cờ Dự Báo (Alert Flag):** Nếu node có cờ `Alert = 1` (do Bi-GRU dự báo quá tải), khi thuật toán/Agent chọn node đó phải chịu một Penalty cực nặng (Penalty = -50).

## 3. Quản lý State
- Mọi biến đổi làm ảnh hưởng tới trạng thái mạng (giảm CPU, tăng MSD utilization) phải được thực hiện trong hàm `step()` của RL Environment và phải có cơ chế rollback nếu fail.

## 4. Phạm vi Roadmap (Bắt buộc tuân thủ)
- **Định hướng triển khai chính thức = Hybrid Orchestration (RuleDRL + MaskablePPO + Make-Before-Break).** Mọi PR/commit phải nằm trong phạm vi này.
- **CẤM sinh code, CẤM thêm vào TODO/WIP** các hạng mục sau (chỉ được mô tả ở luận văn Chương 6 Future Work):
  - Multi-Objective RL (MORL) / Pareto Front (mặt Pareto thay cho cộng dồn Reward).
  - Curriculum Learning ("từ dễ đến khó").
  - Federated / Multi-Agent phân tán cho 6G.
- Nếu user yêu cầu implement các hạng mục Chương 6 trên branch hiện tại, agent phải **TỪ CHỐI** và chỉ ngược lại để mở issue/PR riêng cho Future Work khi roadmap chính thức được thay đổi.

## 5. Cấu hình PPO chuẩn cho Stability (Bắt buộc khi train DGRL)
Khi training MaskablePPO + GAT, để xử lý gradient explode / Explained Variance thấp, BẮT BUỘC dùng **đồng thời** `VecNormalize` và bộ siêu tham số rollout sau:
- `n_steps = 512`
- `10` parallel envs (vectorized)
- tổng rollout batch = `10 × 512 = 5120` steps
- `batch_size = 128` hoặc `256`

Chỉ bật `VecNormalize` mà không kèm cấu hình rollout/batch nêu trên KHÔNG được coi là fix hợp lệ.

## 6. Smart Admission Control vs Bug
- HTTP `409 NO_SAFE_ACTION` = hành vi đúng (Smart Admission Control), KHÔNG được "fix" bằng việc nới Hard Constraints hay ép placement.
- Việc reject 83.6% / accept 16.4% trong stress test (GEANT2) tuân Little's Law là hợp lệ, KHÔNG phải lỗi acceptance rate.
