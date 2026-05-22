# Manual Server Testbed Validation

Use this when validating CoreRouter manually on server `112.137.129.246`.

## 1. Start The Watch Session

```bash
ssh 112.137.129.246
cd /home/CoreRouter
bash scripts/manual_testbed_validation.sh tmux-guide
```

To create the panes automatically:

```bash
bash scripts/manual_testbed_validation.sh start-tmux
tmux attach -t corerouter
```

The Mininet pane should keep running:

```bash
sudo /home/CoreRouter/venv/bin/python3 infrastructure/sdn/topo_p4.py --p4
```

`topo_p4.py --p4` also starts the SDN Controller REST API on port `8765`.

## 2. Validate The Path

```bash
cd /home/CoreRouter
bash scripts/manual_testbed_validation.sh health
bash scripts/manual_testbed_validation.sh telemetry
bash scripts/manual_testbed_validation.sh orchestrate
bash scripts/manual_testbed_validation.sh benchmark
```

Useful focused smoke tests:

```bash
bash scripts/manual_testbed_validation.sh phase5
bash scripts/manual_testbed_validation.sh phase7
```

Full `test/test_phases.sh` only passes Phase 3 when Mininet is already running.

## 3. Bi-GRU Integration

Current backend data flow:

```text
telemetry/pps -> TrafficForecastService -> forecast alert -> StateManager -> hysteresis gate -> DRL/MBB
```

Training is optional for connectivity validation. Without a checkpoint, the backend
uses deterministic trend forecasting as a stable fallback. With a trained Bi-GRU
checkpoint:

```bash
export JO_VPPM_BIGRU_MODEL_PATH=/home/CoreRouter/results/models/bigru/bigru_forecaster.pt
./run_backend_docker.sh run
```

The real DRL brain is mandatory. Backend startup logs should include:

```text
Loaded JO-VPPM model from results/models/v11/dgrl_v11_final_vietnam.zip
Loaded VecNormalize scaler from results/models/v11/vec_normalize_v11_vietnam.pkl
```
