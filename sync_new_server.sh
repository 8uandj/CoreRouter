#!/bin/bash
# sync_new_server.sh — Sync code lên server mới và in runbook setup
#
# Usage:
#   ./sync_new_server.sh push          # Sync + in runbook
#   ./sync_new_server.sh runbook       # Chỉ in runbook

SERVER="112.137.129.246"
REMOTE_DIR="/home/CoreRouter"
LOCAL_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

sync_to_server() {
    echo "🚀 Syncing to $SERVER:$REMOTE_DIR ..."
    ssh "$SERVER" "sudo mkdir -p $REMOTE_DIR && sudo chown -R \$USER:\$USER $REMOTE_DIR"
    rsync -avz --progress \
        --exclude '.git' \
        --exclude 'venv' \
        --exclude '.venv' \
        --exclude '__pycache__' \
        --exclude '.ai' \
        --exclude 'node_modules/' \
        --exclude 'results/figures' \
        --exclude 'results/logs/' \
        --exclude 'results/models/*.zip' \
        --exclude 'results/models/v10_dynamic/' \
        --exclude 'results/models/v10/*ckpt*.zip' \
        "$LOCAL_DIR/" "$SERVER:$REMOTE_DIR/"
    echo "✅ Sync complete."
}

runbook() {
    cat <<'RUNBOOK'
╔══════════════════════════════════════════════════════════════╗
║      3S-COM SETUP RUNBOOK — Server MicroK8s mới             ║
╚══════════════════════════════════════════════════════════════╝

PRE-REQUISITES (cài một lần):
  sudo snap install microk8s --classic
  sudo microk8s enable registry dns storage
  sudo apt-get install -y mininet python3-pip ovs-common
  sudo pip3 install mininet
  pip install -r requirements.txt          # Python deps cho backend
  cd src/portal/frontend && npm install    # Frontend deps

══════════════════════════════════════════════════════════════
BƯỚC 1 — Import Docker images vào MicroK8s
  (Cần kết nối internet hoặc có sẵn image tar)
══════════════════════════════════════════════════════════════
  docker pull alpine:latest
  docker pull quay.io/frrouting/frr:9.1.1
  docker pull nginx:1.27-alpine
  docker pull python:3.11-alpine
  # CRITICAL: kubectl image cho Tekton tasks (dùng local, không DockerHub runtime)
  # Lưu ý: bitnami/kubectl:1.30 KHÔNG tồn tại — dùng :latest rồi tag lại
  docker pull bitnami/kubectl:latest

  for img in \
    "alpine:latest" \
    "quay.io/frrouting/frr:9.1.1" \
    "nginx:1.27-alpine" \
    "python:3.11-alpine" \
    "bitnami/kubectl:latest"; do
      docker save "$img" | sudo microk8s ctr image import -
  done

  # Tag và push lên local registry (localhost:32000)
  # LUẦT: TẤT CẢ image dùng bởi Tekton tasks và VNF pods phải
  # có trong local registry — KHÔNG pull DockerHub/internet lúc runtime.
  sudo microk8s ctr image tag docker.io/library/alpine:latest        localhost:32000/alpine:latest
  sudo microk8s ctr image tag quay.io/frrouting/frr:9.1.1           localhost:32000/frr:9.1.1
  sudo microk8s ctr image tag docker.io/library/nginx:1.27-alpine    localhost:32000/nginx:1.27-alpine
  sudo microk8s ctr image tag docker.io/library/python:3.11-alpine   localhost:32000/python:3.11-alpine
  # kubectl image: tag sang localhost:32000/kubectl:1.30 (khớp Tekton tasks)
  sudo microk8s ctr image tag docker.io/bitnami/kubectl:latest       localhost:32000/kubectl:1.30

  sudo microk8s ctr image push localhost:32000/alpine:latest
  sudo microk8s ctr image push localhost:32000/frr:9.1.1
  sudo microk8s ctr image push localhost:32000/nginx:1.27-alpine
  sudo microk8s ctr image push localhost:32000/python:3.11-alpine
  sudo microk8s ctr image push localhost:32000/kubectl:1.30

  # VERIFY: Kiểm tra tất cả image đã vào local registry chưa
  echo "=== Local Registry Image List ==="
  for img in alpine:latest frr:9.1.1 nginx:1.27-alpine python:3.11-alpine kubectl:1.30; do
    sudo microk8s ctr image ls | grep "localhost:32000/$img" && echo "✅ $img" || echo "❌ MISSING: $img"
  done

══════════════════════════════════════════════════════════════
BƯỚC 2 — Deploy Phase 1 + 2 (K8s resources + Tekton pipelines)
══════════════════════════════════════════════════════════════
  sudo microk8s kubectl apply -k infrastructure/k8s/

  # Kiểm tra:
  sudo microk8s kubectl get pods -n core-router
  sudo microk8s kubectl get pipelines -n core-router

══════════════════════════════════════════════════════════════
BƯỚC 3 — Deploy vVOC NodePort (Phase 3 bridge target)
══════════════════════════════════════════════════════════════
  sudo microk8s kubectl apply -f infrastructure/k8s/manifests/vvoc-phase3-test.yaml
  sudo microk8s kubectl rollout status deploy/vnf-voc-phase3 -n core-router

  # Verify từ host:
  curl http://$(hostname -I | awk '{print $1}'):31656/healthz
  # Kết quả mong đợi: {"status": "ok", ...}

══════════════════════════════════════════════════════════════
BƯỚC 4 — Chạy toàn hệ thống
══════════════════════════════════════════════════════════════
  # Option A: Chạy tất cả cùng lúc (Mininet + Backend + Frontend)
  source venv/bin/activate
  ./run_simulation.sh
  # Sau khi khởi động, kiểm tra log Mininet:
  # tail -f results/logs/logs_mininet.txt
  # Phase 3 Pass khi thấy: *** [Phase 3 - M1] PASSED

  # Option B: Chỉ chạy Mininet (để test Phase 3 thủ công)
  sudo python3 infrastructure/sdn/topo_p4.py
  # Sau đó trong mininet CLI:
  # mininet> h1 curl -sS http://<HOST_IP>:31656/healthz
  # mininet> vnf1 curl -sS http://<HOST_IP>:31656/healthz

══════════════════════════════════════════════════════════════
BƯỚC 5 — Test Phase 2 (Tekton migration pipeline)
══════════════════════════════════════════════════════════════
  # Deploy test VNFs trước:
  ./deploy_helper.sh frr vnf-test-01 hanoi-1
  ./deploy_helper.sh frr vnf-test-02 hanoi-2

  # Trigger migration Make-Before-Break:
  cat <<'EOF' | sudo microk8s kubectl create -f -
  apiVersion: tekton.dev/v1
  kind: PipelineRun
  metadata: { generateName: migrate-, namespace: core-router }
  spec:
    pipelineRef: { name: vnf-migrate-single }
    taskRunTemplate: { serviceAccountName: tekton-admin }
    workspaces:
    - name: ws
      volumeClaimTemplate:
        spec:
          accessModes: [ReadWriteOnce]
          resources: { requests: { storage: 50Mi } }
    params:
    - { name: oldDeployName,  value: vnf-test-01 }
    - { name: newDeployName,  value: vnf-test-01-migrated }
    - { name: fileName,       value: vnf-frr.yaml }
    - { name: targetLocation, value: hanoi-2 }
  EOF

  sudo microk8s kubectl get pipelinerun -n core-router --watch
  # Kết quả mong đợi: Succeeded

RUNBOOK
}

case "${1:-}" in
    push)
        sync_to_server
        runbook
        ;;
    runbook)
        runbook
        ;;
    *)
        echo "Usage: $0 {push|runbook}"
        echo "  push    — Sync code lên server $SERVER và in runbook"
        echo "  runbook — Chỉ in runbook setup"
        exit 1
        ;;
esac
