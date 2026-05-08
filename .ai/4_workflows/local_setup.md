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
