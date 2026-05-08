# Quy trình Deployment

Kịch bản deploy hệ thống 3S-COM lên môi trường staging/production.

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
