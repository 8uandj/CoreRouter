# Quy trình Test & Benchmark (Test Drill)

Đây là quy trình tiêu chuẩn để xác minh xem Agent (AI) và Hệ thống điều phối có đang hoạt động tốt hay không sau khi bạn thay đổi code.

## 1. Chạy Ablation Study (Benchmark lõi RL)
Script này giả lập 10,000 requests trên topo Vietnam Backbone để đánh giá hiệu năng của thuật toán so với các baselines.
```bash
source .venv/bin/activate
python3 src/analytics/ablation_study.py
```
**Kiểm tra output:**
- Acceptance Ratio phải đạt ít nhất 60% ở chế độ Full.
- **MSD Violations PHẢI BẰNG 0** nếu Action Masking hoạt động đúng.

## 2. Kiểm tra log K8s Pods
Nếu đang chạy môi trường thật (có K8s), kiểm tra xem các VNF pod có đang chạy bình thường không:
```bash
kubectl get pods -A
kubectl logs -l app=corerouter-orchestrator
```
