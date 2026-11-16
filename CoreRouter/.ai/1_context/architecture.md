# Kiến trúc hệ thống và Luồng dữ liệu (Data Flow)

Dự án áp dụng chuẩn kiến trúc NFV-MANO (ETSI) kết hợp với SDN, tách bạch rõ ràng Control Plane và Data Plane. Không được phá vỡ sự phân tách này khi chỉnh sửa code.

## 1. Sơ đồ luồng (Pipeline)

Hệ thống hoạt động theo vòng lặp khép kín (Closed-Loop) gồm 4 giai đoạn:

1. **Thu thập dữ liệu (Telemetry Extraction):** 
   - Lấy thông tin trạng thái mạng từ Data Plane với Observation Space là $N \times 6 + 13$. State của mỗi node: `[CPU_util, RAM_util, MSD_used, MSD_free, Alert_Flag, Geo_Latency]`.
2. **Dự báo (Bi-GRU Forecasting):**
   - Đưa dữ liệu chuỗi thời gian (traffic log) qua mô hình Bi-GRU để dự đoán xem luồng dữ liệu sắp tới là "Chuột" (Mouse) hay "Voi" (Elephant). 
   - Bật cờ `Alert = 1` tại node sắp nghẽn. DRL Agent sẽ bị trừ điểm nặng (-50) nếu cố tình nạp VNF vào node này.
3. **Điều phối AI (Hybrid Orchestration - RuleDRL):**
   Hệ thống sử dụng 3 module cốt lõi trong `src/ai/` và `src/core/` để ra quyết định:
   - **`src/core/state_manager.py` (Bộ não trạng thái):** Một Singleton an toàn luồng (Thread-safe) lưu trữ trạng thái CPU/RAM/MSD thời gian thực. Module này sở hữu hàm `choose_mode()` đóng vai trò là "Cổng trễ" (Hysteresis Gate) quyết định việc chuyển đổi giữa Heuristic và DRL (AI_ENGAGE_THRESHOLD = 0.45, AI_RELEASE_THRESHOLD = 0.35). Nó cũng chuẩn bị Observation Space ($N \times 6 + 13$) và Action Masking.
   - **`src/ai/heuristic.py` (Nhánh Rule-based):** Xử lý trong chế độ tải bình thường (Decoupled Action). Thuật toán tối ưu hóa độ trễ (chọn node rảnh nhất + route ngắn nhất 1 hop). Nếu vi phạm Hard Constraint, module này sẽ ném `HardConstraintError` để ép API chuyển quyền cho nhánh AI.
   - **`src/ai/dgrl_agent.py` (Nhánh AI cốt lõi):** Adapter nạp model MaskablePPO (`v10_final`). Khi tải mạng căng thẳng (Stress Load) hoặc có cờ cảnh báo bão (Alert Flag), agent này sẽ tiếp quản để tính toán cặp quyết định nguyên tử `[v_place, v_route]` giúp chống nghẽn MSD. Nó cũng đi kèm cơ chế `Resilience Safe Action` dự phòng nếu ML model bị crash.
4. **Thực thi (Stateless Enforcement):**
   - K8s khởi tạo/terminate các VNF (Pod).
   - SDN Controller nạp luật xuống các P4 Switch qua P4Runtime/CLI, chèn chuỗi SID SRv6 vào gói tin để bẻ lái luồng (Traffic Steering).

## 2. Lưu ý về Kiến trúc Data Plane
- **Không giữ trạng thái (Stateless):** Các Switch trung gian chỉ đọc header SRv6 và forward theo chỉ dẫn, không lưu trữ thông tin luồng.
- **Make-Before-Break (Quy trình Di dời VNF):** Quy trình 3 bước đảm bảo Zero-Downtime:
  1. *Make*: Khởi tạo bản sao VNF tại Node an toàn mới.
  2. *Steer*: Bẻ luồng dữ liệu thông qua việc rewrite luật SRv6 ở Ingress (Switching Cost = -3.0).
  3. *Break*: Xóa VNF cũ giải phóng tài nguyên.
- **Mô hình Trễ 4 thành phần (Physics-Aware Latency):** Không dùng hằng số giả định. Tính toán dựa trên độ trễ quang học ($D_{prop}$, dùng công thức Haversine), trễ xử lý nhãn ($D_{srv6}$ = $0.05ms \times$ Số lượng SID), và trễ hàng đợi ($D_{queue}$, mô hình M/G/1 Pollaczek-Khinchine cho bursty traffic $C_v^2 \approx 3.0$).
