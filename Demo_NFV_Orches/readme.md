# Demo NFV Orchestrator mini– CoreRouter 3S-COM

## 🎯 Mục tiêu
Minh họa khả năng điều phối vòng đời của một Virtual Network Function (VNF) trên nền Kubernetes mà không cần ONAP/OSM.  
Hệ thống sử dụng **Tekton Pipelines** làm Orchestrator, triển khai **FRRouting (vRouter)** làm VNF mẫu.

## ⚙️ Kiến trúc
- **Hạ tầng NFVI**: Kind cluster (Kubernetes trong Docker)
- **Orchestrator**: Tekton Pipelines + Dashboard
- **VNF mẫu**: FRRouting (Router ảo)
- **Pipeline**: nhiều task song song + chuỗi lifecycle (instantiate, wait, scale, observe)

## Cấu trúc thư mục:
Demo_NFV_Orches/
├── tasks/
│   ├── task-bb-sh.yaml
│   ├── task-kubectl-apply-file.yaml
│   ├── task-kubectl-get.yaml
│   ├── task-kubectl-get-all.yaml
│   ├── task-kubectl-run.yaml
│   ├── task-kubectl-scale.yaml
│   ├── task-kubectl-wait.yaml
│
├── config-frr.yaml          # ConfigMap FRR
├── ns-vnf.yaml              # Namespace vnf
├── tekton-admin.yaml        # RBAC + SA cluster-admin cho Tekton
├── vnf-frr.yaml             # Deployment + Service mẫu VNF FRR
├── vnf-inputs.yaml          # ConfigMap chứa manifest VNF để pipeline apply
│
├── pipeline-vnf-wide.yaml   # Pipeline chính (8 giai đoạn)
├── pipelinerun-vnf-wide.yaml# File chạy pipeline
│
├── kustomization.yaml       # Gom các tài nguyên cần apply
└── README.md                # Tóm tắt và hướng dẫn

## Cài môi trng trên Fedora:
# Cài Docker (Fedora)
sudo dnf install -y moby-engine docker-compose
sudo systemctl enable --now docker
sudo usermod -aG docker $USER
newgrp docker

# Cài Kind + Kubectl
curl -Lo ./kind https://kind.sigs.k8s.io/dl/v0.23.0/kind-linux-amd64
chmod +x ./kind && sudo mv ./kind /usr/local/bin/
sudo dnf install -y kubectl

# Tạo cluster Kind mini NFV
kind create cluster --name nfv-mini --config - <<'EOF'
kind: Cluster
apiVersion: kind.x-k8s.io/v1alpha4
nodes:
- role: control-plane
EOF

# Cài Tekton Pipelines + Dashboard
```bash
kubectl apply -f https://storage.googleapis.com/tekton-releases/pipeline/latest/release.yaml
kubectl apply -f https://storage.googleapis.com/tekton-releases/dashboard/latest/release.yaml
```

- Đợi Tekton sẵn sàng:
kubectl -n tekton-pipelines get deploy,po
# Tạo quyền cho Tekton
kubectl apply -f Demo_NFV_Orches/tekton-admin.yaml

## 🚀 Cách chạy

# Khởi chạy pipeline
```bash
kubectl apply -k Demo_NFV_Orches/
kubectl create -f Demo_NFV_Orches/pipelinerun-vnf-wide.yaml
kubectl -n tekton-pipelines get pipelinerun
kubectl -n tekton-pipelines get taskrun

```
# Kiểm tra vnf
``` bash
kubectl -n vnf get deploy,po,svc -o wide
kubectl -n vnf exec -it deploy/vnf-frr -- vtysh -c "show version"
```
# Tekton Dashboard (trực quan)
```bash
kubectl -n tekton-pipelines port-forward svc/tekton-dashboard 9097:9097
```

## Thu hoạch sau demo
| Hạng mục                         | Kết quả                                                                      |
| -------------------------------- | ---------------------------------------------------------------------------- |
| **Orchestrator Framework**       | Triển khai thành công Tekton Pipelines + Dashboard, thay thế Argo.           |
| **Lifecycle Automation**         | Tự động hoá triển khai – giám sát – scale – snapshot VNF.                    |
| **Cấu trúc modular**             | Pipeline được chia thành nhiều `Task` độc lập: apply, get, scale, wait, run. |
| **Tái sử dụng & mở rộng**        | Có thể thay FRR bằng bất kỳ VNF container nào khác.                          |
| **Tự động hóa toàn bộ qua YAML** | Tất cả cấu hình được quản lý dạng GitOps, chỉ cần `kubectl apply -k`.        |
| **Chuẩn hóa kiến trúc 3S-COM**   | Đây là nguyên mẫu **Orchestrator** trong kiến trúc CoreRouter 3S-COM.        |

## Các bc mở rộng
| Mục tiêu                    | Mô tả                                                                                   |
| --------------------------- | --------------------------------------------------------------------------------------- |
| **Trigger tự động**         | Dùng Tekton Trigger để khởi chạy pipeline khi có yêu cầu deploy VNF mới (qua API POST). |
| **AI-driven orchestration** | Dùng ML model (về traffic hoặc resource usage) để trigger scale out/in tự động.         |
| **Multi-VNF chain**         | Orchestrate nhiều VNF (VD: FRR + IDS + LoadBalancer).                                   |
| **Monitoring dashboard**    | Kết hợp Prometheus + Grafana để hiển thị performance metrics theo thời gian.            |
| **Service chaining (SFC)**  | Kết nối các VNF thành một chuỗi network logic.                                          |
s