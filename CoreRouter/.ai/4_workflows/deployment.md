# Quy trình Deployment

Kịch bản deploy hệ thống 3S-COM lên môi trường staging/production.

## 0. Guardrail bắt buộc: ONAP isolation
- Server runtime `112.137.129.246` có cài ONAP. Mọi thao tác deploy của CoreRouter phải tránh hoàn toàn namespace/resource ONAP.
- KHÔNG chạy lệnh `kubectl` diện rộng kiểu `kubectl delete pods -A`, `kubectl apply -f /path/to/all`, hoặc label/taint node nếu mục tiêu có thể ảnh hưởng ONAP.
- Worker `k8s-cluster` là worker của CoreRouter; không được để pod ONAP chạy trên node này. Chỉ được kiểm tra read-only:
```bash
sudo microk8s kubectl get pods -A -o wide | grep -i onap | grep k8s-cluster || true
```
Nếu có kết quả, dừng thao tác và báo cáo; không tự delete/evict pod ONAP.

## 1. Build K8s Images
- Nếu có chỉnh sửa logic Orchestrator, build lại image và push lên local registry của MicroK8s:
```bash
docker build -t localhost:32000/corerouter-orchestrator:latest .
docker push localhost:32000/corerouter-orchestrator:latest
```

## 2. Nạp luật P4 xuống Switch
- Biên dịch mã nguồn P4 sang file JSON cho BMv2:
```bash
p4c-bm2-ss --p4v 16 src/infrastructure/sdn/main.p4 -o build/main.json
```
- Sử dụng `simple_switch_CLI` hoặc Controller script để nạp các luật push/pop SID ban đầu.

## 3. Deploy Orchestrator
- Apply K8s manifests:
```bash
kubectl apply -f src/infrastructure/k8s/
```
