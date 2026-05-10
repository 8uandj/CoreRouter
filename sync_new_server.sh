#!/bin/bash

# Server Synchronization Script for 112.137.129.246
# This script syncs the code to the new server and provides deployment instructions.

SERVER="112.137.129.246"
REMOTE_DIR="/home/CoreRouter"
LOCAL_DIR="."

sync_to_server() {
    echo "🚀 Preparing directory on the new server ($SERVER)..."
    ssh $SERVER "sudo mkdir -p $REMOTE_DIR && sudo chown -R \$USER:\$USER $REMOTE_DIR"
    
    echo "🚀 Syncing code to the new server at $SERVER:$REMOTE_DIR..."
    
    # We use ssh with specific options to ensure it prompts for password if needed
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
        $LOCAL_DIR/ $SERVER:$REMOTE_DIR/
        
    echo "✅ Sync TO server complete."
}

runbook() {
    echo "--------------------------------------------------------"
    echo "💡 MIGRATION RUNBOOK CHO MICROK8S TRÊN SERVER MỚI"
    echo "--------------------------------------------------------"
    echo "1. SSH vào server:"
    echo "   ssh $SERVER"
    echo "   cd $REMOTE_DIR"
    echo ""
    echo "2. Import Docker Images vào MicroK8s (LỖ TRỐNG SỐ 2):"
    echo "   # Tải các image cơ bản từ Docker Hub (hoặc build custom image của bạn)"
    echo "   docker pull alpine:latest"
    echo "   docker pull quay.io/frrouting/frr:9.1.1"
    echo "   docker pull nginx:1.27-alpine"
    echo "   docker pull python:3.11-alpine"
    echo ""
    echo "   # Export từ Docker sang MicroK8s registry"
    echo "   docker save alpine:latest | microk8s ctr image import -"
    echo "   docker save quay.io/frrouting/frr:9.1.1 | microk8s ctr image import -"
    echo "   docker save nginx:1.27-alpine | microk8s ctr image import -"
    echo "   docker save python:3.11-alpine | microk8s ctr image import -"
    echo ""
    echo "   # Đẩy lên local registry của MicroK8s (localhost:32000)"
    echo "   microk8s ctr image tag docker.io/library/alpine:latest localhost:32000/alpine:latest"
    echo "   microk8s ctr image tag quay.io/frrouting/frr:9.1.1 localhost:32000/frr:9.1.1"
    echo "   microk8s ctr image tag docker.io/library/nginx:1.27-alpine localhost:32000/nginx:1.27-alpine"
    echo "   microk8s ctr image tag docker.io/library/python:3.11-alpine localhost:32000/python:3.11-alpine"
    echo "   microk8s ctr image push localhost:32000/alpine:latest"
    echo "   microk8s ctr image push localhost:32000/frr:9.1.1"
    echo "   microk8s ctr image push localhost:32000/nginx:1.27-alpine"
    echo "   microk8s ctr image push localhost:32000/python:3.11-alpine"
    echo ""
    echo "3. Triển khai Phase 1 (VNFs):"
    echo "   microk8s kubectl apply -k infrastructure/k8s"
    echo ""
    echo "4. Chạy Backend (LỖ TRỐNG SỐ 3):"
    echo "   # Đảm bảo bạn chạy uvicorn với quyền truy cập Kubeconfig của MicroK8s"
    echo "   sudo su"
    echo "   source venv/bin/activate"
    echo "   ./run_simulation.sh"
    echo "   # Backend sẽ tự động lắng nghe trên 0.0.0.0:8000 và load /var/snap/microk8s/current/credentials/client.config"
    echo "--------------------------------------------------------"
}

case "$1" in
    push)
        sync_to_server
        runbook
        ;;
    *)
        echo "Usage: $0 {push}"
        echo "  push: Sync code to server and show migration runbook"
        exit 1
        ;;
esac
