KHUNG KỊCH BẢN BENCHMARK TOÀN DIỆN (5 SCENARIOS)
1. Scenario 1: Normal Load (Bài test "Sự cẩn trọng thái quá")
Mục tiêu: Đo lường hành vi của AI trong điều kiện mạng lưới thảnh thơi (Business-as-usual).
Thiết lập (Config): Tốc độ đến (Arrival rate) thấp = 0.2 req/step. Vòng đời VNF (TTL) ngắn = 10 - 50 steps. Traffic phân phối đều.
Phản ứng kỳ vọng:
Greedy & Decoupled AI: Đạt Acceptance Rate khổng lồ (~95-100%), độ trễ cực thấp (~0.11ms) vì chúng thiển cận, cứ nhét VNF ngay tại Ingress Node
.
JO-VPPM: Acceptance Rate thấp hơn một chút (~85-89%), độ trễ cao hơn (3-5ms)
.
Lý luận bảo vệ (Vũ khí): Đừng giấu số liệu này! Hãy dùng nó để giới thiệu khái niệm Over-Conservatism (Cẩn trọng thái quá). JO-VPPM chủ động rải rác VNF ra xa để dự phòng tải, hy sinh 5% lợi ích ngắn hạn để đổi lấy sự sống còn dài hạn
. Đây là tư duy của hệ thống Carrier-Grade thực thụ.
2. Scenario 2: The "Elephant" Heavy-Tail (Bài test "Xếp ba lô")
Mục tiêu: Chứng minh sức mạnh của hàm phần thưởng tỷ lệ (Proportional Knapsack Reward)
.
Thiết lập: Tốc độ đến trung bình = 0.5 req/step. Áp dụng phân phối Pareto (Heavy-tail). 20% luồng request là "Voi" (Video/Data băng thông cực lớn, ngốn 5-10x CPU thông thường).
Phản ứng kỳ vọng:
Greedy: Chết sặc. Nó nhét các luồng "Voi" vào các Edge DC nhỏ (như Ninh Bình, Huế) cho đến khi sập phần cứng, sau đó từ chối toàn bộ request phía sau
.
JO-VPPM: Tỏa sáng rực rỡ. Nhờ GAT, AI nhận thức được sức mạnh của Core DC (Hà Nội, ĐN, HCM với CPU 150-200)
. Nó chủ động đẩy luồng Voi về Core DC và nhường Edge DC cho các luồng nhỏ (IoT/URLLC)
.
3. Scenario 3: Topology & Physics Stress (Bài test "Giới hạn SRv6")
Mục tiêu: Minh chứng thuật toán tuân thủ định luật vật lý mạng (Path-Aware MSD = Base + Hops)
.
Thiết lập: Sinh ra các request có Source và Target cách xa nhau (VD: Hà Nội -> Cần Thơ). Đặt Ingress Router tại các Edge DC có MSD Limit = 3-5 (nơi không thể dán nhiều nhãn SRv6)
.
Phản ứng kỳ vọng:
Decoupled AI: Tách biệt định tuyến và tính toán nên sẽ chọn Placement ở xa, sinh ra đường đi dài. Khi áp vào vật lý (MSD Hops > 5), gói tin bị Reject thẳng tay ở Data Plane
.
JO-VPPM: Nhờ bị phạt bạo lực -50 điểm lúc huấn luyện
, AI biết rằng nếu Ingress ở Edge DC, nó bắt buộc phải đặt VNF ngay tại chỗ hoặc cách tối đa 1-2 hop.
Lý luận bảo vệ: Đây là minh chứng thép cho tính năng Hardware-Awareness (Nhận thức phần cứng). JO-VPPM duy trì 0% MSD Violation, trong khi các AI truyền thống vi phạm từ 30% - 60%
.
4. Scenario 4: DDoS & Make-Before-Break (Bài test "Sơ tán chủ động")
Mục tiêu: Thể hiện sức mạnh của Hybrid Orchestrator và Proactive Migration.
Thiết lập: Bơm 1 cú Surge UDP cực lớn vào Core Hà Nội. Trigger module Bi-GRU bật cờ Alert = 1 tại node này
.
Phản ứng kỳ vọng:
Hệ thống chuyển từ Heuristic sang DRL. JO-VPPM đọc được Alert = 1.
Để né hình phạt cực nặng (-50), AI từ chối đặt VNF mới vào Hà Nội, và kích hoạt luồng Migrate-Single-VNF (Make-Before-Break) đưa các VNF quan trọng sang Hải Phòng/Đà Nẵng
.
Lý luận bảo vệ: Hệ thống chứng minh khả năng "Chống sụp đổ dây chuyền". Thà chịu phí bẻ luồng (Switching Cost = -3) còn hơn để node chết, qua đó thực thi cam kết Zero-Downtime
.
5. Scenario 5: The "Chaos" (Sàn đấu Sinh tử)
Mục tiêu: Kịch bản "Chạy tất cả lẫn lộn" để chốt hạ hiệu năng tổng thể của mô hình.
Thiết lập: Trạng thái bão hòa (Saturation Regime). Arrival rate = 1.0 (nhồi nhét liên tục). TTL = 100 - 500 (giữ tài nguyên lâu). Trộn lẫn Elephant Flows, URLLC traffic, và bật Alert ngẫu nhiên trên bản đồ
.
Phản ứng kỳ vọng:
Traditional Baseline: Tê liệt hoàn toàn. Acceptance Rate tụt xuống dưới 7% do tắc nghẽn cổ chai cục bộ và cạn kiệt MSD
.
JO-VPPM: Đạt Acceptance Rate ~15% - 20%. Mặc dù con số tuyệt đối có vẻ thấp, nhưng nó đại diện cho việc phục vụ thành công số lượng khách hàng gấp 2.5 lần (+150%) so với baseline trong cùng một điều kiện hạ tầng hữu hạn, đồng thời giữ độ trễ trung bình ở mức thấp (sub-1.5ms)
.