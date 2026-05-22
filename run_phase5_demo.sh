#!/bin/bash

# =================================================================
# 3S-COM Phase 5: Hybrid AI-SRv6 Orchestration Auto-Demo Script
# =================================================================

# 1. Cấu hình môi trường
export JO_VPPM_ENABLE_MODEL=1
export JO_VPPM_MODEL_PATH=results/models/v11/dgrl_v11_final_vietnam.zip
export JO_VPPM_SCALER_PATH=results/models/v11/vec_normalize_v11_vietnam.pkl
export PYTHONPATH=$PYTHONPATH:.
VENV_PYTHON="./venv/bin/python3"

echo "=== [1/5] Cleaning up old processes ==="
sudo fuser -k 8765/tcp 2>/dev/null
sudo fuser -k 8000/tcp 2>/dev/null
sleep 2

# Hàm dọn dẹp khi thoát
cleanup() {
    echo -e "\n\n=== Stopping Demo Processes ==="
    sudo kill $CONTROLLER_PID $BACKEND_PID 2>/dev/null
    exit
}
trap cleanup SIGINT

echo "=== [2/5] Starting SDN Controller (Port 8765) ==="
$VENV_PYTHON infrastructure/sdn/controller.py --api-port 8765 > sdn_controller.log 2>&1 &
CONTROLLER_PID=$!

echo "=== [3/5] Starting AI Backend (Port 8000) ==="
$VENV_PYTHON src/portal/backend/app/main.py > backend.log 2>&1 &
BACKEND_PID=$!

# Đợi port sẵn sàng
echo -n "Waiting for services to be ready..."
while ! nc -z localhost 8765; do sleep 1; echo -n "."; done
while ! nc -z localhost 8000; do sleep 1; echo -n "."; done
echo -e " READY!\n"

echo "=== [4/5] Running Phase 5 Traffic Scenario ==="
echo "Monitoring logs in real-time... (Press Ctrl+C to stop)"
echo "------------------------------------------------------"

# Chạy Traffic Gen và hiển thị output
sudo $VENV_PYTHON traffic_gen.py

echo "------------------------------------------------------"
echo "=== [5/5] Demo Finished ==="
echo "Check 'sdn_controller.log' and 'backend.log' for detailed Phase 5 traces."

# Giữ script chạy để xem log nếu cần, nhấn Ctrl+C để dọn dẹp
wait
