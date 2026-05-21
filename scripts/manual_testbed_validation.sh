#!/usr/bin/env bash
# Manual testbed validation helper for CoreRouter.
#
# This script intentionally keeps operations explicit so it can be run by hand
# on the server terminal while watching backend/frontend/controller/Mininet logs.

set -euo pipefail

ROOT="${CORE_ROUTER_ROOT:-/home/CoreRouter}"
if [[ ! -d "$ROOT" ]]; then
  ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
fi

BACKEND_URL="${BACKEND_URL:-http://127.0.0.1:8000}"
CONTROLLER_URL="${CONTROLLER_URL:-http://127.0.0.1:8765}"
NS="${CORE_ROUTER_NAMESPACE:-core-router}"
TEKTON_NS="${TEKTON_NAMESPACE:-tekton-pipelines}"
TEKTON_DASHBOARD_PORT="${TEKTON_DASHBOARD_PORT:-9097}"
TEKTON_DASHBOARD_ADDRESS="${TEKTON_DASHBOARD_ADDRESS:-0.0.0.0}"
VENV_PY="${VENV_PY:-$ROOT/venv/bin/python3}"
if [[ ! -x "$VENV_PY" ]]; then
  VENV_PY="python3"
fi

cd "$ROOT"

usage() {
  cat <<USAGE
Usage: $0 <command>

Commands:
  tmux-guide       Print tmux commands for backend, frontend, Mininet+controller.
  start-tmux       Create a tmux session with panes for logs and Mininet.
  start-mininet    Keep only Mininet + SDN Controller running in tmux.
  attach-mininet   Attach to the Mininet tmux session.
  start-tekton-web Keep Tekton Dashboard web running in tmux.
  attach-tekton-web Attach to the Tekton Dashboard tmux session.
  logs-guide       Print backend/frontend log commands.
  health           Check backend, orchestration state, controller, and K8s pods.
  telemetry        Inject sample telemetry + PPS forecast alert.
  orchestrate      Call /api/orchestrate with a small Data request and PPS.
  benchmark        Run a small benchmark: benchmark_phase6.py --steps 30.
  phase5           Run backend/frontend smoke tests.
  phase7           Run AI orchestration smoke tests.
  logs-backend     Follow backend container logs.
  state            Print current orchestration state JSON.
  bigru-info       Explain Bi-GRU integration and checkpoint env.

Environment overrides:
  CORE_ROUTER_ROOT=/home/CoreRouter
  BACKEND_URL=http://127.0.0.1:8000
  CONTROLLER_URL=http://127.0.0.1:8765
  JO_VPPM_BIGRU_MODEL_PATH=/home/CoreRouter/results/models/bigru/bigru_forecaster.pt
  TEKTON_DASHBOARD_ADDRESS=0.0.0.0
  TEKTON_DASHBOARD_PORT=9097
USAGE
}

json_pretty() {
  if command -v python3 >/dev/null 2>&1; then
    python3 -m json.tool
  else
    cat
  fi
}

logs_guide() {
  cat <<'GUIDE'
Backend logs:
  cd /home/CoreRouter
  ./run_backend_docker.sh logs

Frontend logs:
  If frontend is running inside tmux:
    tmux ls
    tmux attach -t <frontend-session-name>

  If frontend was started directly in a terminal, its stdout only exists in that terminal.
  To make future frontend logs attachable, restart it in tmux:
    tmux new -s corerouter-fe
    cd /home/CoreRouter/src/portal/frontend
    npm run dev -- --host 0.0.0.0

Mininet/controller logs:
  tmux attach -t mininet-core

Tekton Dashboard logs:
  tmux attach -t tekton-web
GUIDE
}

tmux_guide() {
  cat <<'GUIDE'
Run these on the server:

  cd /home/CoreRouter
  tmux new -s corerouter

Pane 1: backend logs
  ./run_backend_docker.sh logs

Pane 2: frontend logs
  cd /home/CoreRouter/src/portal/frontend
  npm run dev -- --host 0.0.0.0

Pane 3: Mininet + SDN Controller
  cd /home/CoreRouter
  sudo /home/CoreRouter/venv/bin/python3 infrastructure/sdn/topo_p4.py --p4

Notes:
  - Keep the Mininet pane open; the controller REST API on :8765 is started by topo_p4.py --p4.
  - Detach tmux with Ctrl-b d.
  - Re-attach with: tmux attach -t corerouter
GUIDE
}

start_tmux() {
  command -v tmux >/dev/null 2>&1 || {
    echo "tmux is not installed. Use: sudo apt-get install -y tmux" >&2
    exit 1
  }

  if tmux has-session -t corerouter 2>/dev/null; then
    echo "tmux session 'corerouter' already exists. Attach with:"
    echo "  tmux attach -t corerouter"
    exit 0
  fi

  tmux new-session -d -s corerouter -c "$ROOT" "./run_backend_docker.sh logs"
  tmux split-window -h -t corerouter:0 -c "$ROOT/src/portal/frontend" "npm run dev -- --host 0.0.0.0"
  tmux split-window -v -t corerouter:0.1 -c "$ROOT" "sudo $VENV_PY infrastructure/sdn/topo_p4.py --p4"
  tmux select-pane -t corerouter:0.0
  echo "Created tmux session 'corerouter'. Attach with:"
  echo "  tmux attach -t corerouter"
}

