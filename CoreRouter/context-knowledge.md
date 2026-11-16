--------------------------------------------------------------------------------
# CƠ SỞ TRI THỨC TOÀN DIỆN DỰ ÁN JO-VPPM (VERSION 10)
**Tên đề tài:** Joint Optimization of VNF Placement and Proactive Migration under Data-Plane Hardware Constraints.
**Mô hình cốt lõi:** Deep Graph Reinforcement Learning (DGRL) kết hợp Hybrid Orchestration & Make-Before-Break.

---

## 1. TỔNG QUAN HỆ THỐNG VÀ BỐI CẢNH (SYSTEM CONTEXT)
Dự án nhằm xây dựng phân hệ điều phối mạng (Orchestrator) cho hệ thống **3S-COM**, giải quyết bài toán Online Joint Orchestration cho SFC (Service Function Chain) [1, 3].
*   **Điểm khác biệt cốt lõi (Novelty):** Biến Giới hạn phần cứng P4 (MSD - Maximum Segment Depth của SRv6) thành **Ràng buộc cứng (Hard Constraints)**, và thay thế cơ chế phản ứng bị động (Reactive) bằng **Di dời chủ động (Proactive Migration)** [2, 3].
*   **Topology Testbed:** Hỗ trợ tính khái quát hóa (Generalization) trên 3 đồ thị mạng: Vietnam Backbone (10 nodes), NSFNET (14 nodes), và GÉANT2 (22 nodes) [2, 3].

---

## 2. NỀN TẢNG TOÁN HỌC VÀ VẬT LÝ (MATH & PHYSICS FOUNDATION)

### 2.1. Mô hình Trễ 4 Thành phần (Physics-Aware Latency)
Hệ thống không dùng hằng số giả định mà tính toán dựa trên vật lý thực [2]:
1.  **Trễ quang học ($D_{prop}$):** Tính bằng công thức Haversine (khoảng cách cong Trái Đất) chia cho vận tốc ánh sáng trong sợi quang ($200,000$ km/s) [2, 3]. Ngưỡng mạng WAN VN tối thiểu là 7.5ms.
2.  **Trễ xử lý nhãn ($D_{srv6}$):** Thời gian Switch P4 đọc và chèn nhãn ($0.05ms \times$ Số lượng SID) [2, 3].
3.  **Trễ hàng đợi ($D_{queue}$):** Sử dụng **Hàng đợi M/G/1 (Pollaczek-Khinchine)** thay vì M/M/1 để mô phỏng lưu lượng bùng nổ (Heavy-tail, Pareto) với phương sai $C_v^2 \approx 3.0$ [2, 3]. Khi CPU > 80%, độ trễ vọt lên theo đường tiệm cận đứng [2].

### 2.2. Giới hạn Sức chứa & Định lý Little (Little's Law)
Biện luận cho tỷ lệ Acceptance Rate 16.4% ở kịch bản Stress Test [4]:
*   **Công thức:** $L = \lambda W$ (Trong đó $\lambda = 1.0$ req/step, $W \approx 300$ steps) [4].
*   **Biện luận:** Mạng GEANT2 (22 nodes) chỉ chứa được tối đa 15-18% lượng khách hàng đồng thời trước khi tràn tài nguyên vật lý. Việc hệ thống reject ~83.6% request là hành vi **Kiểm soát thu nhận thông minh (Smart Admission Control)** nhằm chống lại sự sụp đổ dây chuyền, bảo vệ an toàn 100% cho các luồng đã nhận [3, 4].

---

## 3. KIẾN TRÚC THUẬT TOÁN AI CỐT LÕI (AI ARCHITECTURE)

### 3.1. Deep Graph Reinforcement Learning (DGRL)
*   **Observation Space ($N \times 6 + 13$):** State của mỗi Node chứa `[CPU_util, RAM_util, MSD_used, MSD_free, Alert_Flag, Geo_Latency]` [3]. Trích xuất đặc trưng bằng **Graph Attention Network (GAT)** với Ma trận kề tĩnh để đảm bảo phổ đồ thị không bị nhiễu, giúp đạt *Explained Variance = 0.42* [3].
*   **Action Space:** MultiDiscrete([N, N]) chọn cặp [v1, v2] cho Placement và Ingress Routing [3].

