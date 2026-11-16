#!/bin/bash
echo "=== 🚀 STARTING 3S-COM REFACTORED SYSTEM ==="

# Define paths for organization
LOG_DIR="results/logs"
TOPO_SCRIPT="infrastructure/sdn/topo_p4.py"

mkdir -p "$LOG_DIR"

cleanup() {
    echo -e "\n🧹 Cleaning up simulation environment..."
    sudo kill -9 $MININET_PID 2>/dev/null
    kill -9 $BACKEND_PID 2>/dev/null
    kill -9 $FRONTEND_PID 2>/dev/null
    sudo mn -c 2>/dev/null
    echo "✅ Safe exit."
    exit 0
}

trap cleanup SIGINT SIGTERM

echo "1️⃣  Starting Data Plane (Mininet)..."
sudo python3 "$TOPO_SCRIPT" > "$LOG_DIR/logs_mininet.txt" 2>&1 &
MININET_PID=$!
sleep 5

echo "2️⃣  Starting Control Plane Backend (FastAPI)..."
export PYTHONPATH=$PYTHONPATH:.
uvicorn src.portal.backend.app.main:app --host 0.0.0.0 --port 8000 --reload > "$LOG_DIR/logs_backend.txt" 2>&1 &
BACKEND_PID=$!
sleep 2

echo "3️⃣  Starting Frontend UI..."
cd src/portal/frontend
npm run dev > ../../../"$LOG_DIR/logs_frontend.txt" 2>&1 &
FRONTEND_PID=$!
cd ../../../

echo "==========================================="
echo "🎊 System launched successfully!"
echo "👉 Dashboard: http://localhost:5173"
echo "Logs are located in: $LOG_DIR"
echo "Press Ctrl+C to stop all processes."
echo "==========================================="

wait
