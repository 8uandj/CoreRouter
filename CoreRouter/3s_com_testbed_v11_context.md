# CoreRouter Project Context — Version 11.0 (Live Cluster Edition)

## 1. Trạng thái hiện tại (Status)
- **Giai đoạn:** Phase 5 (LIVE) & Chuẩn bị Phase 6 (Benchmarking).
- **Hạ tầng:** Multi-node MicroK8s Cluster (4 nodes: 3s-com, k8s-master, worker1, worker2).
- **AI Model:** JO-VPPM v10 (GAT+PPO) - Đã kích hoạt chạy thật trong Docker Python 3.11.
- **SDN:** P4/BMv2 chạy trên node 3s-com, điều khiển bởi SDN Controller (REST API :8765).

## 2. Các thay đổi kiến trúc quan trọng (Crucial Changes)
### Backend & AI
- **Dockerization:** Backend API chạy trong container `3s-com-backend:py311` để đảm bảo tương thích thư viện ML.
- **K8s Client:** Tự động poll trạng thái Pod Ready bằng Python SDK và bypass SSL cho MicroK8s.
- **Model Path:** `results/models/v10/dgrl_v10_final_vietnam.zip`.

### SDN Controller (`infrastructure/sdn/controller.py`)
- **Strict Separation:** KHÔNG chứa logic `kubectl`. Chỉ nhận lệnh steer và nạp bảng định tuyến xuống Switch P4.
- **Make-Before-Break:** Giao thức được điều phối bởi Backend; Controller xác nhận bằng `confirm_steer_done`.

### Frontend
- **DCs Mapping:** Chỉ hiển thị 3 node thực tế (`hanoi-1`, `danang-1`, `hcm-1`).
- **Stability:** Đã thêm Guard clauses chống crash khi dữ liệu VNF từ K8s trả về không đồng nhất.

## 3. Quản lý tài nguyên (Resource Management)
- **CPU/RAM:** Dư sức chạy 10-node topology trên cụm 4 máy hiện tại.
- **Lưu ý ổ đĩa (CRITICAL):** Máy master (3s-com) rất dễ đầy disk (do ONAP và Docker layers). 
    - Lệnh dọn dẹp: `docker builder prune -af` và `sudo swapoff /swapfile2 && sudo rm /swapfile2`.
    - Duy trì ít nhất 10GB trống để K8s không bị treo.

## 4. Quy trình vận hành (Operation Workflow)
1. **Khởi động Backend:** `./run_backend_docker.sh run`
2. **Khởi động SDN:** `sudo venv/bin/python3 infrastructure/sdn/topo_p4.py`
3. **Khởi động Controller:** `venv/bin/python3 infrastructure/sdn/controller.py`
4. **Khởi động Frontend:** `cd src/portal/frontend && npm run dev`

## 5. Kế hoạch tiếp theo (Next Steps)
- Mở rộng cấu hình `topo_p4.py` lên 10 switches.
- Cập nhật kustomize manifests để triển khai VNF lên các worker nodes mới bằng `nodeSelector`.
- Chạy benchmark tự động trên mô hình 10 node.
