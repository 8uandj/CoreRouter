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
- Phát triển định hướng tương lai (Future Work) theo Chương 6:
  - Tích hợp Multi-Objective RL (MORL) (Mặt Pareto thay vì cộng dồn Reward).
  - Curriculum Learning ("từ dễ đến khó" chống Catastrophic Forgetting).
  - Federated Learning cho kiến trúc 6G (Multi-Agent phân phân tán).

## 3. Các vấn đề đang theo dõi (Known Bugs/Issues)
- GAT đôi khi bị bùng nổ gradient nếu hàm Reward không được normalize kỹ. Hãy dùng `VecNormalize` của SB3.
- Cần chú ý cẩn thận khi kết nối P4Runtime với Mininet ở môi trường thật, dễ gặp lỗi timeout nếu Controller gửi rule quá nhanh.
