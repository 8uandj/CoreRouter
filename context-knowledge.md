 SYSTEM CONTEXT & KNOWLEDGE BASE: 3S-COM ORCHESTRATOR PROJECT
1. TỔNG QUAN DỰ ÁN (PROJECT OVERVIEW)
Dự án nhằm xây dựng nền tảng 3S-COM (Smart, Secure and SDN&NFV-powered Controller, Orchestrator & Manager), đóng vai trò là bộ não điều phối mạng lõi (Core Network) 1, 2.
Kiến trúc tổng thể: Sử dụng chuẩn NFV-MANO (ETSI) kết hợp SDN để tách biệt Control Plane và Data Plane 3-5.
Mặt phẳng dữ liệu (Data Plane - 3S-Router): Sử dụng thiết bị phần cứng hộp trắng (Whitebox switches) chạy chip chuyên dụng (như Intel Tofino) có khả năng lập trình bằng ngôn ngữ P4 để thực thi Data Plane ở tốc độ đường truyền (Line-rate) 5-8.
Công nghệ định tuyến: Sử dụng SRv6 (Segment Routing over IPv6) để bẻ lái luồng (Traffic Steering) qua các chuỗi dịch vụ mạng SFC (Service Function Chain) 8, 9.
2. KHOẢNG TRỐNG NGHIÊN CỨU & MỤC TIÊU ĐÓNG GÓP (RESEARCH GAPS & NOVELTIES)
Hardware-Awareness (Nhận thức phần cứng): Các mô hình cũ coi mạng là đường ống vô tận 8. Dự án này áp dụng các giới hạn vật lý cứng như bộ nhớ TCAM và đặc biệt là MSD (Maximum Segment Depth) – giới hạn số lượng nhãn SRv6 (mỗi nhãn 128-bit) mà switch có thể chèn vào gói tin mà không làm rớt mạng 8.
Proactive Migration (Di chuyển chủ động): Thay vì đợi mạng nghẽn hoặc bị DDoS mới cấu hình lại (Reactive), hệ thống sử dụng AI (Time-series forecasting) để dự báo sớm và sơ tán VNF, đảm bảo tính nhất quán của trạng thái (State Consistency) 8, 10, 11.
Graph-Aware DRL (Học tăng cường sâu trên đồ thị): Các thuật toán Heuristic truyền thống không hiểu được cấu trúc hình học của mạng. Dự án dùng GNN (Graph Neural Network) kết hợp DRL để agent tự học chiến lược ưu tiên luồng 12-14.
3. MÔ HÌNH HÓA TOÁN HỌC (MATHEMATICAL FORMULATION - JO-VDPR)
Bài toán Tối ưu hóa chung Phân rã VNF, Đặt vị trí và Định tuyến (JO-VDPR) là một bài toán NP-Hard 15, 16, được mô hình hóa dưới dạng Quy hoạch Tuyến tính Nguyên (ILP/MILP) 17-19.
3.1. Định nghĩa các tập hợp và thông số (Sets & Parameters)
Mạng vật lý (Substrate Network): Đồ thị vô hướng $G_S = (N_S, E_S)$ 20, 21.
$N_S$: Tập các node vật lý (Servers, Switches).
$E_S$: Tập các liên kết vật lý.
$C_n^{cpu}, C_n^{mem}, C_n^{sto}$: Sức chứa CPU, RAM, Storage của node vật lý $n$ 19, 22, 23.
$B_{u,v}, D_{u,v}$: Băng thông và độ trễ của link vật lý $(u,v)$ 20, 23.
$MSD_n$: Giới hạn độ sâu nhãn SRv6 tối đa của node $n$ 8, 24.
Yêu cầu SFC (SFC Requests): Tập $R$, mỗi yêu cầu $r \in R$ là đồ thị có hướng $G_V = (N_V, E_V)$ 20, 25.
$V_r = \langle v_{r,1}, v_{r,2}, ..., v_{r,k} \rangle$: Chuỗi các VNF có thứ tự 20.
$f_r$ (hoặc $\beta_r$): Băng thông yêu cầu của chuỗi 20, 26.
$\tau_r^{td}$: Giới hạn độ trễ tối đa cho phép (End-to-end Delay Constraint) 27.
$\pi_r$: Trọng số ưu tiên của dịch vụ (Priority weight) 28.
3.2. Biến quyết định (Decision Variables)
$z_{r,f,k} \in \{0,1\}$: Bằng 1 nếu VNF $f$ của chuỗi $r$ được phân rã theo phương án $k$ 28, 29.
$x_{r,j}^{n} \in \{0,1\}$: Bằng 1 nếu VNF thứ $j$ của chuỗi $r$ được đặt (mapped) tại node vật lý $n$ 19, 28, 30.
$y_{r}^{u,v} \in \{0,1\}$: Bằng 1 nếu luồng giao thông của chuỗi $r$ đi qua link vật lý $(u,v)$ 28, 30.
3.3. Hàm mục tiêu (Objective Functions)
Mục tiêu là tối thiểu hóa tổng chi phí có trọng số (Cost Minimization) hoặc tối đa hóa tỷ lệ chấp nhận (Acceptance Ratio) 31, 32:$$ \min C_{total} = \sum_{r \in R} \pi_r \cdot (\alpha L_r + \beta E_r + \gamma M_r) $$Trong đó:
$L_r$: Độ trễ tổng (Bao gồm Propagation delay, Processing delay, và SRv6 parsing delay) 32.
$E_r$: Tiêu thụ năng lượng / Chi phí tài nguyên 32.
$M_r$: Chi phí cấu hình lại / di chuyển (Migration penalty) 32, 33.
3.4. Các ràng buộc cốt lõi (Constraints)
Ràng buộc vị trí (Placement): Mỗi VNF chỉ được đặt ở đúng một node.$$ \sum_{n \in N_S} x_{r,j}^n = 1 \quad \forall j \in V_r $$ 34, 35.
Ràng buộc tài nguyên Node (Capacity):$$ \sum_{r, j} x_{r,j}^n \cdot \phi_{r,j}^{cpu} \le C_n^{cpu} \quad \forall n \in N_S $$ 34, 35.
Ràng buộc Băng thông (Bandwidth):$$ \sum_{r} y_r^{u,v} \cdot f_r \le B_{u,v} \quad \forall (u,v) \in E_S $$ 34, 35.
Ràng buộc Bảo toàn luồng (Flow Conservation): Đảm bảo tính liên tục của path 34.
Ràng buộc Độ trễ (Latency): $\sum Delay \le \tau_r^{td}$ 31, 35.
Ràng buộc SRv6 MSD (Phần cứng): Chiều dài chuỗi VNF được bọc nhãn không được vượt quá giới hạn $MSD$ của chip P4 8, 32.
4. CÁC THUẬT TOÁN TỐI ƯU SỬ DỤNG TRONG 3S-COM (OPTIMIZATION METHODS)
4.1. Deep Graph Reinforcement Learning (DGRL) / MA-DDPG
Giải pháp học tăng cường sâu đa tác tử trên đồ thị nhằm tự động điều phối tài nguyên theo độ ưu tiên 14, 36.
Markov Decision Process (MDP):
State ($S_t$): Chứa thông tin về đồ thị topo, CPU/RAM/BW còn lại, hàng đợi SRv6, và yêu cầu SFC 37, 38. Thường được trích xuất đặc trưng bằng GNN (Graph Neural Network) để gom cụm không gian/thời gian 13, 39.
Action ($A_t$): Vector liên tục (DDPG/PPO) quyết định việc thêm/bớt node tính toán, gán vị trí VNF ($x_{r,j}^n$) và thiết lập path ($y_r^{u,v}$) 40, 41.
Reward ($R_t$): Thưởng dương (+2.0) nếu mapping thành công và thoả mãn SLA trễ; Phạt âm (-1.5) nếu rớt gói, vượt MSD, hoặc vi phạm QoS 42, 43.
4.2. Multi-Objective Evolutionary Algorithm (MOEA - NSGA-II)
Giải pháp toán học tìm tập tối ưu Pareto cho việc phân rã và đặt VNF đồng thời 15, 44.
Cơ chế: Mã hóa các phương án rã VNF và đặt node thành các "Nhiễm sắc thể" (Chromosomes). Sử dụng các toán tử lai ghép (Crossover) và đột biến (Mutation) 45.
Crowding Distance & Non-dominated Sorting: Dùng để loại bỏ các cấu hình vi phạm TCAM hoặc MSD, tối ưu hoá đồng thời hai mục tiêu xung đột là: Giảm độ trễ (Latency) vs Giảm chi phí ánh xạ (Mapping Cost) 15, 46.
4.3. Prediction-Assisted SRv6 Heuristic (PASH)
Dành cho cơ chế phản ứng tự động bảo mật cao (Closed-loop mitigation) 10, 44.
Dự báo (Prediction): Áp dụng mô hình Time-series (như Bi-GRU, LSTM) để phân tích logs thu thập từ các VNF, dự đoán sớm các cuộc tấn công (như DDoS) hoặc xu hướng cạn kiệt tài nguyên 10, 47, 48.
Chủ động di dời (Proactive Migration): Trước khi node bị nghẽn (gây drop gói tin và mất trạng thái), hệ thống tự động sinh ra kịch bản di chuyển các VNF quan trọng sang node khác.
Steering: Cập nhật lại luật trên switch P4 với nhãn SID mới, đảm bảo duy trì độ sâu dưới mức MSD 8, 49.
5. KIẾN TRÚC MÔI TRƯỜNG THỰC NGHIỆM (TESTBED IMPLEMENTATION)
AI cần lưu ý khi sinh code hoặc kịch bản triển khai Demo:
Phần mềm Switch (Data Plane): Dùng BMv2 (Behavioral Model version 2) chạy trong Docker (hoặc môi trường Native) bằng ngôn ngữ P4-16. Biên dịch bằng p4c (mã nguồn từ opennetworking/p4c hoặc p4lang/p4c) 6, 7, 50.
Các luật cơ bản: push_sfc_label cho Ingress 49.
Sử dụng API simple_switch_CLI hoặc P4Runtime để nạp flow rules (nhãn SRv6 0xABCD) 51, 52.
Hạ tầng mạng ảo (NFVI Emulator): Dùng Mininet (với module tự viết bằng Python topo_p4.py) để giả lập Host, vFirewall, Switch 53, 54. Cần gán cờ docker run --privileged và ánh xạ network namespace cho các port Mininet.
Hệ thống điều phối (Orchestrator Control Plane): Dùng OSM (Open Source MANO) hoặc ONAP chạy trên cụm Kubernetes (MicroK8s) để phân rã file TOSCA (VNFD/NSD) và điều khiển vòng đời Pods 55-58.
6. HƯỚNG DẪN KẾ THỪA CHO AI ASSISTANT (INSTRUCTIONS FOR AI)
Dựa trên ngữ cảnh trên, khi tôi (người dùng) yêu cầu viết code, thiết kế logic hoặc triển khai mô hình, bạn phải:
Luôn kiểm tra các ràng buộc vật lý: Nếu tôi yêu cầu code thuật toán mapping VNF, bạn cần chắc chắn thêm biến kiểm tra $MSD$ và TCAM chứ không chỉ CPU/RAM thông thường.
Tuân thủ danh pháp biến: Sử dụng các ký hiệu đã định nghĩa trong mục 3 (như $x_{r,j}^n$, $y_{r}^{u,v}$, $\tau_r^{td}$) khi giải thích thuật toán tối ưu.
Tích hợp DRL chuẩn xác: Khi viết code Python (PyTorch) cho RL agent, hãy thiết kế Reward function xử lý hình phạt liên quan đến migration down-time và SRv6 overhead, Action space cần phản ánh topology mạng.
Hỗ trợ P4 Code: Khi chỉnh sửa code P4, sử dụng chuẩn v1model.p4, tuân thủ luồng Parser -> Ingress (Bảng Match-Action đẩy nhãn) -> Egress -> Deparser. Cần chú ý lỗi Permission denied ở Linux khi mount volume Docker (bật cờ :z).

