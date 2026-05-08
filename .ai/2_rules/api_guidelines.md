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
  - Xử lý lỗi: Trả về HTTP 409 (Conflict) với mã `NO_SAFE_ACTION` và thông báo rõ ràng khi không tìm được cặp placement/routing nào an toàn (vi phạm Hard Constraints).

## 5. Smart Admission Control — KHÔNG PHẢI BUG
- HTTP `409 NO_SAFE_ACTION` là **hành vi đúng** của **Smart Admission Control**, KHÔNG phải bug. Khi mọi node ứng viên đều vi phạm Hard Constraints (MSD/CPU/Alert), hệ thống PHẢI reject request.
- TUYỆT ĐỐI KHÔNG "fix" 409 bằng cách: bỏ/ nới lỏng Action Masking, hạ ngưỡng MSD, ép placement vào node không an toàn, hay biến `NO_SAFE_ACTION` thành 200/202.
- Trong Stress Test (ví dụ GEANT2), việc reject **83.6%** request để bảo toàn **16.4%** request được chấp nhận an toàn (tránh tràn MSD, tuân Định lý Little / Little's Law) là hành vi mong muốn của hệ thống — KHÔNG báo cáo dưới dạng "lỗi acceptance rate thấp".
- Khi gặp 409 trong log/test, hướng xử lý đúng là: kiểm tra capacity / topology / Alert Flag / phân lớp SLA, KHÔNG sửa code Orchestrator để ép qua.
