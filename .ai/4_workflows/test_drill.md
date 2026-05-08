# Quy trình Test & Benchmark (Test Drill)

Đây là quy trình tiêu chuẩn để xác minh xem Agent (AI) và Hệ thống điều phối có đang hoạt động tốt hay không sau khi bạn thay đổi code.

## 1. Chạy Ablation Study (Benchmark lõi RL)
Script này giả lập 10,000 requests trên topo Vietnam Backbone để đánh giá hiệu năng của thuật toán so với các baselines.
```bash
source .venv/bin/activate
python3 src/analytics/ablation_study.py
```
**Kiểm tra output:**
- Acceptance Ratio mục tiêu **≥ 60% ở chế độ Full** đối với kịch bản tải bình thường (Vietnam Backbone, ablation chuẩn).
- **CHÚ Ý — Stress Test:** Trong các kịch bản stress (ví dụ GEANT2 stress), acceptance rate **~16.4%** kèm reject ~83.6% là **hành vi đúng của Smart Admission Control** (Little's Law) — KHÔNG báo cáo dưới dạng "lỗi acceptance thấp" và KHÔNG sửa code để ép tăng acceptance.
- **MSD Violations PHẢI BẰNG 0** nếu Action Masking hoạt động đúng.
- HTTP `409 NO_SAFE_ACTION` xuất hiện trong log là dấu hiệu Hard Constraint hoạt động, không phải bug.

## 1.1. Cấu hình PPO khi train lại (bắt buộc)
Khi cần re-train DGRL để khắc phục gradient explode / Explained Variance thấp, bắt buộc dùng đồng thời:
- `VecNormalize` (SB3) cho obs/reward.
- `n_steps = 512`, `10` parallel envs (tổng rollout batch = 5120 steps), `batch_size = 128` hoặc `256`.

## 1.2. Phạm vi test hợp lệ
Chỉ test/benchmark các thành phần thuộc Hybrid Orchestration (Heuristic, MaskablePPO, Make-Before-Break, Hysteresis Gate). KHÔNG viết test cho MORL / Pareto / Curriculum Learning — các hạng mục này thuộc Chương 6 Future Work, không nằm trong code roadmap hiện tại.

## 2. Kiểm tra log K8s Pods
Nếu đang chạy môi trường thật (có K8s), kiểm tra xem các VNF pod có đang chạy bình thường không:
```bash
kubectl get pods -A
kubectl logs -l app=corerouter-orchestrator
```
