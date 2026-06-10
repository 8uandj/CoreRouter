# 3S-COM Orchestrator (CoreRouter)

**CoreRouter** is the implementation repository for **3S-COM** (Smart, Scalable, Secure), a closed-loop orchestration platform for Service Function Chaining (SFC) in geo-distributed SDN/NFV networks.

The project supports the bachelor thesis:

**Joint Optimization of VNF Placement and Proactive Migration under Data-Plane Hardware Constraints**

CoreRouter focuses on the **Joint Optimization of VNF Placement and Proactive Migration (JO-VPPM)** problem under real data-plane hardware constraints, especially **Maximum Segment Depth (MSD)** limits in **SRv6/P4** programmable networks. The orchestrator combines rule-based control, graph-aware reinforcement learning, Kubernetes-based VNF lifecycle management, and P4/SRv6 traffic steering.

## Why This Project Exists

Many SFC placement algorithms treat the network as an ideal graph and ignore the physical parsing limits of programmable switches. In SRv6 networks, however, each service path is encoded as a SID stack in the packet header. If the SID stack exceeds the switch's MSD limit, the packet cannot be parsed safely.

CoreRouter treats MSD as a **hard constraint**, not a soft penalty. Unsafe placement/routing actions are masked before execution. If no safe action exists, the system returns:

```text
HTTP 409 NO_SAFE_ACTION
```

This is an intentional **Smart Admission Control** decision, not a runtime failure.

## Key Features

- **Hybrid Orchestration:** Uses lightweight heuristics under stable load and switches to Deep Graph Reinforcement Learning under stress or forecast alerts.
- **Hardware-Aware RL:** Enforces SRv6 MSD limits through invalid action masking.
- **Graph-Aware Policy:** Uses Graph Attention Networks (GAT) with a static adjacency matrix so the agent can reason about network topology.
- **Atomic Placement and Routing:** The RL action is a joint `[v_place, v_route]` decision instead of a fragile two-stage placement-then-routing pipeline.
- **Proactive Migration:** Implements Make-Before-Break migration: create the new VNF, steer traffic to it, then remove the old instance.
- **Hardware-in-the-Loop Testbed:** Integrates MicroK8s, Tekton, Mininet, BMv2 P4 switches, SRv6 steering, and FastAPI.
- **Portal UI:** Provides a React/Vite web interface for topology, VNF registry, telemetry, orchestration, and Tekton pipeline visibility.

## Repository Layout

```text
.ai/                         Project knowledge base and engineering rules
data/                        Telecom traces and generated datasets
docs/                        Thesis, reports, design notes, and evaluation docs
infrastructure/k8s/          MicroK8s manifests and Tekton pipelines
infrastructure/sdn/          Mininet topologies, P4 program, and SDN controller
results/                     Trained models, benchmark outputs, and artifacts
scripts/                     Validation and safety helper scripts
src/ai/                      Heuristic and DGRL agent adapters
src/analytics/               Training, forecasting, benchmarks, visualization
src/core/                    State manager, domain models, and interfaces
src/orchestration/jo_vdpr/   RL environment, reward logic, topology, GNN policy
src/portal/backend/          FastAPI backend
src/portal/frontend/         React/Vite frontend
test/, tests/                Smoke tests and Python unit tests
```

The thesis source is located at:

```text
docs/thesis_latex/myThesis.tex
```

## System Architecture

CoreRouter follows a closed-loop orchestration pipeline:

1. **Telemetry Extraction**
   The system collects CPU, RAM, MSD usage, alert flags, SLA class, and topology-related state from the runtime environment.

2. **Forecasting**
   Traffic telemetry can be used to detect or predict congestion and set alert flags for overloaded nodes.

3. **Decision Engine**
   The orchestrator selects between:
   - a heuristic branch for normal load;
   - a MaskablePPO/GAT DGRL branch for stress load or alert conditions.

4. **Enforcement**
   Kubernetes/Tekton handles VNF lifecycle operations, while the SDN controller installs SRv6/P4 steering rules.

## Prerequisites

For local simulation and backend development:

- Python 3.10+
- `pip`
- Git

For the web portal:

- Node.js 18+
- npm

For the full testbed:

- Linux host with sudo access
- Docker
- MicroK8s
- Tekton Pipelines
- Mininet
- BMv2 / P4 toolchain

The full testbed is optional. You can run offline training, benchmarks, and parts of the backend without MicroK8s or Mininet.

## Python Setup

From the repository root:

```bash
python3 -m venv .venv
. .venv/bin/activate
pip install --upgrade pip
pip install -r requirements.txt
pip install -r src/portal/backend/requirements.txt
```

## Running the Backend

Start the FastAPI backend:

```bash
python3 -m uvicorn src.portal.backend.app.main:app --host 0.0.0.0 --port 8000 --reload
```

Open:

```text
http://localhost:8000
http://localhost:8000/docs
```

Useful API endpoints:

```text
GET  /api/ai/status
GET  /api/orchestrate/status
GET  /api/orchestrate/state
POST /api/orchestrate
POST /api/orchestrate/alert?alert=true
POST /api/orchestrate/reset
POST /api/orchestrate/free
```

