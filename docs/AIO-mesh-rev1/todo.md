# AIO-Mesh FGCS Major Revision — TODO

## Mục tiêu của vòng revise

Bản revise phải tách rõ hai lớp đóng góp: **(i) runtime safety contract của AIO-Mesh** là nguồn của thuộc tính fail-closed trước actuation; **(ii) HARP** là một policy có thể thay thế, có nhiệm vụ cải thiện chất lượng/hiệu quả của candidate actions. Không tiếp tục diễn đạt PPO, GAT hoặc invalid-action masking như các thuật toán mới. Claim về safety chỉ giới hạn trong các hard constraints đã mô hình hóa (CPU, memory, SRv6 MSD) và trạng thái mà controller quan sát được.

## P0 — Bắt buộc hoàn thành trước khi resubmit

| ID | Reviewer concern | Công việc phải làm | Đầu ra cần cập nhật trong paper |
|---|---|---|---|
| P0.1 | R2: Elephant và Chaos có số liệu giống hệt nhau | **Đã xác minh cho current-code rerun:** manifest map Elephant stress → `heavy_tail`, Chaos → `chaos`; simulator định nghĩa heavy-tail bằng shock độc lập 20%, còn Chaos là Markov hai trạng thái với mức vào/ra stress khác nhau. Rerun 20 seed × 3,000 bước hoàn tất trên cả ba topology; scenario mapping lưu trong run manifests. Các aggregate historical trước rerun vẫn cần lineage audit riêng. | Các profile và số liệu khác nhau trong `rev1.tex`; manifests tại `results/rev1/{vietnam,nsfnet,geant2}/benchmark/`. |
| P0.2 | R2: safety chưa được tách khỏi policy | **Hoàn tất trong simulator:** Greedy, DAI, SAF-H, CSPF và HARP cùng qua protected admission; admitted modeled hard violations đều bằng 0 trong chín topology--workload conditions. Manuscript phân biệt zero admitted modeled violations (runtime boundary) với candidate quality. | `rev1.tex`: protected benchmark, admission/ablation tables, limitations; không tuyên bố đây là HIL hoặc forwarding proof. |
| P0.3 | R2: HARP vs SAF-H có margin nhỏ, chưa significance | CSPF-style constrained pair baseline đã chạy đủ 180 lượt (20 seed × 3 workload × 3 topology); trace hashes khớp HARP trong cả chín condition. HARP--CSPF Δ = +0.18--+0.86 pp; sáu paired tests còn significant sau Holm. SAF-H vẫn thắng HARP trong bảy stress conditions, HARP thắng một và một inconclusive comparison. | CSPF column và paired table đã thêm vào `rev1.tex`; raw/provenance/statistics tại `results/rev1/cspf_baseline/`. CSPF là endpoint-pair adaptation, không full ingress-to-egress CSPF. |
| P0.4 | R2: compact action/anchor chưa xác định đầy đủ chain | Đối chiếu code để xác định chính xác `v_place` áp dụng cho function nào/chain-level template nào; mô tả thuật toán dựng `phi_q`, các segment paths và full SID list từ `(v_place,v_anchor,m)`. Tạo test với chain ≥3 VNFs và đối chiếu `h_q` giữa mask/admission/controller. | Hoàn thiện Sec. System Model, HARP MDP, Algorithm 2; không để TODO semantics. |
| P0.5 | R2/R4/R5: không có end-to-end decision latency/scalability | **Đang chạy:** ba HARP checkpoint synthetic 25/50/100 được huấn luyện độc lập trong tmux, cùng seed 42, 3M bước, 10 envs, rollout 512 và batch 32; synthetic benchmark sẽ chạy theo protocol 20 seed × 3 workload × 3,000 bước sau training. Batch 32 dùng nhất quán sau khi GAT trên 100 nodes OOM ở batch 256. **Còn thiếu:** per-request interval tới controller handoff, live concurrency, admission/deployment/readiness/steering latency. | Log: `results/rev1/training_logs/synthetic_{25,50,100}_batch32.log`; deferred evaluation được giám sát trong tmux. Figure/table chỉ thêm sau khi có raw output; không suy generalization từ timing SAF-H. |
| P0.6 | R2: path cache có thể tạo false infeasibility | **Không áp dụng cho current code:** audit xác nhận runtime hiện tại không có candidate-path cache/K. Manuscript phải giữ phần cache ở giới hạn/related-work context và không mô tả rejection là cache miss hay global infeasibility. | Không cần K-sensitivity nếu code và manuscript tiếp tục xác nhận không có cache; xóa mọi bảng/claim K từ implementation khác. |
| P0.7 | R2: Hybrid predicate chưa định nghĩa | **Đã định nghĩa và source-check:** mode chuyển sang HARP khi (u_t>0.45) hoặc alert active; chuyển về heuristic khi (u_t<0.35) và không có alert; giữa hai ngưỡng giữ mode trước. Không có dwell-time rule hay forecasting model và không báo cáo lợi ích Hybrid riêng. | Eq.~\ref{eq:hybrid_gate} và phần giải thích giới hạn trong `rev1.tex`; ngưỡng trong `src/core/state_manager.py`. |
| P0.8 | R5: feature normalization, mask frequency, stale state, TOCTOU | **Đã mô tả một phần:** 6 node + 13 global features, frozen checkpoint normalizer, mask tại mỗi inference, local state-version check dưới process lock, optional telemetry TTL. **Còn giới hạn:** upstream measurement age không xác minh; không có atomic transaction qua Kubernetes/P4; TTL mặc định không đảm bảo freshness nếu chưa cấu hình. | Feature semantics và giới hạn được ghi trong `rev1.tex`; phải giữ nguyên wording có điều kiện, không claim cross-controller atomicity. |

