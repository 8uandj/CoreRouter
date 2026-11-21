#!/usr/bin/env bash
set -u
cd /dis/users/dcs/CoreRouter
socket=harp_mentor_completion_20261121
for session in supplement independent_train independent_eval greedy_audit expiry_intervention; do
 while tmux -L "$socket" has-session -t "=$session" 2>/dev/null; do sleep 60; done
 printf 'session_finished=%s\n' "$session"
done
python3 AIO-mesh-submit-2/results/evidence/mentor_completion_20261121/commands/verify_supplement.py || exit 1
[ "$(find AIO-mesh-submit-2/results/evidence/mentor_completion_20261121/greedy_decoupled -name "*.csv" | wc -l)" -eq 180 ] || exit 1
[ "$(find AIO-mesh-submit-2/results/evidence/mentor_completion_20261121/mask_expiry_intervention -name "*.csv" | wc -l)" -eq 60 ] || exit 1
python3 AIO-mesh-submit-2/scripts/rev1/refresh_submission_manifest.py > /tmp/harp_mentor_completion_sha256_refresh.log 2>&1
