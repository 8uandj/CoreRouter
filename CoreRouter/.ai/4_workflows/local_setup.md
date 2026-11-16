# Quy trình Cài đặt Local (Local Setup)

## 1. Môi trường Python (DRL & Core Logic)
```bash
# 1. Tạo môi trường ảo
python3 -m venv .venv
source .venv/bin/activate

# 2. Cài đặt các thư viện lõi (RL, PyTorch, Gym)
pip install -r requirements.txt
```

## 2. Khởi tạo Data Plane Giả lập (Mininet + BMv2)
- Đảm bảo hệ thống đã cài Mininet và P4 compiler (p4c).
- Chạy script tạo topology (nếu có):
```bash
sudo python3 src/infrastructure/sdn/topo_p4.py
```

## 3. Khởi tạo Control Plane (K8s)
- Cài đặt MicroK8s nếu chưa có.
```bash
sudo snap install microk8s --classic
microk8s enable dns registry
```

## 4. Nạp bộ não JO-VPPM v11 cho Backend
- Model production hiện tại của testbed Vietnam 10-node:
```bash
export JO_VPPM_ENABLE_MODEL=1
export JO_VPPM_MODEL_PATH=results/models/v11/dgrl_v11_final_vietnam.zip
export JO_VPPM_SCALER_PATH=results/models/v11/vec_normalize_v11_vietnam.pkl
```
- Chạy backend bằng Docker Python 3.11:
```bash
./run_backend_docker.sh build
./run_backend_docker.sh run
./run_backend_docker.sh logs
```

## 5. Lưu ý server runtime có ONAP
- Không thao tác vào ONAP khi dựng CoreRouter.
- Không để pod ONAP chạy trên worker `k8s-cluster` của CoreRouter.
- Chỉ kiểm tra read-only nếu cần:
```bash
sudo microk8s kubectl get pods -A -o wide | grep -i onap | grep k8s-cluster || true
```