## P1 — Nên hoàn thành để vòng major revision thuyết phục

| ID | Reviewer concern | Công việc đề xuất | Đầu ra |
|---|---|---|---|
| P1.1 | R2: load sweep chỉ có một curve | **Hoàn tất:** load sweep 0.2–1.5 cho HARP, SAF-H, Greedy và Decoupled AI với common admission trên matched traces tại Vietnam, NSFNET, GEANT2. | Figure và bảng current-code load sweep trong `rev1.tex`; per-seed evidence tại `evidence/load_sweep/`. |
| P1.2 | R4/R5: topology nhỏ | SAF-H synthetic timing đã có (10 seeds × 300 decisions), archive per-seed đã nằm trong bundle. HARP N² 25/50/100-node checkpoints và benchmark 20 seeds × 3 workload × 3.000 bước đã hoàn tất; số liệu acceptance và timing thành phần đã có trong `rev1.tex`. Chưa chạy 200 nodes, live API concurrency hay phép timing HARP cô lập. | Giữ rõ SAF-H serialized timing và HARP concurrent benchmark timing là hai phép đo khác nhau; không diễn giải evaluation seeds thành independent training uncertainty. |
| P1.3 | R5: services/concurrent chains | **Đã đo occupancy:** 0/25/50/100 background chains trên ba topology với 20 seeds. Live concurrent API requests/queueing policy chưa đo. | Table~\ref{tab:active_chain_stress}; raw manifests tại `results/rev1/e4_active_chains/`. |
| P1.4 | R5: long-running stability | Chạy HIL liên tục tối thiểu vài giờ; ưu tiên 24 h nếu khả thi. Ghi total requests, admitted/rejected, rejection by constraint, migrations, controller/deployment failures, telemetry/mask refresh failures, latency drift, admitted MSD violations. | Subsection “Extended HIL stability”. Không gọi là production case study nếu không chạy trên carrier production. |
| P1.5 | R5: practical MSD consequence | Tạo controlled over-MSD test: cố ý tạo SID list > MSD, ghi controller/admission outcome và BMv2/P4 counter/log. Phân biệt rõ target-specific behavior; không suy rộng BMv2 thành mọi ASIC. | 1 đoạn motivation + 1 row/table/log summary; có thể dùng appendix nếu dài. |
| P1.6 | R2/R5: masking role | **Hoàn tất 2026-11-17:** đã báo tỷ lệ candidate bị mask, runtime rejection, admitted hard violations và safe acceptance trên matched traces cho Vietnam, NSFNET, GEANT2 (20 evaluation seeds × 4 workload × 7 variants); paired SoftMSD admission bật/tắt dùng cùng checkpoint. | Bảng/prose E3 trong `rev1.tex`; tổng hợp và provenance tại `evidence/e3/`. |
| P1.7 | R4: abbreviations | **Đã rà soát và chỉnh first-use** cho các thuật ngữ trong bài gồm SRv6, SAF-H, GAT, MDP, CPU/RAM, TTL, HTTP/API, ASIC, SD/CI, MLP, 5G/B5G và các thuật ngữ related-work. Cần một lượt kiểm tra sau khi chèn số liệu/thí nghiệm mới. | Các chỉnh sửa văn bản/heading trong `rev1.tex` được tô xanh; kiểm tra lại acronym order khi tích hợp bảng/figure mới. |

