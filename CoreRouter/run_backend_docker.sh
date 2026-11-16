#!/bin/bash
# run_backend_docker.sh — Chạy Backend với Python 3.11 + Model AI thật
# Dùng thay thế cho cách chạy trực tiếp bằng venv Python 3.8
#
# Usage:
#   ./run_backend_docker.sh build   # Build image lần đầu (mất 5-10 phút)
#   ./run_backend_docker.sh run     # Chạy container
#   ./run_backend_docker.sh stop    # Dừng container
#   ./run_backend_docker.sh logs    # Xem log real-time

set -e
IMAGE="3s-com-backend:py311"
CONTAINER="3s-com-backend"
PROJECT_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

build() {
    echo "🔨 Building Python 3.11 backend image..."
    docker build \
        -f "$PROJECT_ROOT/src/portal/backend/Dockerfile.py311" \
        -t "$IMAGE" \
        "$PROJECT_ROOT"
    echo "✅ Build complete: $IMAGE"
}

run_container() {
    # Dừng container cũ nếu đang chạy
    docker rm -f "$CONTAINER" 2>/dev/null || true

    echo "🚀 Starting backend container (Python 3.11 + Real AI Model)..."
    docker run -d \
        --name "$CONTAINER" \
        --network host \
        --restart unless-stopped \
        -v /var/snap/microk8s/current/credentials/client.config:/root/.kube/config:ro \
        -e JO_VPPM_ENABLE_MODEL=1 \
        -e JO_VPPM_REQUIRE_MODEL=1 \
        -e JO_VPPM_MODEL_PATH=results/models/v11/dgrl_v11_final_vietnam.zip \
        -e JO_VPPM_SCALER_PATH=results/models/v11/vec_normalize_v11_vietnam.pkl \
        -e JO_VPPM_BIGRU_MODEL_PATH="${JO_VPPM_BIGRU_MODEL_PATH:-}" \
        -e JO_VPPM_FORECAST_PPS_THRESHOLD="${JO_VPPM_FORECAST_PPS_THRESHOLD:-800}" \
        "$IMAGE"

    echo "✅ Container '$CONTAINER' started!"
    echo "   Backend API : http://localhost:8000"
    echo "   API Docs    : http://localhost:8000/docs"
    echo ""
    echo "📋 Theo dõi log: ./run_backend_docker.sh logs"
    echo "🛑 Dừng:         ./run_backend_docker.sh stop"
}

stop_container() {
    docker rm -f "$CONTAINER" 2>/dev/null && echo "🛑 Container '$CONTAINER' stopped." || echo "Container không đang chạy."
}

show_logs() {
    docker logs -f "$CONTAINER"
}

case "${1:-}" in
    build) build ;;
    run)   run_container ;;
    stop)  stop_container ;;
    logs)  show_logs ;;
    *)
        echo "Usage: $0 {build|run|stop|logs}"
        echo ""
        echo "  build — Build Docker image Python 3.11 (chạy 1 lần)"
        echo "  run   — Khởi động backend container với Real AI Model"
        echo "  stop  — Dừng container"
        echo "  logs  — Xem log real-time"
        exit 1
        ;;
esac
