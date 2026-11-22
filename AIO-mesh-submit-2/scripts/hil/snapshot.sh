#!/usr/bin/env bash
# Read-only snapshot of live P4 tables/counters, K8s inventory and backend state into <dir>.
D="$1"; mkdir -p "$D"; T=/home/CoreRouter/results/hil/e2e_tools
date -u +%FT%T.%NZ > "$D/utc.txt"
for i in $(seq 1 10); do $T/p4cli.sh s$i 'table_dump srv6_local_sid' 'table_dump routing_v6' 'table_dump srv6_end_dx4_table' 'counter_read srv6_advance_counter 0' 'counter_read srv6_terminal_counter 0' 'counter_read msd_violation_counter 0' > "$D/p4_s$i.txt"; done
kubectl -n core-router get deploy -o json > "$D/deployments.json"
kubectl -n core-router get pods -o wide > "$D/pods.txt"
curl -s http://127.0.0.1:8000/api/orchestrate/state > "$D/api_state.json"
curl -s http://127.0.0.1:8765/steer/status > "$D/steer_status.json"
curl -s http://127.0.0.1:8765/stats/msd_drops > "$D/msd_drops.json"
