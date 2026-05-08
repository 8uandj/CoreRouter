# Trạng thái dự án (Current State)

## 1. Các hạng mục đã hoàn thành (Done)
- **Mô hình hóa toán học:** Đã định nghĩa hoàn chỉnh bài toán JO-VPPM dưới dạng MDP, tích hợp mô hình độ trễ 4 thành phần thực tế với hàng đợi M/G/1.
- **Hybrid Orchestration:** Chế độ RuleDRL linh hoạt kết hợp Heuristic (cho tải < 40%) và AI (cho bão tải > 60%).
- **Backend API Integration:** Đã tích hợp thành công logic Hybrid Orchestration vào Backend API (`/orchestrate`). API hỗ trợ tự động fallback từ Heuristic sang DGRL khi vi phạm Hard Constraints, và tự động kích hoạt tiến trình Make-Before-Break migration khi nhận cờ cảnh báo (Alert Flag) từ dự báo.
- **Môi trường RL:** Đã xây dựng `JOVDPREnv` hỗ trợ nhận thức mạng dạng đồ thị và ràng buộc phần cứng MSD.
- **Thuật toán AI cốt lõi:**
  - Hoàn thành cơ chế Invalid Action Masking để ép AI không bao giờ vi phạm giới hạn MSD.
  - Tích hợp GAT (Graph Attention Network) với Static Adjacency Matrix để giữ ổn định ma trận phổ.
  - Tích hợp Adaptive Lagrangian Penalty để cân bằng tự động giữa Latency SLA và Reward.
- **Hạ tầng mô phỏng & Kết quả Benchmark:** 
  - Khởi tạo thành công 3 topologies: Vietnam Backbone (10-node), NSFNET (14-node), GÉANT2 (22-node).
  - Hoàn thành benchmark trên 900,000 steps. Tại kịch bản Stress Test trên GEANT2, JO-VPPM đạt Acceptance Rate **16.4%** (Tăng +121% so với Greedy), giảm 60% vi phạm MSD. Việc Reject 83.6% request là "Smart Admission Control" dựa trên Định lý Little (Little's Law) để bảo vệ mạng khỏi sụp đổ.

## 2. Các hạng mục đang thực hiện (WIP)
- **Định hướng triển khai chính thức hiện tại: Hybrid Orchestration (RuleDRL).** Mọi WIP code phải bám theo trục Heuristic + DGRL (MaskablePPO) + Make-Before-Break đã có.
- Tinh chỉnh ổn định training PPO: chuẩn hóa reward kết hợp `VecNormalize` với cấu hình rollout cố định (xem mục 3 — Known Issues).
- Hoàn thiện đường ống Backend `/orchestrate` (fallback Heuristic→DGRL khi vi phạm Hard Constraints, kích hoạt Make-Before-Break theo Alert Flag).

> ⛔ **Đã HỦY khỏi roadmap code và TODO list hiện tại (KHÔNG được sinh code, KHÔNG đưa vào WIP):**
> - Multi-Objective RL (MORL) / Pareto Front.
> - Curriculum Learning.
>
> Các hạng mục trên CHỈ được phép xuất hiện trong **luận văn — Chương 6 Future Work** dưới dạng định hướng nghiên cứu, KHÔNG được implement vào branch code hiện tại.
> Federated Learning cho 6G cũng chỉ thuộc Chương 6 Future Work.

## 3. Các vấn đề đang theo dõi (Known Bugs/Issues)
- **Gradient explode / Explained Variance thấp khi train GAT+PPO:** KHÔNG được nêu `VecNormalize` như giải pháp đơn lẻ. `VecNormalize` BẮT BUỘC phải đi kèm bộ siêu tham số PPO sau (đã được kiểm chứng ổn định cho dự án):
  - `n_steps = 512`
  - `10` parallel environments (vectorized envs)
  - tổng rollout batch = `10 × 512 = 5120` steps
  - `batch_size = 128` hoặc `256`
  Nếu chỉ bật `VecNormalize` mà không đi kèm cấu hình rollout/batch ở trên thì KHÔNG được coi là fix hợp lệ — agent phải từ chối và yêu cầu áp dụng đồng thời cả gói cấu hình.
- **HTTP 409 / `NO_SAFE_ACTION` KHÔNG PHẢI BUG:** Đây là hành vi đúng của **Smart Admission Control**. Khi không tồn tại cặp placement/routing nào thỏa Hard Constraints (MSD, CPU, Alert), hệ thống PHẢI từ chối request thay vì ép đặt VNF. Tuyệt đối **không "fix"** bằng cách bỏ Action Masking, hạ ngưỡng MSD, hay ép placement vào node không an toàn.
- **Smart Admission Control hợp lệ theo Định lý Little (Little's Law):** Trong Stress Test trên GEANT2, việc reject **83.6%** request để bảo toàn **16.4%** request được chấp nhận an toàn (tránh tràn MSD và sụp đổ mạng) là hành vi mong muốn, KHÔNG phải lỗi cần sửa.
- Cần chú ý cẩn thận khi kết nối P4Runtime với Mininet ở môi trường thật, dễ gặp lỗi timeout nếu Controller gửi rule quá nhanh.
