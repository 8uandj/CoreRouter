# 3S-COM Testbed — Master Status & Knowledge Base
# Phiên bản: 1.0 (Hoàn tất Phase 4) | Tổng kết: 26/26 Test Cases PASS

## 📋 Tổng quan dự án (Architectural Context)
Hệ thống 3S-COM là Testbed nghiên cứu về **SRv6 Service Function Chaining (SFC)** với khả năng **Hardware-Awareness** (nhận biết ràng buộc phần cứng MSD). Hệ thống kết hợp Mininet (P4 Data Plane) và Kubernetes (VNF Orchestration).

---

## 🚀 Lịch sử hoàn thiện các Phase

### Phase 1: K8s Infrastructure & VNF Foundation ✅
- **Hạ tầng**: Triển khai trên MicroK8s, namespace `core-router`.
- **Registry**: Local Registry tại `localhost:32000` (Loại bỏ phụ thuộc DockerHub lúc runtime).
- **VNF Core**: Xây dựng image vVOC (Virtual Voice over Cloud) chạy trên Alpine Python 3.11.
- **Security**: Phân quyền RBAC cho Tekton ServiceAccount để thao tác Deployment/Pods.

### Phase 2: Tekton Orchestration (Make-Before-Break) ✅
- **Pipeline logic**: Hiện thực hóa luồng **Make-Before-Break**:
  1. **Make**: Deploy VNF mới.
  2. **Wait**: Đợi Readiness Probe thực thụ (HTTP port 8000).
  3. **Steer**: SDN Controller bẻ luồng (Phase 4).
  4. **Break**: Xoá VNF cũ sau khi nhận `confirm_steer_done`.
- **Tasks**: Bộ 7 Tekton Tasks chuẩn hóa (kubectl-apply, scale, delete, get, v.v.)

### Phase 3: Mininet ↔ K8s Connectivity ✅
- **Bridge**: Thiết lập `br-k8s-mn` kết nối Mininet hosts và Kubernetes NodePort.
- **L2 Transparency**: Loại bỏ hoàn toàn `iptables MASQUERADE`. 
- **SFC Integrity**: Sử dụng per-host return routes để đảm bảo VNF nhìn thấy IP gốc của host (phục vụ phân tích DDoS/SFC).

### Phase 4: P4 SRv6 Data Plane (Current Stage) ✅
- **P4 Program**: `srv6_basic.p4` hiện thực hóa SRv6 Forwarding.
  - **Quy tắc #1 (Hard MSD)**: Enforce `MAX_SID_DEPTH` ngay tại Parser. Vượt ngưỡng = DROP.
  - **Visibility**: Thêm `msd_violation_counter` và API `/stats/msd_drops` để đo đạc gói tin rơi.
- **Hardware Awareness**: 
  - **Quy tắc #2 (CPU Pinning)**: Mỗi BMv2 switch được trói vào 1 CPU vật lý (`--cpuset-cpus`).
- **SDN Controller**: 
  - **Quy tắc #3 (Safe Steer)**: Controller chỉ bẻ luồng sau khi xác nhận Pod K8s đã `Ready`.
  - REST API listening tại `:8765`.

---

## ⚖️ Luật kiến trúc bất biến (Quy tắc thép)
1. **Không BSID**: Tất cả logic SRv6 dựa trên Hard MSD của phần cứng.
2. **CPU Pinning**: Bắt buộc để đảm bảo độ trễ line-rate và không bị nhiễu bởi K8s scheduler.
3. **Transparent Routing**: Tuyệt đối không dùng NAT/MASQUERADE trong chuỗi SFC.
4. **Readiness Integrity**: Kubernetes chỉ được báo Ready khi ứng dụng bên trong đã bind port nghiệp vụ.

---

## 📂 Sơ đồ tài liệu quan trọng
- `infrastructure/sdn/p4/srv6_basic.p4`: Logic P4 (Parser, Counters, Tables).
- `infrastructure/sdn/controller.py`: SDN Controller (MBB Logic, REST API).
- `infrastructure/sdn/p4_switch.py`: Switch Manager (Docker, CPU Pinning).
- `infrastructure/sdn/topo_p4.py`: Main topology entry point.
- `test/test_phases.sh`: Smoke test suite cho cả 4 Phase.

---

## 🧠 Hướng dẫn cho phiên chat tiếp theo
Hệ thống hiện tại đang ở trạng thái **LIVE Phase 4**. Mọi hạ tầng Data Plane và Orchestration đã sẵn sàng. 
**Nhiệm vụ tiếp theo (Phase 5)**: Tích hợp **Backend AI** để tối ưu hóa việc chọn đường (Path Selection) dựa trên Action Masking (không bao giờ sinh SID List > MSD) và gọi API `/steer` để Migration VNF.
