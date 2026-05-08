# Quy tắc Giao tiếp API & Bên ngoài (API Guidelines)

## 1. Giao tiếp với SDN Controller & P4 Switch
- **Connection Timeout:** P4Runtime / BMv2 (Thường chạy giả lập qua Mininet) có thể bị nghẽn nếu nhận quá nhiều Flow Rules trong một giây. LUÔN thiết lập cơ chế Retry (Exponential Backoff) và Timeout (VD: 2000ms) khi gọi lệnh gán nhãn SRv6.
- **Thao tác Không đồng bộ (Async):** Đối với việc scale-out nhiều VNF cùng lúc, hãy đẩy các lệnh khởi tạo Pod (K8s) vào message queue hoặc chạy async thay vì blocking luồng Orchestrator chính.

## 2. Bảo mật & Logging
- **Tuyệt đối không log Payload:** Trong Data Plane, chỉ thao tác với IPv6/SRv6 Header. KHÔNG log hoặc đọc nội dung Payload của gói tin để đảm bảo quyền riêng tư và tránh bị chậm mạng.
- **Không log Tokens/Secrets:** Nếu code có truy cập vào K8s API server, tuyệt đối không in (print/log) các Token truy cập, Kubeconfig, hay SSH keys ra console.

## 3. Giao tiếp với Frontend UI
- Portal Dashboard lấy dữ liệu bằng các REST API (hoặc WebSocket).
- Định dạng chuẩn trả về: JSON.
- LUÔN chứa các key cơ bản: `status`, `message`, và `data`. Nếu lỗi, `status` là `error` kèm `code`.

## 4. API Điều phối (Hybrid Orchestration)
- Endpoint chính: `POST /orchestrate`
- Dữ liệu trả về từ API này phải tuân thủ nghiêm ngặt để frontend có thể visualize:
  - `placement_node`, `routing_node`: Thông tin node.
  - `srv6_segment_list`: Danh sách các SIDs.
  - `method_used`: Tên phương pháp (ví dụ: "Heuristic (Latency Optimized)" hoặc "JO-VPPM AI (Resilience Optimized)").
  - `hybrid_branch`: Nhánh xử lý (`heuristic` hoặc `drl`).
  - `make_before_break`: Cờ (boolean) báo hiệu xem migration có được trigger không.
  - Xử lý lỗi: Trả về HTTP 409 (Conflict) với thông báo rõ ràng khi không tìm được cặp placement/routing nào an toàn (vi phạm Hard Constraints).
