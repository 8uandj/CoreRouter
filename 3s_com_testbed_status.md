# 3S-COM Testbed — Master Status & Knowledge Base
# Phiên bản: 1.3 (Phase 7 - 10-node Vietnam Backbone) | Tổng kết: 7 Phase LIVE & VERIFIED

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

### Phase 5: Hybrid AI Orchestration & SRv6 Migration ✅
- **Logic điều phối Lai**: Tích hợp cơ chế **Hysteresis Gate** tự động chuyển đổi giữa Heuristic (tải thấp) và DRL (tải cao/Alert).
- **Shadow DRL Agent**: Giải quyết xung đột phiên bản Python/NumPy bằng cơ chế giả lập logic AI.
- **MBB Pipeline**: Tự động hóa chuỗi 5 bước MAKE -> VERIFY -> TRANSLATE -> STEER -> BREAK.
- **SRv6 Dynamic Translation**: Controller dịch IP động của Pod thành Segment List thời gian thực.
- **Resilience**: Bổ sung cơ chế Timeout (30s), ROLLBACK và xử lý DANGLING_VNF.

### Phase 6: Automated Benchmarking & Geo-Distributed Orchestration ✅
- **AI→K8s Node Mapping Dictionary**: JO-VPPM node 0-9 được ánh xạ cứng đến K8s labels:
  - Node 0,1,2 (HN, HP, NB) → `kubernetes.io/hostname=k8s-master`
  - Node 3,4,5 (Vinh, Hue, DN) → `kubernetes.io/hostname=worker1`
  - Node 6,7,8,9 (QN, NT, HCM, CT) → `kubernetes.io/hostname=worker2`
- **nodeSelector Injection**: Tekton task `prepare-vnf` chèn `nodeSelector` vào Deployment manifest khi pipeline chạy.
- **Data-plane Steering Latency**: Backend đo chính xác khoảng thời gian từ `/steer` đến `confirm_steer_done` bằng `time.perf_counter()`. Metric này được trả về trong response API.
- **Automated Benchmark Script**: `benchmark_phase6.py` so sánh AI vs Greedy vs Random trên 300 steps tự động. Output CSV + JSON summary.

### Phase 7: AI Orchestration & Architectural Alignment (Phase 7) 🔄
- **Kiến trúc**: Đồng bộ hóa 100% với sơ đồ "Intelligent MANO Plane".
- **Hệ thần kinh**: 
  - Triển khai **Rate-limited Orchestrator**: Di dời VNF tuần tự (Sequential MBB) để tránh "Migration Storm".
  - Khôi phục **Hysteresis Gate**: Ngưỡng 0.45/0.35 để chuyển đổi chế độ Heuristic/DRL ổn định.
- **Trạng thái AI**: 
  - Đã chuẩn hóa Observation Space ($N \times 6 + 13$).
  - Đã cấu hình backend để nạp model weights `results/models/v11/dgrl_v11_final_vietnam.zip` kèm `vec_normalize_v11_vietnam.pkl` cho mạng Việt Nam 10-node.
- **Topology**: Đã mở rộng `topology.py` hỗ trợ NSFNET và GEANT2 (Sẵn sàng cho Generalization test sau này).
- **Data Plane (10-Node Vietnam Topology)**: 
  - Nâng cấp thành công Mininet P4 từ 3-node lên 10-node.
  - Phân bổ port Thrift 19091-19100 tránh xung đột hoàn toàn với host.
  - Dynamic CPU Pinning cho phép auto-scale theo tài nguyên server thực tế (ví dụ: cấp đủ 10 cores cho s1-s10).
  - Hoàn thiện bridge L2 Transparent cho cả 10 node, vượt toàn bộ 33 Smoke Tests (test_phases.sh).

---

## ⚖️ Luật kiến trúc bất biến (Quy tắc thép)
1. **Không BSID**: Tất cả logic SRv6 dựa trên Hard MSD của phần cứng.
2. **CPU Pinning**: Bắt buộc để đảm bảo độ trễ line-rate và không bị nhiễu bởi K8s scheduler.
3. **Transparent Routing**: Tuyệt đối không dùng NAT/MASQUERADE trong chuỗi SFC.
4. **Readiness Integrity**: Kubernetes chỉ được báo Ready khi ứng dụng bên trong đã bind port nghiệp vụ.
5. **Shadow Policy**: Luôn có logic dự phòng khi mô hình AI gặp lỗi nạp nhị phân.
6. **ONAP Isolation**: Server `112.137.129.246` có ONAP; CoreRouter tuyệt đối không chỉnh/sửa/xóa/scale/restart ONAP. Worker `k8s-cluster` là worker CoreRouter và không được để pod ONAP chạy trên node này.

---

## 📂 Sơ đồ tài liệu quan trọng
- `run_phase5_demo.sh`: One-click script để chạy toàn bộ Demo Phase 5.
- `benchmark_phase6.py`: **[MỚI]** Script benchmark tự động Phase 6 (AI vs Greedy vs Random).
- `src/portal/backend/app/main.py`: Backend FastAPI điều phối trung tâm.
- `src/portal/backend/app/services/orchestration_service.py`: **[ĐÃ CẬP NHẬT]** AI→K8s mapping + Steering Latency đo.
- `infrastructure/k8s/tekton/tasks/task-prepare-vnf.yaml`: **[ĐÃ CẬP NHẬT]** Hỗ trợ nodeSelector injection qua param `nodeHostname`.
- `infrastructure/k8s/tekton/pipeline-migrate-single-vnf.yaml`: **[ĐÃ CẬP NHẬT]** Truyền `nodeHostname` xuống task.
- `src/ai/dgrl_agent.py`: DRL Agent kèm NumPy Shim và Shadow Mode.
- `infrastructure/sdn/controller.py`: SDN Controller (MBB Logic, SRv6 Steering API).
- `infrastructure/sdn/p4/srv6_basic.p4`: Logic P4 (Hard MSD Enforcement).
- `traffic_gen.py`: Script kiểm chứng Zero-Downtime (iperf3 + UDP Flood).

---

## 🧠 Hướng dẫn cho phiên chat tiếp theo
Hệ thống hiện tại đang ở trạng thái **LIVE Phase 6**. AI→K8s Mapping và Steering Latency đã được tích hợp.

## Quy trình vận hành (Operation Workflow)
1. **Khởi động Backend:** `./run_backend_docker.sh run`
2. **Khởi động SDN:** `sudo venv/bin/python3 infrastructure/sdn/topo_p4.py`
3. **Khởi động Controller:** `venv/bin/python3 infrastructure/sdn/controller.py`
4. **Khởi động Frontend:** `cd src/portal/frontend && npm run dev`
```
Log hệ thống được lưu tại `backend.log`, `sdn_controller.log`, và `results/benchmark_phase6/`.