start_mininet() {
  command -v tmux >/dev/null 2>&1 || {
    echo "tmux is not installed. Use: sudo apt-get install -y tmux" >&2
    exit 1
  }

  if tmux has-session -t mininet-core 2>/dev/null; then
    echo "tmux session 'mininet-core' already exists. Attach with:"
    echo "  tmux attach -t mininet-core"
    exit 0
  fi

  tmux new-session -d -s mininet-core -c "$ROOT" "sudo $VENV_PY infrastructure/sdn/topo_p4.py --p4"
  echo "Created tmux session 'mininet-core'. Attach with:"
  echo "  tmux attach -t mininet-core"
  echo
  echo "Controller REST API should be available at: $CONTROLLER_URL"
}

attach_mininet() {
  tmux attach -t mininet-core
}

start_tekton_web() {
  command -v tmux >/dev/null 2>&1 || {
    echo "tmux is not installed. Use: sudo apt-get install -y tmux" >&2
    exit 1
  }

  if tmux has-session -t tekton-web 2>/dev/null; then
    echo "tmux session 'tekton-web' already exists. Attach with:"
    echo "  tmux attach -t tekton-web"
    exit 0
  fi

  tmux new-session -d -s tekton-web -c "$ROOT" \
    "sudo microk8s kubectl -n $TEKTON_NS port-forward --address $TEKTON_DASHBOARD_ADDRESS svc/tekton-dashboard $TEKTON_DASHBOARD_PORT:9097"
  echo "Created tmux session 'tekton-web'. Attach with:"
  echo "  tmux attach -t tekton-web"
  echo
  echo "Tekton Dashboard URL:"
  echo "  http://127.0.0.1:$TEKTON_DASHBOARD_PORT"
  if [[ "$TEKTON_DASHBOARD_ADDRESS" == "0.0.0.0" ]]; then
    echo "  http://<server-ip>:$TEKTON_DASHBOARD_PORT"
  fi
}

attach_tekton_web() {
  tmux attach -t tekton-web
}

health() {
  echo "== Backend health =="
  curl -sS --max-time 5 "$BACKEND_URL/api/health"; echo

  echo
  echo "== Orchestration state =="
  curl -sS --max-time 5 "$BACKEND_URL/api/orchestrate/state" | head -c 1000; echo

  echo
  echo "== SDN Controller health =="
  if curl -sS --max-time 3 "$CONTROLLER_URL/health"; then
    echo
  else
    echo "WARN: controller unavailable. Start Mininet with: sudo $VENV_PY infrastructure/sdn/topo_p4.py --p4" >&2
  fi

  echo
  echo "== K8s pods =="
  sudo microk8s kubectl get pods -n "$NS"
}

telemetry() {
  curl -sS --max-time 5 -X POST "$BACKEND_URL/api/orchestrate/reset" >/dev/null
  curl -sS --max-time 5 -X POST "$BACKEND_URL/api/orchestrate/telemetry" \
    -H "Content-Type: application/json" \
    -d '{
      "samples": [
        {"node_id": 0, "cpu_util": 0.82, "ram_util": 0.40, "msd_util": 0.30, "pps": 300},
        {"node_id": 0, "pps": 950}
      ]
    }' | json_pretty
}

orchestrate() {
  curl -sS --max-time 10 -X POST "$BACKEND_URL/api/orchestrate" \
    -H "Content-Type: application/json" \
    -d '{
      "cpu_req": 10,
      "ram_req": 5,
      "msd_req": 2,
      "service_type": "Data",
      "source_node": 0,
      "destination_node": 8,
      "pps": 1000
    }' | json_pretty
}

benchmark() {
  "$VENV_PY" benchmark_phase6.py --steps 30
}

phase5() {
  bash test/test_phases.sh phase5
}

phase7() {
  bash test/test_phases.sh phase7
}

logs_backend() {
  ./run_backend_docker.sh logs
}

state() {
  curl -sS --max-time 5 "$BACKEND_URL/api/orchestrate/state" | json_pretty
}

bigru_info() {
  cat <<'INFO'
Bi-GRU integration path:
  telemetry/pps -> TrafficForecastService -> forecast alert -> StateManager -> hysteresis gate -> DRL/MBB

Training is optional for connectivity tests:
  - Without JO_VPPM_BIGRU_MODEL_PATH, backend uses deterministic trend forecast fallback.
  - With a trained checkpoint, set:

      export JO_VPPM_BIGRU_MODEL_PATH=/home/CoreRouter/results/models/bigru/bigru_forecaster.pt
      ./run_backend_docker.sh run

Required backend log lines for the DRL brain:
  Loaded JO-VPPM model from results/models/v11/dgrl_v11_final_vietnam.zip
  Loaded VecNormalize scaler from results/models/v11/vec_normalize_v11_vietnam.pkl
INFO
}

case "${1:-}" in
  tmux-guide) tmux_guide ;;
  start-tmux) start_tmux ;;
  start-mininet) start_mininet ;;
  attach-mininet) attach_mininet ;;
  start-tekton-web) start_tekton_web ;;
  attach-tekton-web) attach_tekton_web ;;
  logs-guide) logs_guide ;;
  health) health ;;
  telemetry) telemetry ;;
  orchestrate) orchestrate ;;
  benchmark) benchmark ;;
  phase5) phase5 ;;
  phase7) phase7 ;;
  logs-backend) logs_backend ;;
  state) state ;;
  bigru-info) bigru_info ;;
  -h|--help|help|"") usage ;;
  *)
    usage
    echo "Unsupported command: ${1:-}" >&2
    exit 1
    ;;
esac
