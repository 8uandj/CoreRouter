#!/usr/bin/env bash
set -euo pipefail
cd /dis/users/dcs/CoreRouter
socket=harp_mentor_completion_20261121
while tmux -L "$socket" has-session -t '=independent_eval' 2>/dev/null; do
  sleep 60
done
venv/bin/python AIO-mesh-submit-2/scripts/rev1/summarize_independent_training.py
