# Tổng quan dự án: 3S-COM (Smart, Scalable, Secure)

## 1. Bài toán cốt lõi
Dự án tập trung vào việc giải quyết bài toán **JO-VPPM Version 10 (Joint Optimization of VNF Placement and Proactive Migration)** trong môi trường mạng lõi phân tán địa lý (geo-distributed backbone networks). Hệ thống kết hợp cơ chế Hybrid Orchestration và Make-Before-Break.

Vấn đề thực tế mà hệ thống giải quyết: Các thuật toán AI (DRL) thông thường coi mạng là đường ống vô tận và bỏ qua giới hạn phần cứng của Data Plane. Điều này dẫn đến việc tạo ra các chuỗi dịch vụ (SFC) với nhãn SRv6 quá dài, vượt qua giới hạn **MSD (Maximum Segment Depth)** của switch (như chip Intel Tofino). Hậu quả là switch không thể đọc được gói tin (parse error) và sẽ drop toàn bộ luồng dữ liệu. 

## 2. Giải pháp của 3S-COM
Hệ thống đóng vai trò như một bộ não điều phối (Orchestrator) thông minh:
- **Tôn trọng phần cứng tuyệt đối**: Đưa giới hạn MSD vào thành "ràng buộc cứng" (Hard constraint) thông qua kỹ thuật Invalid Action Masking. AI không bao giờ được phép chọn node vượt quá MSD.
- **Di dời chủ động (Proactive Migration)**: Không chờ mạng sập mới cứu. Hệ thống dùng mô hình Time-series để dự báo "Elephant flows" và chủ động di dời VNF sang node khác trước khi xảy ra nghẽn (Stateless Flow Steering).
- **Học sâu trên đồ thị (DGRL)**: Sử dụng Graph Attention Networks (GAT) với ma trận kề tĩnh (Static Adjacency Matrix) để giúp AI "nhìn" được không gian địa lý của các Data Center, từ đó phân bổ tải hiệu quả hơn.
- **Tối ưu hóa kết hợp (Joint Optimization)**: Vượt qua nghịch lý hai giai đoạn (chia để trị), Agent đưa ra quyết định đồng thời (Single-step) cả Placement và Routing trong một không gian hành động nguyên tử `[v_place, v_route]`.
- **Hybrid Orchestration (RuleDRL)**: Khi tải mạng thấp (< 40%), bypass AI và dùng thuật toán Heuristic (Decoupled) để tối ưu chi phí. Khi tải mạng cao (> 60%), nhường quyền điều khiển cho AI (JO-VPPM) để bảo vệ mạng, hy sinh trễ để đảm bảo an toàn MSD.

> 🎯 **Định hướng triển khai chính thức (Official Roadmap):** **Hybrid Orchestration (RuleDRL + MaskablePPO + Make-Before-Break)**. Đây là trục duy nhất được phép phát triển code ở thời điểm hiện tại. Mọi đề xuất MORL / Pareto Front / Curriculum Learning chỉ được phép xuất hiện trong **luận văn Chương 6 Future Work**, không được sinh code hay đưa vào TODO list.

## 2.1. Phân lớp SLA (SLA Classes)
Hệ thống phân loại traffic theo các lớp SLA độ trễ end-to-end để Reward Shaping và Admission Control áp dụng đúng ngưỡng:

| Lớp SLA       | Ngưỡng độ trễ mục tiêu | Ghi chú |
|---------------|-------------------------|---------|
| URLLC         | ~1–10 ms                | Ultra-Reliable Low-Latency Communication. |
| VoIP          | ~30–50 ms               | Thoại thời gian thực. |
| Video         | ~50–80 ms               | Streaming / hội nghị truyền hình. |
| **Traffic Data** | **~80–100 ms**       | **Bắt buộc có** — lớp dữ liệu thường (web/file/API). KHÔNG được bỏ sót khi cấu hình SLA. |

Khi vi phạm ngưỡng của bất kỳ lớp nào, áp Penalty theo Adaptive Lagrangian. Thiếu lớp Traffic Data sẽ dẫn tới Reward bias về low-latency và Admission Control sai lệch.

## 3. Tech Stack
- **Control Plane & AI**: Python 3.10+, PyTorch, Stable-Baselines3 (MaskablePPO), Gymnasium.
- **Data Plane**: P4-16 (BMv2 switch), SRv6 (Segment Routing over IPv6), Mininet.
- **Orchestration**: Kubernetes (MicroK8s), Docker.

## 4. Tập người dùng
- Các nhà nghiên cứu viễn thông, kỹ sư SDN/NFV.
- Môi trường thử nghiệm mô phỏng mạng lõi với các Topology đa dạng: Vietnam Backbone (10 nodes), NSFNET (14 nodes), và GÉANT2 (22 nodes).
