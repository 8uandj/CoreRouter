# 🧠 JO-VPPM MASTER HANDOVER GUIDE (SOTA 2025 Edition)
> **Goal:** Finalize the Thesis on Joint Optimization of VNF Placement and Proactive Migration.
> **Context Type:** Full System State & Technical Roadmap for AI Agents.

---

## 1. Core System Architecture
The system, **JO-VPPM**, is an intelligent orchestrator for SRv6-enabled 5G/6G networks.

### A. Mathematical Problem
- **Input:** SFC Request (CPU, RAM, MSD, Service Type).
- **Constraints:** 
    - **Physical:** CPU/RAM capacity.
    - **Hardware-Plane (MSD):** Maximum Segment Depth limits per node.
- **Objective:** Minimize Latency & Energy, Maximize Acceptance, Ensure 100% Hardware Safety.

### B. Agent Implementation (Current: `dgrl_v8`)
- **Algorithm:** `MaskablePPO` (from `sb3-contrib`).
- **Policy:** `GNNActorCriticPolicy` with **GAT (Graph Attention Network)** layers.
- **Adjacency:** Currently static (based on physical connectivity).
- **Masking:** Invalid Action Masking prevents the agent from selecting nodes that violate CPU or MSD limits.

---

## 2. Component Directory & Logic
| File Path | Description & Logic |
| :--- | :--- |
| `src/orchestration/jo_vdpr/env.py` | **The World:** Manages resource decay, state updates, and action masking. |
| `src/orchestration/jo_vdpr/rewards.py` | **The Brain's Motivation:** Implements "Proportional Knapsack Reward" and "Adaptive Lagrangian Penalty" for SLA. |
| `src/orchestration/jo_vdpr/topology.py` | **The Map:** Contains the 10-node Vietnam Backbone coordinates and MSD limits. |
| `src/portal/backend/app/` | **The Bridge:** FastAPI endpoints. `v8` integration is pending. |
| `src/portal/frontend/src/` | **The Face:** React/Canvas visualization of packets and nodes. |

---

## 3. Critical Academic "Gaps" (Research Debt)
To pass a rigorous thesis defense, the next AI Agent MUST address these points:
1.  **Topological Generalization:** The model is current "overfitted" to 10 nodes. **Action:** Train/Test on **NSFNET** and **GEANT2**.
2.  **Physical-Layer Latency:** Current `D = distance / c`. **Action:** Use $D_{total} = D_{prop} + D_{trans} + D_{queue} + D_{proc}$.
3.  **SRv6 Overhead:** Each SID adds 16 bytes. This must increase $D_{trans}$ in the logic.
4.  **Burst Traffic:** Current traffic is uniform. **Action:** Implement **Poisson Arrival** and **Pareto Flow Sizes**.
5.  **Proactive vs Reactive:** Currently lacks forecasting. **Action:** Feed a "Looking Ahead" window (Temporal features) into the GNN.

---

## 4. Current Artifacts Summary
- [evaluation_synthesis_v2.md](file:///home/hung8uandj/.gemini/antigravity/brain/790f0b8b-ee03-4253-88ba-9e9500e8697a/evaluation_synthesis_v2.md): Comparison of JO-VPPM vs ILP and Greedy.
- [rigorous_critique_response.md](file:///home/hung8uandj/.gemini/antigravity/brain/790f0b8b-ee03-4253-88ba-9e9500e8697a/rigorous_critique_response.md): Formal defense against academic critiques.
- [implementation_plan.md](file:///home/hung8uandj/.gemini/antigravity/brain/790f0b8b-ee03-4253-88ba-9e9500e8697a/implementation_plan.md): The technical roadmap for the next 48 hours.

---

## 5. Instructions for the Next AI Session
1.  **Initialize Context:** Load this file and read `src/orchestration/jo_vdpr/env.py`.
2.  **Priority 1:** Update `env.py` and `rewards.py` with the upgraded Latency Model (SRv6 Overhead + M/M/1).
3.  **Priority 2:** Implement the `AIOrchestrator` service in the backend to provide real-time inference to the UI.
4.  **Priority 3:** Update `Topology.jsx` to support "Burst Mode" visualization (multiple moving packets).
5.  **Priority 4:** Run a 10,000-request benchmark on multiple topologies (Vietnam, GEANT) to generate final thesis charts.

---
**Prepared by:** Antigravity AI
**Status:** Ready for SOTA Evolution & Integration Phase.
