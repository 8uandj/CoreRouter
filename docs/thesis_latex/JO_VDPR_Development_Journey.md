# Lịch sử Nâng cấp & Tiến trình Tư duy Hệ thống JO-VDPR
*(Tài liệu lưu trữ hành trình tư duy và nâng cấp Hệ thống Mô phỏng JO-VDPR trong khuôn khổ Đồ án Tốt nghiệp)*

Tài liệu này không chỉ ghi nhận hình thái cuối cùng của phần mềm, mà còn là **bản tracking quá trình phản biện, đặt vấn đề và tiến hóa logic toán học** giữa người dùng và AI trong việc xây dựng hệ thống SD-WAN / SRv6 Orchestrator.

---

## 🚀 PHA 1: Khắc phục sơ hạt & Xử lý Trôi dốc Thời Gian K8s (Time-Race Condition)
**1. Đặt vấn đề đầu tiên:** 
- Giao diện Frontend (`Topology.jsx`) cực kỳ tù túng, VNF bị xếp đè lên nhau, đè lên chữ. Lỗi crash hệ thống vì thiếu cấu hình định tuyến (biến `TRAFFIC_POLICY`).
- **Nghịch lý Proactive DDoS:** Trong thực tế, chạy Tekton / K8s Pipeline để dựng 1 Pod Firewall tốn tới ~30 giây. Nhưng Front-end lại bắn giao thức tấn công ngay sau 2.2 giây khiến các gói tin "lao vào khoảng không", xóa Firewall cũng lỗi do API bị đè.

**2. Tư duy Giải quyết:**
- Fix ngay lỗi scope của Code, bổ sung tính năng *Zoom/Pan Map* để không gian mô phỏng mở rộng.
- Thay vì gửi API `onDeploy` trực tiếp vào Pipeline K8s thật (phá hỏng trải nghiệm Demo Proactive ngắn 10 giây), chúng ta **cô lập luồng Demo**. Sử dụng bộ nhớ trung gian tạm thời (`simVnfs`) để vẽ VNF Firewall ảo lên màn hình, đợi hết tấn công rồi dọn dẹp (Cleanup) hoàn hảo mà không làm lag hàng đợi Backend thật.

---

## ⚖️ PHA 2: Kiến trúc Phần Cứng (MSD) & Phôi Thai Cân Bằng Tải
**1. Câu hỏi lớn từ User:**
- *"Tại sao lại có MSD_S1 = 3 và MSD_S2 = 6? S1 thực chất là đệ tử hướng dẫn của Đại ca S2 à? Liệu trong thực tế có gói tin nào đi vượt quá năng lực thiết bị không?"*
- *"Nếu có nhiều hơn 1 VNF giống nhau, gói tin sẽ gửi vào con nào?"*

**2. Tư duy Giải quyết:**
- Xác nhận logic Ủy Quyền SDN: Nếu SFC Depth > 3, Ingress S1 sẽ từ chối gán nhãn SRv6 (Limit hardware) và gửi gói tin L3 thuần qua Core S2. Tại đây S2 với phần cứng Tofino mạnh mẽ (MSD=6) sẽ nhận trách nhiệm bắt gói tin và gán nhãn bù.
- **Nâng cấp (Feature):** Thiết kế Luồng *"Deep Inspect (Quét tất cả VNF)"* để cố tình làm tràn danh sách nhãn SID > 6 nhằm khơi mào hiệu ứng **Drop (MSD Violation)** hiển thị sự phá hủy gói tin ngay trên Tofino S2 theo đúng mô phỏng thực tế.
- **Load Balancing V1:** Lưu một `ref` tracking riêng để chia bài cho các gói tin. Đảm bảo nếu có 2 Firewall, gói thứ nhất chui vào Firewall 1, gói thứ hai chui vào Firewall 2 (Round-Robin mù).

---

## 🌍 PHA 3: Quy Hoạch Geo-Distributed Data Centers & Lỗi Đâm Xuyên Vật Lý
**1. Phát hiện Kiến trúc Sai lầm:**
- User sắc bén phát hiện: *"Các VNF đang gộp 1 búi phía trên màn hình, trên thực tế chúng được rải theo địa lý. Đồng thời gói tin bay xuyên ngang qua nhau nhìn rất vô lý!"*

