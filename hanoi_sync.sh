#!/bin/bash

# Hanoi Server Synchronization & Benchmark Automation
# This script helps sync code to the remote server and pull results back.

SERVER="hanoi-server"
REMOTE_DIR="~/CoreRouter"
LOCAL_DIR="."

# 1. Sync local code to server
sync_to_server() {
    echo "🚀 Syncing code, models, and data to $SERVER..."
    rsync -avz --progress \
        --exclude '.git' \
        --exclude 'venv' \
        --exclude '.venv' \
        --exclude '__pycache__' \
        --exclude 'results/figures' \
        --exclude '.ai' \
        $LOCAL_DIR/ $SERVER:$REMOTE_DIR/
    echo "✅ Sync TO server complete."
}

# 2. Pull results from server
pull_results() {
    echo "📥 Pulling ALL benchmark figures from $SERVER..."
    mkdir -p results/figures
    rsync -avz --progress \
        $SERVER:$REMOTE_DIR/results/figures/ \
        results/figures/
    echo "✅ Pull FROM server complete. All versions are synced in results/figures/"
}

# 3. Check server configuration
check_server() {
    echo "🔍 Checking configuration on $SERVER..."
    ssh $SERVER "echo '--- CPU Info ---' && lscpu | grep 'Model name' && \
                echo '--- RAM Info ---' && free -h && \
                echo '--- GPU Info ---' && (nvidia-smi || echo 'No NVIDIA GPU found') && \
                echo '--- PyTorch GPU Check ---' && \
                (if [ -f $REMOTE_DIR/venv/bin/python3 ]; then $REMOTE_DIR/venv/bin/python3 -c \"import torch; print('PyTorch (venv) CUDA Available:', torch.cuda.is_available())\"; \
                 else python3 -c \"import torch; print('PyTorch (system) CUDA Available:', torch.cuda.is_available())\" 2>/dev/null || echo 'Python/Torch not ready'; fi)"
}

# 4. Remote execution hint
run_hint() {
    echo "--------------------------------------------------------"
    echo "💡 To run the FULL benchmark on hanoi-server, run:"
    echo "   ssh $SERVER 'cd $REMOTE_DIR && venv/bin/python3 src/analytics/benchmark_v10_final.py --topology all --scenario all --steps 10000'"
    echo ""
    echo "🔔 Tip: Use 'tmux' or 'screen' on the server for long runs."
    echo "--------------------------------------------------------"
}

case "$1" in
    push)
        sync_to_server
        run_hint
        ;;
    pull)
        pull_results
        ;;
    check)
        check_server
        ;;
    *)
        echo "Usage: $0 {push|pull|check}"
        echo "  push: Sync code to server and show run command"
        echo "  pull: Download results from server"
        echo "  check: Check remote server CPU/RAM/GPU status"
        exit 1
        ;;
esac
