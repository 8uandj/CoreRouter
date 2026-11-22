#!/usr/bin/env bash
# Read-only environment inventory for the HIL testbed export.
# Usage: scripts/collect_inventory.sh <output_dir>
# Performs only reads: git metadata, process/tmux/docker listings, resource
# usage, Kubernetes GETs, and HTTP GETs on the backend and SDN controller.
set -u
OUT="${1:?output dir}"
REPO=/home/CoreRouter
mkdir -p "$OUT"
ts() { date -u +%Y-%m-%dT%H:%M:%SZ; }
run() { # run <name> <cmd...>
  local name="$1"; shift
  { echo "# captured_utc=$(ts)"; echo "# cmd: $*"; "$@"; echo "# exit=$?"; } > "$OUT/$name.txt" 2>&1
}
run host_identity      bash -c 'hostname; whoami; id; uname -a; uptime; nproc'
run resources          bash -c 'free -h; df -h / /home; cat /proc/loadavg'
run git_state          bash -c "cd $REPO && git rev-parse HEAD && git branch --show-current && git status --short && git log --oneline -20 && git reflog -10"
run tmux_sessions      bash -c 'tmux ls; tmux list-windows -a -F "#{session_name}:#{window_index} #{pane_current_command} #{pane_pid}"'
run processes_project  bash -c 'ps -eo pid,user,lstart,etime,pcpu,pmem,cmd | grep -E "simple_switch|topo_p4|uvicorn|run_all_scenarios|monitor_kubernetes|tcpdump" | grep -v grep'
run docker_ps          docker ps --format '{{.ID}} {{.Names}} {{.Image}} {{.Status}} {{.CreatedAt}}'
run docker_inspect_backend docker inspect 3s-com-backend --format '{{.Id}} image={{.Image}} created={{.Created}} started={{.State.StartedAt}} restarts={{.RestartCount}} mounts={{json .Mounts}}'
run docker_inspect_mininet docker inspect gracious_jackson --format '{{.Id}} image={{.Image}} created={{.Created}} started={{.State.StartedAt}} cmd={{json .Config.Cmd}}'
run k8s_nodes          kubectl get nodes -o wide
run k8s_core_router    bash -c 'kubectl -n core-router get deployments -o wide; kubectl -n core-router get pods -o wide --field-selector=status.phase=Running; kubectl -n core-router get svc'
run k8s_pipelineruns_recent bash -c 'kubectl -n core-router get pipelineruns --sort-by=.metadata.creationTimestamp | tail -15'
run api_health         curl -s -m 5 -w '\nHTTP %{http_code}\n' http://127.0.0.1:8000/api/health
run api_orchestrate_status curl -s -m 5 -w '\nHTTP %{http_code}\n' http://127.0.0.1:8000/api/orchestrate/status
run api_orchestrate_state  curl -s -m 10 -w '\nHTTP %{http_code}\n' http://127.0.0.1:8000/api/orchestrate/state
run sdn_health         curl -s -m 5 -w '\nHTTP %{http_code}\n' http://127.0.0.1:8765/health
run sdn_msd_drops      curl -s -m 5 -w '\nHTTP %{http_code}\n' http://127.0.0.1:8765/stats/msd_drops
run sdn_steer_status   curl -s -m 5 -w '\nHTTP %{http_code}\n' http://127.0.0.1:8765/steer/status
run sdn_topology       curl -s -m 5 -w '\nHTTP %{http_code}\n' http://127.0.0.1:8765/topology
echo "inventory written to $OUT"
