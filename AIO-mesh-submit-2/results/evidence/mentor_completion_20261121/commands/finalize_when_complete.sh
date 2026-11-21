#!/usr/bin/env bash
set -u
cd /dis/users/dcs/CoreRouter
socket=harp_mentor_completion_20261121
for session in mask oracle seeded_bursty seeded_load_chains saf_sensitivity sparse_gat_mlp; do
 while tmux -L "$socket" has-session -t "=$session" 2>/dev/null; do sleep 60; done
 printf 'session_finished=%s\n' "$session"
done
venv/bin/python - <<'PY'
from pathlib import Path
p=Path('AIO-mesh-submit-2/results/evidence/mentor_completion_20261121')
checks={'mask':(len(list((p/'mask').glob('*/per_seed.csv'))),3),'oracle':(len(list((p/'oracle').glob('*/results.json'))),6),'seeded_bursty':(len(list((p/'seeded_bursty').glob('*/seed_*.csv'))),60),'seeded_load_chains':(len(list((p/'seeded_load_chains').glob('*/load_*_seed_*.csv'))),600),'saf_sensitivity':(len(list((p/'saf_sensitivity').glob('*/*.csv'))),480),'sparse_gat_mlp':(len(list((p/'sparse_gat_mlp').glob('*/seed_*.csv'))),60)}
for name,(actual,expected) in checks.items(): print(f'{name}: {actual}/{expected}',flush=True)
if any(actual!=expected for actual,expected in checks.values()): raise SystemExit('incomplete outputs; checksum refresh deferred, inspect logs')
PY
rc=$?
if [ "$rc" -ne 0 ]; then exit "$rc"; fi
python3 AIO-mesh-submit-2/scripts/rev1/refresh_submission_manifest.py > /tmp/harp_mentor_completion_sha256_refresh.log 2>&1