### 3.2. Quản trị Ràng buộc (Constraint Management)
Hệ thống phân tách rõ 2 loại ràng buộc để tránh xung đột hàm mục tiêu:
1.  **Hard Constraints (Ràng buộc cứng - CPU, RAM, MSD):** Giải quyết bằng **Invalid Action Masking** (sử dụng MaskablePPO). Cắt logit của các hành động sai về $-\infty$, ép xác suất vi phạm phần cứng xuống 0% [2, 3].
2.  **Soft Constraints (Ràng buộc mềm - Delay SLA):** Giải quyết bằng **Adaptive Lagrangian Penalty ($\lambda$)**. Phạt Agent nếu tổng trễ vượt SLA thực tế: VoIP (< 50ms), Video (< 30ms), URLLC (< 10ms) [2, 3]. 

### 3.3. Kiến trúc Điều phối Lai (Hybrid Orchestration / RuleDRL)
Khắc phục điểm yếu "Cẩn trọng thái quá" (Over-Conservatism) của RL ở Normal Load:
*   **Công thức đo tải:** $\mathcal{U}_{global}(t) = \max (Avg\_CPU, Avg\_MSD)$
*   **Khi $\mathcal{U}_{global} < 40\%$ (Ngày thường):** Bypass AI, dùng thuật toán Heuristic (Decoupled) để đạt Acceptance 99.8% và Latency 0.11ms.
*   **Khi $\mathcal{U}_{global} > 60\%$ (Bão DDoS/Stress):** Chuyển quyền cho **JO-VPPM (AI)** để bảo vệ mạng, hy sinh trễ để đảm bảo an toàn MSD, giúp phục vụ lượng SFC gấp đôi (+121%) so với SOTA Heuristic.


### 3.4. Bản chất Tối ưu hóa Kết hợp (The "Joint" Optimization Logic)
Điểm khác biệt cốt lõi của JO-VPPM so với các phương pháp Decoupled (Chia để trị) hiện hành nằm ở khả năng xử lý bài toán VNF Placement và Traffic Routing trong một không gian quyết định duy nhất (Single-step decision-making).

*   **Vượt qua Nghịch lý Hai giai đoạn (The Two-Stage Flaw):** 
    * Các phương pháp truyền thống thường mắc sai lầm khi chọn Node trước rồi mới tìm đường (gây quá tải băng thông/MSD trên link), hoặc tìm đường trước rồi mới ép VNF vào Node (gây thiếu hụt CPU/RAM). JO-VPPM khắc phục điều này bằng cách đánh giá toàn diện trạng thái mạng (Comprehensive Resource-Aware).
*   **Không gian hành động Nguyên tử (Atomic Action Space):** 
    * Agent sử dụng không gian hành động `MultiDiscrete([N, N])` để xuất ra một cặp giá trị $[v_{place}, v_{route}]$ đồng thời. Mạng GAT đánh giá sự phù hợp của tổ hợp này dựa trên hàm mục tiêu kết hợp (Joint Objective Function).
*   **Đánh giá Phần thưởng Tích hợp (Holistic Reward Evaluation):** 
    * Tổ hợp hành động chỉ nhận được phần thưởng dương khi và chỉ khi: Node $v_{place}$ đủ tài nguyên tính toán (CPU/RAM) VÀ đường dẫn qua $v_{route}$ tuân thủ nghiêm ngặt giới hạn phần cứng P4 (MSD limit), đồng thời thỏa mãn ngưỡng trễ SLA. Nếu một trong hai yếu tố thất bại, toàn bộ tổ hợp bị loại bỏ thông qua Invalid Action Masking.
*   **Joint trong Di dời chủ động (Joint Migration):** 
    * Quá trình Migration không hoạt động độc lập. Khi cờ `Alert = 1` xuất hiện, bài toán "Né tải" được đưa vào cùng không gian tính toán Joint. Agent đồng thời tính toán chi phí lập bản sao VNF tại Node mới (Placement Cost) và chi phí bẻ luồng SRv6 qua mạng (Switching Cost), đảm bảo quá trình Make-Before-Break đạt Zero-Downtime và chi phí thấp nhất.