**2. Tư duy Giải quyết (Massive Overhaul):**
- Đập đi xây lại 100% Canvas Topology. Bãi bỏ `VNF_BOX` nhỏ hẹp.
- Quy hoạch lại thành mạng lưới 9 Vùng Data Center đa quốc gia (Hà Nội Edge, Hải Phòng Core, New York, Paris...). 
- **Cải tiến Toán Học Mô phỏng Đồ thị (Vẽ Bezier Curve):** Không dùng các đường thẳng cắt chéo vật thể vô hồn. Sử dụng ma trận nội suy không gian Cubic Bezier `C(t)` để tính toán các điểm Control Points, bẻ cong quỹ đạo gói tin (Service Overlay Tunnels) vắt qua các Data Center một cách hoa mỹ, tuyệt đối không đâm xuyên các Node không ở trong SFC.
- **Auto Placement:** Áp dụng thuật toán tính toán Cell Grid. VNF auto tản đều 3x2 trong khung thành DC, triệt tiêu việc "chèn chữ và đè lên nhau".

---

## 🧠 PHA 4: Đỉnh Cao Tối Ưu (MDP Optimization & SDN Buffering)
**1. Nghịch lý Toán học Mạng Đặt ra:**
- *"Trong JO-VDPR, nếu điểm bắt đầu ở Hà Nội cần IDPS, nhưng Hà Nội không có mà Paris có IDPS. Chúng ta bắt gói tin lặn lội sang Paris hay Khởi tạo mới IDPS ở Hà Nội thì tốt hơn?"*
- *"Chưa kể, nếu bắt nó chờ khởi tạo mất 30s mới gửi đi thì là thảm họa!"*

**2. Tư duy Giải quyết (Implementation MDP & PPO Control plane):**
- Đây là cốt tủy của Lõi Tối Ưu trong luận văn. Thay vì điều hướng mù, hệ thống tích hợp phương trình toán học: `Min_Cost = (Dist * 1.5) + (Q_Load_Penalty * 700)`.
- Hệ thống luôn muốn Steer tới VNF có sẵn. Nhưng nếu `Min_Cost` này vượt một ngưỡng đắt đỏ ($C_{init} = 4500$, ví dụ như bay từ Châu Á sang Châu Á thì không sao, nhưng bay sang tận Paris), thì AI sẽ ra lệnh **Từ chối Steer và Chọn Scale-Out** (Đẻ VNF mới tinh tại Source DC).
- Đồng thời tích hợp thêm Q-LoadPenalty (Hàng Đợi), chứng minh rằng nếu VNF láng giềng gần thật đấy, nhưng đang quá nghẽn (Q-load cao) thì AI cũng sẽ quyết định Scale-Out tạo VNF mới để chia lửa!
- **Tính năng SDN Buffering:** Tái tạo Delay khởi tạo K8s một cách chân thực bằng cách: Giữ chân paket màu Vàng có chữ `⏳ BUFFER` ở Ingress chờ `~3 giây`, vẽ VNF dưới dạng `Pending` -> `Running`, rồi mới Release gói tin đi tiếp.

---

## 🏢 PHA 5: Rào Cản Phần Cứng (Hardware Capacity Constraints)
**1. Vấn đề Xung đột Hạ Tầng (The Final Polish):**
- User phản ánh: *"Nếu liên tục gửi gói tin tới giới hạn nghẽn, thuật toán sẽ liên tục tạo VNF mới ở Đà Nẵng, đẻ mãi thì Data Center Đà Nẵng sập chứa sao nổi? Hậu quả là VNF sinh tràn ra ngoài lưới, chạy loạn xạ!"*

**2. Tư duy Giải quyết (Geo-Scaling & Capacity Check):**
- Thết lập ngưỡng cứng `MAX_VNF_PER_DC = 6` (Mô phỏng giới hạn CPU/RAM của Blade Server trong thực tế).
- **Thuật toán thông minh:** Thay vì chỉ loay hoay trong cái ao làng (Source DC), nếu Source DC đã Full 100% dung lượng, AI lập tức chạy vòng lặp tìm Data Center Khác. 
- Nó sẽ tính **Độ trễ Dịch chuyển (Detour Latency) = D(A, B) + D(B, C)** để lựa ra Datacenter lân cận rẻ nhất còn rảnh việc, và khởi tạo dự phòng tài nguyên sang bên cụm đó! 
- Sự kiện này kết hợp chặn Race Condition (Click Injection mù quáng) đã khóa kín hoàn toàn mọi lỗ hổng logic từ Front-end tới Toán học định tuyến JO-VDPR, đưa kiến trúc mô phỏng trên nền SVG tiệm cận hoàn toàn các chuẩn Network Digital Twin của Telco hiện đại.

---
**Tổng Kết:** Nhờ sự đặt vấn đề và thử nghiệm liên tục của User theo sát Core Logic thực tế mạng, Visualizer này đã lớn lên từ một mô hình vẽ vời giao diện L3 đơn thuần, biến thái hoàn toàn thành một "Bộ Não Công Nghệ" có khả năng biểu diễn toán học Đánh đổi độ trễ, Giới hạn phần cứng, Quản lý SDN Buffering, và Dynamic Load Balancing vượt cả kỳ vọng ban đầu của hệ thống!
