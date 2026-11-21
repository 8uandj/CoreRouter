#!/usr/bin/env bash
set -euo pipefail
cd /dis/users/dcs/CoreRouter
export OMP_NUM_THREADS=1 MKL_NUM_THREADS=1 OPENBLAS_NUM_THREADS=1
exec venv/bin/python -u scripts/rev1/run_mask_expiry_intervention.py
