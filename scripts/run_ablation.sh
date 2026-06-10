#!/bin/bash
# ═══════════════════════════════════════════════════════════════
# HARP Ablation Study — Background Runner Script
# ═══════════════════════════════════════════════════════════════
#
# Usage (on server 112.137.129.246):
#   chmod +x scripts/run_ablation.sh
#   nohup bash scripts/run_ablation.sh > ablation.log 2>&1 &
#   tail -f ablation.log
#
# Usage (on Kaggle):
#   Upload the CoreRouter repo, then run in a cell:
#   !cd /kaggle/working/CoreRouter && bash scripts/run_ablation.sh
#
# Prerequisites:
#   - Python 3.10+ with packages: gymnasium, sb3-contrib, stable-baselines3,
#     torch, numpy, matplotlib
#   - Model files exist at results/models/v11/
#   - Dataset at data/processed/real_telecom_combined.csv
# ═══════════════════════════════════════════════════════════════

set -euo pipefail

# ── Configuration ──
TOPOLOGY="vietnam"
STEPS=3000
SEEDS="5"     # Use all 5 seeds (42, 100, 2024, 8888, 9999)
WORKERS=1     # Set to number of CPU cores for parallelism
OUTPUT_DIR="results/benchmark_ablation"

# ── Detect project root ──
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"
cd "$PROJECT_ROOT"

echo "═══════════════════════════════════════════════════════════"
echo "  HARP Ablation Study Runner"
echo "  Topology: $TOPOLOGY | Steps: $STEPS | Seeds: $SEEDS"
echo "  Project Root: $PROJECT_ROOT"
echo "  Started: $(date)"
echo "═══════════════════════════════════════════════════════════"

# ── Verify prerequisites ──
echo ""
echo "▶ Checking prerequisites..."

# Check Python
if ! command -v python3 &> /dev/null; then
    echo "ERROR: python3 not found. Please install Python 3.10+"
    exit 1
fi
echo "  ✓ Python: $(python3 --version)"

# Check model files
MODEL_PATH="results/models/v11/dgrl_v11_final_${TOPOLOGY}.zip"
NORM_PATH="results/models/v11/vec_normalize_v11_${TOPOLOGY}.pkl"

if [ ! -f "$MODEL_PATH" ]; then
    echo "WARNING: Model not found at $MODEL_PATH"
    echo "  Ablation variants using the trained model will return empty results."
    echo "  Make sure to place the model file before running."
fi

if [ ! -f "$NORM_PATH" ]; then
    echo "WARNING: Normalizer not found at $NORM_PATH"
fi

# Check dataset
DATA_PATH="data/processed/real_telecom_combined.csv"
if [ ! -f "$DATA_PATH" ]; then
    DATA_PATH="data/real_telecom_combined.csv"
    if [ ! -f "$DATA_PATH" ]; then
        echo "WARNING: Dataset not found. Will use fallback path."
    fi
fi

# ── Install dependencies if needed ──
echo ""
echo "▶ Checking Python dependencies..."
python3 -c "import gymnasium; import sb3_contrib; import torch; import matplotlib; print('  ✓ All dependencies OK')" 2>/dev/null || {
    echo "  Installing missing dependencies..."
    pip install gymnasium sb3-contrib stable-baselines3 torch matplotlib numpy
}

# ── Set environment ──
export PYTHONPATH="$PROJECT_ROOT:${PYTHONPATH:-}"
export OMP_NUM_THREADS=1
export MKL_NUM_THREADS=1
export OPENBLAS_NUM_THREADS=1
export MPLCONFIGDIR="/tmp/matplotlib"

# ── Run Ablation Benchmark ──
echo ""
echo "═══════════════════════════════════════════════════════════"
echo "  Starting HARP Ablation Benchmark"
echo "  5 variants × 3 scenarios × ${SEEDS} seeds × ${STEPS} steps"
echo "  Estimated time: ~15-30 minutes (single-threaded)"
echo "═══════════════════════════════════════════════════════════"
echo ""

python3 -m src.analytics.benchmark.benchmark_algorithm.run_all \
    --topology "$TOPOLOGY" \
    --scenario ablation \
    --load stress \
    --steps "$STEPS" \
    --workers "$WORKERS" \
    --output-dir "$OUTPUT_DIR" \
    --ablation

EXIT_CODE=$?

echo ""
echo "═══════════════════════════════════════════════════════════"
if [ $EXIT_CODE -eq 0 ]; then
    echo "  ✓ Ablation benchmark completed successfully!"
    echo "  Results saved to: $OUTPUT_DIR/"
    echo "  Finished: $(date)"

    # ── Print summary ──
    echo ""
    echo "  Output files:"
    find "$OUTPUT_DIR" -name "*.csv" -o -name "*.png" -o -name "*.pdf" -o -name "*.json" | sort | head -20
else
    echo "  ✗ Ablation benchmark FAILED with exit code $EXIT_CODE"
    echo "  Check ablation.log for details"
fi
echo "═══════════════════════════════════════════════════════════"