---

## 4. CƠ CHẾ DI DỜI CHỦ ĐỘNG (PROACTIVE MIGRATION)
Hệ thống thực hiện quy trình **Stateless Flow Migration (Make-Before-Break)** để đạt Zero-Downtime [2]:
1.  **Dự báo (Alert):** Module **Bi-GRU** phân tích Time-series telemetry 2 chiều, dự báo luồng voi (Elephant flows). Bật cờ `Alert = 1` tại node sắp nghẽn [2].
2.  **Trừng phạt (Penalty):** DRL Agent bị trừ điểm cực nặng (-50) nếu cố tình nạp VNF vào node có cờ Alert [2, 3].
3.  **Sơ tán (3 bước MBB):**
    *   *Make:* Khởi tạo bản sao VNF tại Node an toàn mới [2].
    *   *Steer:* Giao tiếp API qua SDN/P4Runtime bẻ luồng dữ liệu (Switching Cost = -3.0) [2, 3].
    *   *Break:* Xóa VNF cũ giải phóng tài nguyên [2].

---

## 5. KẾT QUẢ THỰC NGHIỆM VÀ SOTA BENCHMARK (RESULTS & BENCHMARK)
Kết quả chạy trên 900,000 steps (5 seeds × 10,000 steps × 3 topologies × 3 scenarios) [4, 5]:
*   **Sức chịu đựng thảm họa:** Tại Stress Test mạng GEANT2, JO-VPPM đạt Acceptance Rate **16.4%** (Tăng **+121%** so với Greedy chỉ đạt 7.4%), giảm **60%** vi phạm MSD [4, 5].
*   **Chống thiên kiến (Survivorship Bias):** Chỉ số độ trễ Sub-1.5ms chỉ được tính trên tập các request *đã được chấp nhận* để đảm bảo tính minh bạch khoa học.

---

## 6. DANH MỤC TÀI LIỆU SOTA BẢO VỆ (REFERENCE & BIBLIOGRAPHY)
Dùng để viết chương Related Work và biện luận số liệu [6]:
1.  **Về Proactive Migration:** Trích dẫn `moshiri2026proactive` (Forecast-Driven DRL trong DC) và `hu2026rlpmo` (RL cho Migration song song) để bảo vệ module Bi-GRU và Make-before-break.
2.  **Về Định lý Little & Toán học:** Trích `little1961proof` (A proof for L=λW) và `bertsekas1992data` (M/G/1 queue) để bảo vệ việc Reject 84% request là tất yếu vật lý.
3.  **Về Ràng buộc P4/MSD:** Trích `stockmayer2020p4sfc` (P4-SFC) để giải thích cơ chế bẻ luồng bằng SRv6 Header.
4.  **Về Đối thủ / Baseline:** Coi các baseline trong code là đại diện cho SOTA như `wu2025drl` (DRL-FJM, 2025) vốn thiếu Action Masking nên sụp đổ khi bị ép tải phần cứng.

---

## 7. HƯỚNG PHÁT TRIỂN TƯƠNG LAI (FUTURE WORK)
Đề xuất ghi vào Chương 6 của luận văn để chứng tỏ tầm nhìn:
1.  **Multi-Objective RL (MORL):** Thay vì cộng dồn Reward, huấn luyện AI để xuất ra một Mặt Pareto (Pareto Front) kết hợp nhiều mục tiêu theo nghiên cứu của Kuang et al.
2.  **Curriculum Learning:** Huấn luyện Agent "từ dễ đến khó" thay vì thả trực tiếp vào môi trường bão hòa (nhưng cần cẩn trọng bẫy Catastrophic Forgetting).
3.  **Federated Learning cho 6G:** Mở rộng kiến trúc Single-Agent thành Multi-Agent phân tán trên toàn cầu để xử lý bài toán Multi-Domain.

---
**[END OF KNOWLEDGE BASE]**