## Hình cần sửa/bổ sung

1. **`figs/overview.pdf`**: làm rõ ba khối theo thứ tự `Policy/Heuristic -> independent runtime admission -> actuation`. Gắn nhãn HARP là “replaceable policy instance”; không vẽ masking như nguồn duy nhất của safety. Thêm state version/freshness vào đường telemetry nếu implementation có.
2. **`figs/VN_load_sweep.pdf`**: thay single-method curve bằng multiple protected baselines; ưu tiên 2 panels: (a) safe acceptance; (b) runtime rejection/hard-infeasible pressure. Nếu admitted violation của tất cả protected methods đều 0 thì có thể biểu diễn bằng annotation thay vì curve chồng nhau.
3. **`figs/testbed.pdf`**: thể hiện rõ protected vs bypass path; mọi protected policy phải đi qua cùng Admission Boundary. Nếu thêm protected Greedy/DAI, figure không cần đổi logic nhưng caption phải nói common boundary.
4. **Hình mới — K sensitivity**: x=`K`; y1=safe acceptance, y2=mask latency/cache memory hoặc dùng bảng nếu figure quá dày.
5. **Hình mới — Scalability/latency**: `figs/policy_cost_scalability.pdf` hiện báo HARP-vs-SAF-H decision percentiles ở Vietnam và SAF-H feasible-set percentiles trên 25/50/100 synthetic nodes. Đây là phép đo simulator-side; bổ sung HARP size-matched checkpoints và actuation timing nếu sau này thực hiện được, không gộp actuation vào decision latency.
6. **Hình mới tùy chọn — Long-run HIL**: time series decision latency + cumulative admitted violations/rejections; nếu không có biến động đáng kể, dùng summary table thay figure.

## Protocol thực nghiệm khuyến nghị

- Dùng **matched workload traces và matched random seeds** giữa HARP và SAF-H để paired tests có ý nghĩa.
- Lưu `seed`, topology version, workload config, `K`, model checkpoint hash, admission config, MSD profile, telemetry period, hardware/software version cùng mỗi run.
- Tách **decision latency** khỏi **actuation latency**. Decision latency kết thúc ở controller handoff; Kubernetes readiness/Tekton/SRv6 install được báo riêng.
- Với scalability, báo cả `|V|`, `|E|`, `|M|`, `K`, số active chains, concurrency, CPU/GPU của máy chạy policy, RAM, Python/PyTorch version.
- Với significance: primary comparison nên là HARP vs SAF-H; tránh test quá nhiều cặp nếu không cần. Báo exact `p`, CI và effect size, không chỉ dấu `*`.
- Không dùng cụm “globally infeasible” khi chỉ tìm trên `K` cached paths. Dùng “no feasible cached realization”.
- Không claim “hardware-safe by construction” theo nghĩa tuyệt đối. Dùng “fail-closed pre-actuation safety for the modeled CPU/memory/MSD constraints under controller-visible state”.

## Các điểm text cần hoàn thiện sau khi có số liệu

- Abstract: thay câu mô tả kết quả bằng các số chính sau rerun; giữ HARP là policy instantiation, runtime boundary là safety source.
- Introduction/Contributions: không đưa PPO/GAT/masking vào danh sách methodological novelty.
- Table related work: kiểm tra từng cột “Independent admission” và “Explicit PDP/MSD” trước submission; tránh đánh dấu tuyệt đối nếu paper liên quan chỉ hỗ trợ một phần.
- Experimental Setup: đổi “5 runs” sang số runs thực tế và ghi statistical protocol.
- Table `simulation_acceptance_summary`: thay toàn bộ dòng bị ảnh hưởng bởi audit Elephant/Chaos.
- HIL table: thêm protected Greedy/DAI hoặc tạo bảng mới nếu layout hiện tại quá chật.
- Operational Interpretation: chèn measured latency/scalability; bỏ từ “practical” nếu chưa có số đo hỗ trợ.
- Conclusion: đã rút còn hai đoạn, không nhắc lặp lại timing; cập nhật thêm khi CSPF và synthetic/arrival-rate raw results hoàn tất.
