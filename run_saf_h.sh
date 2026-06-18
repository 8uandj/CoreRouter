#!/bin/bash
for topo in vietnam nsfnet geant2; do
  for scenario in heavy_tail bursty uniform; do
    echo "Running $topo $scenario..."
    python3 -m src.analytics.benchmark.benchmark_algorithm.run_all --topology $topo --scenario $scenario --skip-exhaustive > /tmp/${topo}_${scenario}.log
    grep "saf_h" /tmp/${topo}_${scenario}.log | head -n 1
  done
done