### Backend With Docker

The repository also includes a Docker helper for running the backend with the real model configuration:

```bash
./run_backend_docker.sh build
./run_backend_docker.sh run
./run_backend_docker.sh logs
```

Default model environment variables used by the script:

```text
JO_VPPM_ENABLE_MODEL=1
JO_VPPM_REQUIRE_MODEL=1
JO_VPPM_MODEL_PATH=results/models/v11/dgrl_v11_final_vietnam.zip
JO_VPPM_SCALER_PATH=results/models/v11/vec_normalize_v11_vietnam.pkl
```

Stop the container:

```bash
./run_backend_docker.sh stop
```

## Running the Frontend

In a separate terminal:

```bash
cd src/portal/frontend
npm install
npm run dev
```

Open:

```text
http://localhost:5173
```

The frontend expects the backend to be available at `http://localhost:8000`.

## Running Benchmarks

Small live backend benchmark:

```bash
python3 benchmark_phase6.py --steps 30
```

Longer live backend benchmark:

```bash
python3 benchmark_phase6.py --steps 300
```

Offline algorithm benchmark:

```bash
python3 -m src.analytics.benchmark.benchmark_algorithm.run_all
```

Runtime testbed benchmark:

```bash
python3 -m src.analytics.benchmark.benchmark_testbed.run_all_scenarios \
  --api-base-url http://127.0.0.1:8000/api \
  --sdn-base-url http://127.0.0.1:8765
```

## Running Tests and Smoke Checks

Python unit tests:

```bash
pytest tests
```

Phase smoke tests:

```bash
bash test/test_phases.sh phase5
bash test/test_phases.sh phase6
bash test/test_phases.sh phase7
```

Full testbed smoke test:

```bash
sudo bash test/test_phases.sh all
```

Manual validation helper:

```bash
bash scripts/manual_testbed_validation.sh status
bash scripts/manual_testbed_validation.sh orchestrate
bash scripts/manual_testbed_validation.sh benchmark
```

Some phase tests require MicroK8s, Tekton, Mininet, and the backend/frontend to already be running.

## Full Testbed Setup

The full hardware-in-the-loop style environment combines:

- MicroK8s for VNF workloads;
- Tekton for VNF deployment and migration pipelines;
- Mininet for the emulated transport network;
- BMv2/P4 for SRv6 data-plane behavior;
- FastAPI for orchestration APIs;
- React/Vite for the portal.

Start with the Kubernetes documentation:

```text
infrastructure/k8s/README.md
```

Useful runbooks:

```text
infrastructure/k8s/tekton/RUNBOOK-migrate-single-vnf.md
docs/note/manual_server_testbed_validation.md
docs/note/phase2_migrate_single_runbook.md
```

## Make-Before-Break Migration

CoreRouter's migration process follows three phases:

1. **Make:** deploy the replacement VNF on a safe target node.
2. **Steer:** update SRv6/P4 steering rules so new traffic reaches the replacement VNF.
3. **Break:** remove the old VNF only after steering is confirmed.

The old VNF must not be deleted before steering is complete. Otherwise, the migration no longer preserves service continuity.

## Important Runtime Semantics

- `409 NO_SAFE_ACTION` means no safe placement/routing action exists. This is expected behavior.
- MSD limits must remain hard constraints.
- Do not bypass invalid action masking to improve acceptance rate.
- Do not treat high rejection under stress as automatically wrong; under saturated conditions, rejection can be the correct admission-control decision.
- The GAT policy depends on a static physical adjacency matrix.
- The active development direction is Hybrid Orchestration: RuleDRL + MaskablePPO/GAT + Make-Before-Break.

## Training Notes

Training scripts are located in:

```text
src/analytics/training/
```

For MaskablePPO + GAT stability, use `VecNormalize` together with the rollout configuration validated for this project:

```text
n_steps = 512
num_parallel_envs = 10
rollout batch = 10 x 512 = 5120
batch_size = 128 or 256
```

Do not treat `VecNormalize` alone as a complete stability fix.

## Documentation

Key project documents:

```text
docs/thesis_latex/myThesis.tex
docs/JO_VPPM_MASTER_HANDOVER.md
docs/JO_VDPR_Orchestrator_Mechanism.md
docs/evaluation_synthesis.md
3s_com_testbed_status.md
3s_com_testbed_v11_context.md
```

## Development Guidelines

Before making architectural changes, read the project context under `.ai/`. These files capture the current research scope, invariants, and deployment constraints.

Important boundaries:

- Keep changes aligned with Hybrid Orchestration.
- Keep MSD enforcement as a hard safety rule.
- Keep placement and routing as an atomic decision where the RL path is involved.
- Keep Make-Before-Break ordering intact.
- Do not add implementation work for MORL, Pareto Front, Curriculum Learning, Federated Learning, or Multi-Agent RL unless the project roadmap is explicitly changed.

## License

No license file is currently included. Treat this repository as research code unless a license is added.
