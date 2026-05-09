#!/bin/bash
# run_simulation.sh — Khởi động hệ thống 3S-COM
#
# Quy trình:
#   0. Dọn dẹp môi trường cũ (mn -c + veth orphans)
#   1. Data Plane: Mininet (topo_p4.py) — cần sudo
#   2. Control Plane: FastAPI backend (uvicorn)
#   3. Frontend UI: Vite dev server (npm)
#
# Requirement:
#   - Python venv đã được activate HOẶC venv/ tồn tại ở thư mục gốc
#   - MicroK8s đang chạy
#   - vVOC đã deploy (kubectl apply -f infrastructure/k8s/manifests/vvoc-phase3-test.yaml)
#
# Usage:
#   source venv/bin/activate && ./run_simulation.sh

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
LOG_DIR="$SCRIPT_DIR/results/logs"
TOPO_SCRIPT="$SCRIPT_DIR/infrastructure/sdn/topo_p4.py"

mkdir -p "$LOG_DIR"

# ─────────────────────────────────────────────
# Resolve đúng Python + uvicorn từ venv nếu có
# ─────────────────────────────────────────────
if [ -x "$SCRIPT_DIR/venv/bin/python3" ]; then
    PYTHON3="$SCRIPT_DIR/venv/bin/python3"
else
    PYTHON3="$(which python3)"
fi

if [ -x "$SCRIPT_DIR/venv/bin/uvicorn" ]; then
    UVICORN="$SCRIPT_DIR/venv/bin/uvicorn"
else
    UVICORN="$(which uvicorn)"
fi

# ─────────────────────────────────────────────
# Cleanup khi Ctrl+C
# ─────────────────────────────────────────────
cleanup() {
    echo -e "\n🧹 Cleaning up..."
    [ -n "${MININET_PID:-}" ]  && sudo kill -9 "$MININET_PID"  2>/dev/null || true
    [ -n "${BACKEND_PID:-}" ]  && kill  -9 "$BACKEND_PID"      2>/dev/null || true
    [ -n "${FRONTEND_PID:-}" ] && kill  -9 "$FRONTEND_PID"     2>/dev/null || true
    sudo bash "$SCRIPT_DIR/infrastructure/sdn/teardown_bridge.sh" 2>/dev/null || true
    echo "✅ Safe exit."
    exit 0
}
trap cleanup SIGINT SIGTERM

# ─────────────────────────────────────────────
# Phase 0: Dọn môi trường cũ
# ─────────────────────────────────────────────
echo "0️⃣  Cleaning up old environment..."
sudo bash "$SCRIPT_DIR/infrastructure/sdn/teardown_bridge.sh" 2>/dev/null || true

# ─────────────────────────────────────────────
# Phase 1 (Data Plane): Mininet
# ─────────────────────────────────────────────
echo "1️⃣  Starting Data Plane (Mininet)..."
sudo "$PYTHON3" "$TOPO_SCRIPT" > "$LOG_DIR/logs_mininet.txt" 2>&1 &
MININET_PID=$!
sleep 6  # Chờ Mininet và veth bridge khởi tạo xong

# ─────────────────────────────────────────────
# Phase 2 (Control Plane): FastAPI backend
# ─────────────────────────────────────────────
echo "2️⃣  Starting Control Plane Backend (FastAPI)..."
export PYTHONPATH="${PYTHONPATH:-}:$SCRIPT_DIR"
"$UVICORN" src.portal.backend.app.main:app \
    --host 0.0.0.0 --port 8000 --reload \
    > "$LOG_DIR/logs_backend.txt" 2>&1 &
BACKEND_PID=$!
sleep 2

# ─────────────────────────────────────────────
# Phase 3 (Frontend UI): Vite dev server
# ─────────────────────────────────────────────
echo "3️⃣  Starting Frontend UI..."
cd "$SCRIPT_DIR/src/portal/frontend"
npm run dev > "$SCRIPT_DIR/$LOG_DIR/logs_frontend.txt" 2>&1 &
FRONTEND_PID=$!
cd "$SCRIPT_DIR"

# ─────────────────────────────────────────────
echo "==========================================="
echo "🎊 System launched successfully!"
echo "👉 Dashboard:  http://localhost:5173"
echo "👉 API:        http://localhost:8000/docs"
echo "📄 Logs:       $LOG_DIR/"
echo "   Mininet  → tail -f $LOG_DIR/logs_mininet.txt"
echo "   Backend  → tail -f $LOG_DIR/logs_backend.txt"
echo "   Frontend → tail -f $LOG_DIR/logs_frontend.txt"
echo "Press Ctrl+C to stop all processes."
echo "==========================================="

wait
