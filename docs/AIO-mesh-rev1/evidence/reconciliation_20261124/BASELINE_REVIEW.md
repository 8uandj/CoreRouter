# Đối chiếu toàn bộ văn bản với submit1

Mốc: `docs/AIO-mesh-submitted 1/submitted-1.tex`. Bao phủ tất cả các phần gốc, kể cả Funding/CRediT; bảng, hình, công thức và thuật toán nằm trong diff source đầy đủ. Các số giữ lại được kiểm tra bằng `check_evidence.py`. Trạng thái so khớp là mô tả câu chữ, không phải chứng nhận nội dung khoa học.

| Phần gốc | Dòng gốc | Trạng thái câu chữ | Lý do |
|---|---:|---|---|
| Abstract | 91 | 0 giữ nguyên; 1 sửa; 0 thay/bỏ | R2.1–R2.3/P0.2/P1.2: runtime attribution and audited measurements replace unsupported result claims; original introduction retained. |
| Introduction | 103 | 0 giữ nguyên; 6 sửa; 4 thay/bỏ | R2.1/R3/R4.1/R5.1/R5.3: runtime contribution, abbreviation definitions, practical MSD failure semantics; no unsupported universal policy advantage. |
| Background and Related Work | 136 | 1 giữ nguyên; 0 sửa; 0 thay/bỏ | R2.1/R3: original framing retained. |
| AIOps and MLOps for Cloud-Native Infrastructure | 141 | 2 giữ nguyên; 0 sửa; 0 thay/bỏ | Original background and citations retained. |
| Learning-Based Resource and Service-Chain Orchestration | 173 | 0 giữ nguyên; 2 sửa; 1 thay/bỏ | R4.1: abbreviation definitions; absent original bibliography keys are not invented. |
| Programmable Data Planes and Hardware-Constrained Actuation | 182 | 0 giữ nguyên; 2 sửa; 0 thay/bỏ | R4.1/R5.1: SRH definition and MSD failure context. |
| Safe and Graph-Aware Reinforcement Learning for Infrastructure Control | 189 | 0 giữ nguyên; 2 sửa; 0 thay/bỏ | R2.1/R3/R5.3: credit established techniques and distinguish runtime from policy safety. |
| Research Gap Summary | 196 | 1 giữ nguyên; 0 sửa; 2 thay/bỏ | R2.1/R3/R5.3: qualify overbroad novelty claims; preserve submitted design principles. |
| System Model and Design Requirements | 206 | 1 giữ nguyên; 0 sửa; 0 thay/bỏ | Original section introduction retained. |
| Cloud-Native Programmable Substrate | 211 | 0 giữ nguyên; 2 sửa; 0 thay/bỏ | R4.1: expand NFVI/RAM; retain substrate/state model. |
| Service-Chain Request and Orchestration Decision | 222 | 2 giữ nguyên; 2 sửa; 1 thay/bỏ | P0.5/P1.1: requested depth and actual pair interface; retain full-chain model as system target and migration qualification. |
| Hardware-Safety and Admission Constraints | 251 | 2 giữ nguyên; 2 sửa; 1 thay/bỏ | P0.5/P1.1/R5.2: distinguish depth per profile, instance accounting, and checked versus desired full-chain feasibility. |
| Operational Objective | 285 | 1 giữ nguyên; 2 sửa; 0 thay/bỏ | Restore submitted generic objective; clarify it is not the implemented PPO reward. P0.3/R2.5: local pair selection and action-switching proxy. |
| Design Requirements | 307 | 1 giữ nguyên; 1 sửa; 0 thay/bỏ | R2.2/R5.4: guard scope of safety and searched feasible set; original topology-awareness requirement retained. |
| AIO-Mesh Architecture | 315 | 0 giữ nguyên; 2 sửa; 0 thay/bỏ | R2.2/R2.5: policy proposes a pair; runtime handles lifecycle and admission. |
| Closed-Loop Runtime Organization | 329 | 2 giữ nguyên; 2 sửa; 0 thay/bỏ | R2.5/R5.4: exact Hybrid hysteresis and route-profile check; original operational loop retained. |
| Policy Runtime and State Management | 340 | 2 giữ nguyên; 1 sửa; 0 thay/bỏ | R2.2: fallback is a proposal subject to independent admission; other submitted paragraphs retained. |
| Safety Boundary and Admission Semantics | 349 | 0 giữ nguyên; 2 sửa; 1 thay/bỏ | R2.2/R5.4: independent local validation/reservation and snapshot-version interval. Original unverified automatic recovery/counter-response guarantees are not reinstated. |
| Cloud-Native Lifecycle Actuation | 358 | 0 giữ nguyên; 2 sửa; 0 thay/bỏ | P1.1/P1.2: original deployment/MBB/steering explanation retained, campaign measurement scopes added. |
| Programmable Data-Plane Interface | 365 | 0 giữ nguyên; 1 sửa; 1 thay/bỏ | P0.5/P1.1: source-backed compiler, anchor, wire order, exact-depth/MSD checks and no path cache replace unsupported realization guarantees. |
| End-to-End Request Lifecycle | 372 | 0 giữ nguyên; 2 sửa; 0 thay/bỏ | P0.4/P1.1: original full lifecycle/Algorithm 1 restored; local reservation, admission-only branch and context-driven migration clarified. |
| HARP: Hardware-Aware Reinforcement Policy | 410 | 1 giữ nguyên; 1 sửa; 0 thay/bỏ | P0.3/P0.4/R2.2: distinguish proposal masking from admission and action switching from migration. |
| MDP Formulation | 417 | 1 giữ nguyên; 2 sửa; 2 thay/bỏ | P1.1/R2.5: correct N² pair head replaces nonexistent policy migration mode/cached K-path interface. Original displayed MDP and state restored. |
| Graph-Attention State Encoder | 443 | 0 giữ nguyên; 2 sửa; 2 thay/bỏ | R2.3/R5.4: original attention equations retained; correct actual fusion/normalization and qualify MLP-insufficiency claim. |
| Hard-Feasibility Action Mask | 484 | 1 giữ nguyên; 2 sửa; 2 thay/bỏ | P0.4/P0.5/P1.1: local BW/MSD predicates, no cache, empty mask, variant distributions and independent admission. |
| Reward for Soft Operational Objectives | 554 | 0 giữ nguyên; 1 sửa; 2 thay/bỏ | P0.3/R2.5: replace generic reward presented as implementation with actual reward and callback; preserve separate generic system objective. |
| Admission and Migration Semantics | 584 | 0 giữ nguyên; 0 sửa; 4 thay/bỏ | P0.4/P1.1: actual training/evaluation/live empty-mask behavior and lifecycle-driven migration replace unsupported policy modes. |
| Decision Procedure | 607 | 0 giữ nguyên; 2 sửa; 0 thay/bỏ | P0.4/P1.1: guarded inference/fallback replaces nonexistent cached-path selection; restore original procedural explanation and add N² cost. |
| Experiments and Evaluation | 635 | 0 giữ nguyên; 1 sửa; 0 thay/bỏ | R2.2–R2.5/R4.2/R5.5: retain original five evaluation questions with scope corrections. |
| Experimental Setup | 647 | 0 giữ nguyên; 0 sửa; 3 thay/bỏ | R2.3/P1.1/P2.1: actual workloads, 20 seeds, models, complete configured adjacency and no K-path cache replace inaccurate submitted protocol. |
| Baselines, Ablation Variants, and Metrics | 659 | 0 giữ nguyên; 0 sửa; 4 thay/bỏ | R2.2–R2.4/P2.1: actual heuristics, tested ablations, statistics and denominators replace inaccurate baseline/variant descriptions. |
| Hardware-Safe Admission under Workload Saturation | 669 | 0 giữ nguyên; 1 sửa; 0 thay/bỏ | R2.2/R2.4: retain original saturation question/figure reference; expand with common protected-admission evidence. Detailed sweeps in checklist Section 6.8. |
| Simulation Results across Distributed Topologies | 680 | 0 giữ nguyên; 0 sửa; 3 thay/bỏ | R2.3/P2.1: replace unsupported old means/claims with audited tables and paired comparisons. Old burst-results table has no independent verified full metric set and is not relabeled as new evidence. |
| Ablation Study | 750 | 0 giữ nguyên; 0 sửa; 3 thay/bỏ | R2.2–R2.4/P2.1: actual variants/admission bypass results and timing; old Pareto-optimality figure/claims are not supported by corrected records. |
| Hardware-in-the-Loop Testbed Validation | 816 | 0 giữ nguyên; 0 sửa; 4 thay/bỏ | P0.2/P0.5/P1.1/P1.2: request-correlated E2E, MSD injections and separate long-run protocols replace unsupported old scenario table. |
| Operational Interpretation, Overhead, and Limitations | 861 | 0 giữ nguyên; 0 sửa; 4 thay/bỏ | R2.3/R4.2/R5.5: qualify workload-dependent policy tradeoffs, timing regimes and measured testbed scope. |
| Conclusion | 875 | 0 giữ nguyên; 1 sửa; 3 thay/bỏ | R5.6: two paragraphs; retain original opening motivation, update results and qualify only measured scope. |
| Declaration of Competing Interest | 886 | 1 giữ nguyên; 0 sửa; 0 thay/bỏ | Restored unchanged from submitted manuscript. |
| Funding | 890 | 1 giữ nguyên; 0 sửa; 0 thay/bỏ | Restored original submitted grant; no reviewer request authorizes changing grant attribution. |
| Data and Code Availability | 893 | 0 giữ nguyên; 0 sửa; 1 thay/bỏ | P2.1/R2.3: retain repository, clarify retained artifact/reproduction scope rather than asserting unsupported full public availability. |
| Declaration of Generative AI and AI-Assisted Technologies in the Writing Process | 897 | 1 giữ nguyên; 0 sửa; 0 thay/bỏ | Retained unchanged from submitted manuscript. |
| CRediT Authorship Contribution Statement | 900 | 1 giữ nguyên; 0 sửa; 0 thay/bỏ | Restored original author roles; no reviewer request authorizes changing authorship credit. |

Chi tiết từng đoạn và vị trí tương ứng: `submit1_paragraph_review.json`. Diff trực tiếp toàn bộ source, không dùng bản rev1 trung gian làm baseline: `SUBMIT1_TO_REV1.diff`.

Tổng số đoạn văn được lập mục: 117. Số khớp nguyên câu chữ sau khi bỏ markup revision/whitespace: 22. Các phần sửa/thay đều có mục lý do ở trên; cần đọc đoạn gốc và đoạn revision trong JSON khi đánh giá ý nghĩa.
