#!/usr/bin/env bash
set -euo pipefail
cd /dis/users/dcs/CoreRouter
export OMP_NUM_THREADS=1 MKL_NUM_THREADS=1 OPENBLAS_NUM_THREADS=1
for topo in vietnam nsfnet geant2; do
 venv/bin/python scripts/rev1/audit_mask_ttl.py --topology "$topo" --output "results/evidence/mentor_completion_20261121/mask/$topo" > "results/evidence/mentor_completion_20261121/logs/mask_$topo.log" 2>&1 &
done
wait
