# AIO-Mesh FGCS Revision Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking. Kế hoạch mặc định thực hiện tuần tự trong phiên chính; chỉ dùng subagents nếu được chọn riêng.

**Chronology cập nhật:** `todo.md` là yêu cầu ban đầu → người dùng sửa submitted thành `rev1.tex` với số liệu bịa → mentor đưa `todo-2.md`. File đang sửa là `rev1.tex`; không tạo manuscript mới để bỏ qua bản này. Phải loại claim không có bằng chứng trước khi tiếp tục E1–E6.

**Goal:** Hoàn thiện major revision có source/protocol/evidence truy vết được, đáp ứng reviewer và kế thừa bản submit tối đa.

**Architecture:** Đóng băng historical package trước; audit E1 rồi chỉ sửa/rerun phần E2–E4/E6 thực sự cần. Tách offline Kaggle, runtime integration và HIL; manuscript/response chỉ dùng claim đã xác minh.

**Tech Stack:** Python, Gymnasium, PyTorch, SB3/MaskablePPO, NumPy/pandas/SciPy, FastAPI, BMv2/P4/SRv6, Kubernetes/Tekton, LaTeX `elsarticle`. Pin phiên bản cụ thể sau khi đọc metadata; không ép SB3 2.3.2/2.8.0 thành một môi trường mà chưa kiểm tra model.

**Spec:** `docs/AIO-mesh-rev1/REVISION_DESIGN.md`; requirements: `review.txt`, `todo.md`, `todo-2.md`; source audit: `HARP_MODEL_CODE_AUDIT.md`.

## Global Constraints

- Historical source chung Vietnam/NSFNET/GEANT2: `HARP-model:CoreRouter/`; workflow chung tham chiếu `notebook/vietnam.ipynb`.
- Baseline paper: `docs/AIO-mesh-submitted 1/submitted-1.tex`; concept: `docs/thesis_JOVPPM/`; mọi chỉnh paper ở `docs/AIO-mesh-rev1/`.
- Không đổi số submitted để khớp kỳ vọng. Số mới phải nối được tới raw evidence; aggregate/user-reported chỉ giữ đúng nhãn nguồn.
- Không sửa historical snapshot, kết quả raw hoặc notebook lịch sử. Lưu revision outputs riêng dưới `results/rev1/`.
- Không chạy benchmark/training dài local; không thay HIL bằng Kaggle simulator.
- Không mặc định checkbox `[x]` trong todo là evidence. Không áp config Vietnam cho mạng khác khi chưa audit.
- Không mở rộng full-chain/K-cache/distributed freshness như phạm vi mặc định; nếu thiếu thì thu hẹp claim và giải trình.
- Preserve working tree, notebook moves và source refactor. Trước execution dùng isolated workspace có đủ inputs; commit theo task bằng đường dẫn cụ thể, không commit kết quả chưa audit.

## Review Focus

1. Thiếu model/normalizer hoặc sai topology/action head phải fail rõ; không fallback checkpoint, all-zero metrics hay tự train rồi gọi là reproduction — Task 2.
2. Cùng evaluation seed nhưng khác request trace không phải paired evidence; phát hiện trace-hash khác và từ chối ghép thống kê — Task 4.
3. Mask rỗng, concurrent requests và release/MBB phải bảo toàn reservation; MSD mỗi list không được đánh đồng với tài nguyên cộng dồn — Task 3.
4. Failed/missing runs, zero denominator, duplicate artifacts và all-zero paired differences không được tạo significance/acceptance giả — Tasks 1, 4, 5.
5. Simulation timing, API decision timing và actuation/HIL phải có nhãn môi trường riêng; không cộng component P95 hoặc suy throughput từ 1/P95 — Tasks 6, 7.

## Tình trạng đầu vào đã kiểm tra

| Có bằng chứng hiện tại | Chưa được xác nhận |
| --- | --- |
| Snapshot HARP-model `1badfd4`: 815 file; manifest/hash; main v11 ba mạng; 40 intermediate NSFNET ablation checkpoints | Checkpoint ablation Vietnam/GEANT2 đã dùng khi chạy; exact Kaggle dataset/version và training overrides ba mạng |
| Raw ablation 90 hàng + benchmark 60 hàng cho Vietnam và NSFNET; GEANT2 có 17 evaluation artifacts và aggregate | Full GEANT2 per-seed coverage; tính tương đương toàn bộ bảng paper với raw files |
| Main trainer/evaluator/policy/agent/state-manager khớp source lịch sử trong audit | Runtime compatibility, full-chain soundness, protected paired study, fresh statistics/scalability/HIL |
| Notebook lịch sử và source chung được người dùng xác nhận | Notebook có saved outputs/run metadata; không có trong bản notebook đã kiểm tra |

`todo.md` đã được người dùng cập nhật về yêu cầu ban đầu. `rev1.tex` hiện đã có và là draft phải sửa. Người dùng xác nhận các số mới trong draft trước phục hồi đã được bịa; các dấu hoàn tất của `todo-2.md` đã reset để không nhầm với evidence. Một số notebook được nhắc trong tài liệu cũ chưa có trong workspace. Template submitted là `elsarticle`.

## Chặng 0 — Phục hồi integrity (đã bắt đầu)

- [x] Backup draft/checklists/plan trước sửa và ghi hash.
- [x] Gỡ claim 20-seed/significance, HIL 24h/injection và timing/scalability không có evidence.
- [x] Bỏ mô tả full-chain realization/validation không có trong source.
- [x] Tính lại descriptive historical Vietnam/NSFNET bằng raw per-seed CSV, không gọi là revision experiment.
- [x] Lập evidence ledger, result map và status; reset completion ticks cũ.
- [ ] Hoàn tất các chặng E1–E6 bên dưới; không suy từ việc sửa draft rằng experiments đã xong.


## Task 1 — Lập evidence ledger và đối soát submitted (E1–E6, mọi reviewer)

**Files:** Create `docs/AIO-mesh-rev1/EVIDENCE_LEDGER.csv`, `SUBMITTED_RESULT_MAP.md`, `REVISION_STATUS.md`; đọc submitted, hai todo, review, manifest và `results/ablation/HARP-model/`.

**Interfaces:** Ledger gồm `concern_id, claim_id, manuscript_label, source_path, config_path, model_sha256, data_sha256, raw_path, seeds, status, gap, next_action`. `status` chỉ gồm `verified_historical`, `source_verified`, `user_reported`, `missing`, `needs_rerun`, `verified_revision`, `not_applicable`.

- [ ] Map toàn bộ table/figure và headline numbers của submitted, gồm simulation, burst, Vietnam ablation, Pareto, load sweep và testbed; ghi topology/scenario/variant/metric, mẫu số và rounding.
- [ ] Inventory configs/training metadata theo mạng; điền giá trị biết được, đánh dấu thiếu thay vì đoán training budget từ tên topology.
- [ ] Đối soát raw ↔ aggregate ↔ paper; phát hiện duplicate SHA-256 (đặc biệt GEANT2 chaos/heavyTail), thiếu seed/failed run và std `ddof` khác nhau.
- [ ] Đọc input files để phân biệt kết quả historical với các số “attachment/new results” mà todo nhắc tới; không nhập số chỉ có trong văn bản todo.
- [ ] Xuất coverage matrix cho E1–E6/P0.1–P0.8/P1.1–P1.7 và danh sách chỉ phần nào thật sự phải rerun.
- [ ] Nghiệm thu: mỗi label và concern có một row hoặc gap cụ thể; duplicate/thiếu raw không được gắn `verified_revision`. Kiểm tra CSV schema/unique claim ID, `git diff --check`; commit riêng ledger/docs.

## Task 2 — Khóa protocol và artifact compatibility (chặn trước E2/E3)

**Files:** Create `configs/rev1/protocol.json`, `scripts/rev1/check_artifacts.py`, `tests/rev1/test_artifact_contract.py`; tham chiếu `src/analytics/benchmark/benchmark_algorithm/{config,model_loader}.py`, `src/analytics/ablation_study.py`, `src/ai/dgrl_agent.py`.

**Interfaces:** CLI `python scripts/rev1/check_artifacts.py --protocol configs/rev1/protocol.json --output results/rev1/preflight.json`; exit 0 khi mọi input bắt buộc khớp, nonzero khi thiếu/mismatch. Protocol khai báo riêng `historical`/`revision`, topology, train/eval seeds, resolved model/normalizer paths/hashes, dataset/source hash, action/observation specs và dependencies.

- [ ] Viết test missing normalizer, wrong topology/obs dimension, `MultiDiscrete` v11 main vs flat `Discrete(N²)` ablation, MLP/GAT variant và action head sai; chạy `python -m pytest tests/rev1/test_artifact_contract.py -q` để xác nhận test fail trước implementation.
- [ ] Implement preflight đọc metadata/weights trong môi trường phù hợp, kiểm tra main-model và ablation checkpoint độc lập; không tự reshape action head hoặc dựng lại weights để che mismatch.
- [ ] Loại bỏ phụ thuộc auto-selection cho revision: pin resolved model/normalizer cụ thể, vì main config ưu tiên ablation `harp_full` khi file xuất hiện. Nếu cần adapter lịch sử, lập task nhỏ với mapping và equivalence test trước khi dùng; chưa đạt thì ghi reproduction gap.
- [ ] Khóa versions dựa trên metadata, xuất environment lock. Thiếu checkpoint cũ: tìm trong artifact có sẵn trước; train lại được ghi `new training`, không gán là model đã dùng cho submitted.
- [ ] Test pass và preflight output có đủ hash, topology/variant, spaces, package info. Không đòi preflight lịch sử pass khi input thực sự thiếu; nó phải báo đúng gap.
- [ ] Commit protocol/checker/tests, không thay binary historical.

## Task 3 — E1: Chốt semantics, sửa predicate sai và scope manuscript (P0.4/P0.7/P0.8)

**Files:** Audit/modify khi cần `src/core/state_manager.py`, `src/ai/dgrl_agent.py`, `src/orchestration/jo_vdpr/{env,topology,rewards}.py`, `src/portal/backend/app/services/hybrid_decision.py`, `src/infrastructure/sdn/p4_controller.py`; extend `tests/test_state_manager.py`, `tests/test_hybrid_decision.py`, `tests/test_orchestration_api.py`; create `docs/AIO-mesh-rev1/SEMANTICS_CONTRACT.md`, `tests/rev1/test_admission_semantics.py`.

**Interfaces:** Giữ API `try_reserve(v_place, v_route, cpu_req, ram_req, msd_req, vnf_name=None)` cho caller hiện hành nếu đủ; contract phải tách depth của realized list khỏi CPU/RAM occupancy và nêu rõ state representation trước khi đổi API. Không triển khai chain API mới mặc định.

- [ ] Truy policy pair → SID helper → controller → forwarding, đối chiếu simulation/runtime. Lập bảng node features `6N`, context `13`, normalize/freeze/clipping và request fields không có trong observation.
- [ ] Viết failing tests cho reservation placement=route, routing-only/reuse, capacity reject, concurrent overbooking, release/idempotency và MBB peak occupancy. Audit lỗi cộng dồn MSD hiện tại: hai request riêng có SID depth hợp lệ không được bị từ chối chỉ do tổng depth; depth vượt profile phải reject dù occupancy trống.
- [ ] Quyết định predicate/spec sau trace audit; sửa tối thiểu nếu có lỗi, ghi tất cả benchmark/HIL artifacts chịu ảnh hưởng. Nếu model được train theo representation cũ, không tái sử dụng như tương đương mà thiếu migration/retraining validation.
- [ ] Test flat encode/decode, all-false mask → safe reject/search, HTTP 409, frozen normalizer và wrong-model rejection. Gate: `u=max(mean CPU, mean MSD)`, engage `u>0.45`/alert, release `u<0.35`/no alert; kiểm tra bằng/ngoài ngưỡng và giữ trạng thái trong hysteresis band.
- [ ] Xác minh telemetry age/version và lock scope. Ghi rõ local locking không đồng nghĩa atomic K8s/P4 transaction; không tự thêm distributed locking/TTL feature trong task này.
- [ ] Chỉ nhận full-chain claim nếu có ≥3-VNF integration trace gồm complete SID lists/profile và actual forwarding; mặc định mô tả request pair + limitation.
- [ ] Run `python -m pytest tests/test_state_manager.py tests/test_hybrid_decision.py tests/test_orchestration_api.py tests/rev1/test_admission_semantics.py -q`; kiểm tra output, commit semantics/tests/docs riêng. Gate E1: predicate đúng trong scope đã công bố, các claim còn thiếu evidence có disposition cụ thể.

## Task 4 — E2: Workloads, protected baselines, accounting và statistics (P0.1–3/P1.1)

**Files:** Modify `src/analytics/benchmark/benchmark_algorithm/{config,env_factory,algorithms,metrics,exporters,run_all,run_load_sweep}.py`, env nếu cần; create `src/analytics/benchmark/revision/{__init__,traces,statistics}.py`, `tests/rev1/{test_traces,test_accounting,test_statistics}.py`.

**Interfaces:** `build_trace(config: dict, seed: int) -> list[dict]` và `trace_sha256(trace: list[dict]) -> str`; mỗi record có request ID/arrival/source/destination/requirements/TTL/service class. `paired_statistics(rows: list[dict], config: dict) -> list[dict]` yêu cầu cùng topology/scenario/seed/trace hash và metric definition; returns delta percentage points, bootstrap CI95, paired Wilcoxon p, Holm p và rank-biserial, n/effective-n.

- [x] Pre-register protocol trước khi nhìn kết quả mới. Historical: 5 seeds `[42,100,2024,8888,9999]`, 3,000 evaluation steps. Revision evaluation khóa 20 seeds `[42,100,2024,8888,9999,7,17,73,314,2718,11,23,47,89,101,211,512,1024,4096,8192]`; giữ train seed riêng. Đây là kế hoạch chạy, chưa phải kết quả/evidence.
- [ ] Viết failing tests trace replay không phụ thuộc policy RNG; Elephant/Chaos config phải khác và không resolve cùng generator; test burst/load knobs thật sự thay arrival/demand. Chốt tham số generator trong `protocol.json` trước full run; không điều chỉnh để đạt chênh lệch HARP mong muốn.
- [ ] Dùng cùng candidate interface/admission cho HARP, SAF-H, Greedy, DAI; protected/unprotected chỉ là flag rõ ràng, unsafe variant chỉ chạy simulation. Trước tái sử dụng offline simulator phải kiểm tra nó có thực sự cung cấp protected variants; todo không chứng minh đã có.
- [ ] Log theo request: offered, candidate CPU/RAM/MSD failures (có thể chồng lấn), union, admission outcome, rejection class chính không trùng, safe admitted, deployment completion/failure khi thực sự có actuation. Offline `deployed` phải N/A; không gán admission là deployed.
- [ ] Test accounting identity trong vòng đời đã kết thúc, zero offered, failures, skipped arrivals, duplicate IDs, capacity/search failure và oracle nhỏ. Phân biệt safe acceptance/offered, unsafe candidates/evaluated candidates, admitted violation/admitted; report cả counts. Không suy rejection pressure bằng `100-safe acceptance` khi còn unsafe admission, skipped hoặc pending.
- [ ] Statistics: 10,000 paired bootstrap resamples, fixed analysis seed 20261116; hai phía, alpha 0.05; Holm trên 3 topology × 3 stress-profile HARP-vs-SAF-H primary comparisons nếu đủ 9 ô. Không xem 3,000 request steps là 3,000 independent experimental seeds; all-zero differences → CI [0,0], p=1, effect=0 và explicit flag; zero/ties giảm effective n phải được báo.
- [ ] Unit tests dùng fixture có known deltas/CI coverage, thiếu cặp/trace mismatch phải reject, NaN/failed run không impute 0. Run `python -m pytest tests/rev1/test_traces.py tests/rev1/test_accounting.py tests/rev1/test_statistics.py -q`.
- [ ] Load sweep 0.2–1.5× với các mức ghi rõ trong protocol, mọi protected baseline và CI. Oracle chỉ trên topology nhỏ, report missed-feasible riêng khỏi global infeasibility. Commit implementation/tests; full run thuộc Task 5.

## Task 5 — E2/E3: Notebook Rev1 và các lượt chạy Kaggle

**Files:** Create `notebook/rev1-benchmark-ablation-kaggle.ipynb`, `scripts/rev1/package_inputs.py`, `tests/rev1/test_result_coverage.py`; modify ablation trainer/evaluator/exporters chỉ nếu Task 1/3 xác định thiếu instrumentation; add protocol variant mapping.

**Interfaces:** Package manifest pin source/data/models; output mỗi run gồm `run_manifest.json`, `config_resolved.json`, `per_request.csv`, `per_seed_summary.csv`, `aggregate_summary.csv`, `paired_statistics.csv`, raw logs và checkpoint/normalizer export. Directory `results/rev1/<protocol-id>/<topology>/<run-id>/`; historical inventory riêng.

- [ ] Tạo notebook từ workflow đã xác nhận, tách stages inventory/preflight → smoke → historical check khi khả thi → full revision. Mỗi topology dùng cùng code, config rõ; không chọn “first matching package” hoặc merge model tùy ý từ inputs khác.
- [ ] Smoke 64 steps trên cả ba mạng: train tiny checkpoint khi chưa có compatible model, kiểm tra evaluator/runtime adapter nếu topology đó được runtime hỗ trợ; smoke không thay thế research result. Xuất lỗi skip/unavailable trung thực, không đánh dấu all-topology pass giả.
- [ ] E3 matrix: Full, MLP, NoMask, NoMask+Unchecked, NoAdapt, SoftMSD admission on/off; reuse cùng NoMask weights khi chỉ đổi boundary và ghi rõ model key. Không tự nhận có trained NoMigration variant nếu source chưa hỗ trợ.
- [ ] Audit reward sign trước train; log pruning candidates/valid actions, runtime rejections, infeasible CPU/RAM/MSD/union, convergence và overhead. Train mỗi variant/topology một lần theo train config; evaluation dùng matched traces, không train lại cho từng evaluation seed.
- [ ] Historical 5-seed đối soát Task 1 chỉ rerun phần thiếu và compatible. Nếu checkpoint thiếu, báo không thể tái lập đúng model; train mới gắn revision protocol. Fixed-workload evaluation dùng weights cũ khi compatible có thể làm paired control; fresh-training study phải ghi khác training distribution.
- [ ] Bật full stage thủ công sau khi ba smoke pass và E1/Task 4 gate đạt. Kiểm tra expected row count = thực tế topology × scenario × policy/variant × seeds, không gộp duplicate copies; test thiếu seed/failure bằng `python -m pytest tests/rev1/test_result_coverage.py -q`.
- [ ] Archive phải xuất cả models/normalizers (khắc phục thiếu export notebook lịch sử), source hash/config/deps/hardware metadata; tải về kiểm hash/CRC trước đánh dấu ledger `verified_revision`. Không upload/rerun Kaggle khi mới chỉ chuẩn bị notebook local.
- [ ] Đóng E2/E3 chỉ sau ingest/audit/statistics; commit notebook, tooling và evidence summary riêng, không coi training success là evaluation success.

## Task 6 — E4: Latency, scalability và concurrency (P0.5/P1.2/P1.3)

**Files:** Add `scripts/rev1/run_scalability.py`, `tests/rev1/test_timing_contract.py`; instrument `src/portal/backend/app/services/hybrid_decision.py`, router và state/mask/agent interfaces khi cần; output schema trong protocol.

**Interfaces:** Per-request timestamps bằng monotonic nanoseconds: arrival/start/state/mask/inference/admission/handoff/deployment/readiness/steer/complete. Field không đo có value null; records có environment/hardware/topology/active-load/concurrency/worker/warm-up metadata.

- [ ] Test timestamp order, missing stage, warm-up exclusion, failed requests và concurrent completion; đo total decision interval trực tiếp, actuation interval riêng. Không tổng các stage percentiles.
- [ ] Sweep topology 10/25/50/100 theo todo-2, thêm hai topology historical NSFNET/GEANT2 làm anchor; topology tổng hợp phải có seed/connectivity/load normalization. 200 nodes là mở rộng tùy chi phí, không thay requirement 100 nodes bằng extrapolation.
- [ ] Chốt 3 mức active-request occupancy và concurrency `[1,4,16]` trước run, với queue policy/worker count explicit. Không gọi pair-level active flows là multi-VNF chains nếu chưa có realization.
- [ ] Fixed-size policy không được padding hoặc đổi adjacency ngầm cho N mới. Dùng checkpoint tương thích/newly trained hoặc hạn chế thí nghiệm thành mask/admission-only và ghi rõ; bao gồm chi phí/memory N² mask.
- [ ] Kaggle CPU timing và API/testbed timing báo riêng, GPU nếu có tách riêng. Throughput = completed operations / measured elapsed time; report p50/p95/p99, CPU/RAM, queue/drop rates, sample count.
- [ ] Unit contract pass, raw timing + config/hardware audit đạt mới đóng E4. Nếu chưa có measurement, giữ limitation và response không gọi là đã đo.

## Task 7 — E5 có điều kiện và E6 testbed evidence

**Files:** Create `docs/AIO-mesh-rev1/HIL_PROTOCOL.md`; audit `src/analytics/benchmark/benchmark_testbed/`, `src/infrastructure/{sdn,k8s}/`, P4 sources và deployment manifests hiện có; chỉ thêm runner/instrumentation tại module đang sở hữu hành vi.

**Interfaces:** HIL records join request ID ↔ admission ↔ deployment ↔ readiness ↔ steering ↔ forwarding evidence; archive includes configs, versions, per-hour logs, captures/counters và timings.

- [ ] E5 default: nếu không có K-cache trong runtime cuối, bỏ claim/table/figure K-cache từ code khác, giải thích reviewer; không chạy K-sensitivity giả. Nếu audit tìm cache thực: khóa cùng source rồi mới lập config K `[1,3,5,10,20]` + missed-feasible oracle/memory/timing.
- [ ] Audit trước xem HIL logs thật có hỗ trợ con số 25,000/17,820/5,910/1,270 trong checklist không. Không lấy tổng đúng số học làm bằng chứng thí nghiệm; cần timestamps/request IDs/source/hardware.
- [ ] Lập runbook tối đa 24h nếu cần và testbed sẵn có; thu offered/deployed/rejects/errors/migrations, per-hour drift và telemetry gaps. Nếu chỉ có thời lượng ngắn, report thời lượng thật và limitation, không ghi 24h.
- [ ] Controlled SID depth 7 > MSD 4 chỉ trong testbed kiểm soát: trace admission và bypass diagnostic riêng, ghi target P4/BMv2 behavior/counter deltas/pcap; không suy sang ASIC production.
- [ ] MBB phải có readiness → steer confirmation → break và packet timeline; nếu thiếu forwarding evidence, không claim zero downtime. Simulator/Kaggle không đóng E6.
- [ ] Có fixtures/harness thì test trước khi chạy live; chỉ chạy long HIL sau khi preflight endpoints và config đúng. Commit runbook/instrumentation; ingest evidence rồi cập nhật ledger, hoặc ghi limitation thay vì tick complete.

## Task 8 — Manuscript, figures, response và resubmission gate

**Files:** Modify `docs/AIO-mesh-rev1/rev1.tex` (draft hiện có); historical submitted giữ nguyên, `RESPONSE_TO_REVIEWERS.md`, `figs/`, `scripts/rev1/render_paper_results.py`; modify revision `refs.bib`; historical documents giữ nguyên.

**Interfaces:** Renderer chỉ đọc artifact có ledger status hợp lệ và protocol/model/trace identifiers; emits `.tex` table fragments, figures và `paper_result_manifest.json` nối input hash ↔ output file ↔ manuscript label. Nội dung diễn giải bắt nguồn từ accepted claim/evidence map.

- [ ] Sửa draft hiện có `rev1.tex`, giữ nội dung định vị lại hợp lý; loại số liệu/claim bịa và đối chiếu lại với submitted/raw evidence; giữ template `elsarticle`. Chuẩn bị figures/bib bằng paths thật, phân biệt `Figs`/`figs` trên Linux.
- [ ] Có thể chuẩn bị prose sớm sau E1: Abstract/Introduction/Related work/Architecture runtime-first; action pair vs general chain; hard constraints ↔ failure modes; mask frequency/normalization/gate/TOCTOU/safety limitations. Dùng `%NNH: cần hoàn thiện sau khi thực nghiệm [E1–E6]: ...` trong draft đúng concern, chưa xóa trước audit.
- [ ] Rework overview/testbed figures thể hiện Policy/Heuristic → independent Admission → Actuation; chỉ vẽ freshness/cache khi implemented. Table/figure numbers chỉ thay sau Tasks 4–7; lịch sử không bị xóa chỉ vì chưa có rerun.
- [ ] Đối chiếu và cập nhật simulation/burst/ablation/Pareto/load-sweep/HIL cùng prose phụ thuộc chúng; statistical significance chỉ khi CI/test/adjusted p hỗ trợ. Giữ kết quả HARP thua/hòa SAF-H nếu đó là evidence.
- [ ] Related-work table: kiểm từng nguồn trước khi đánh independent admission/MSD; ở bước thực hiện tra primary papers và lưu citation note. Rà abbreviations, rút conclusion khoảng hai đoạn, tách BMv2 khỏi carrier-grade claims.
- [ ] Response theo từng comment R1–R5, gồm thay đổi, vị trí section/label/page sau build, evidence và limitation. Không trả lời concern bằng checkbox hoặc nhận định chưa kiểm chứng.
- [ ] Build `latexmk -pdf -interaction=nonstopmode -halt-on-error rev1.tex` tại revision folder khi toolchain có sẵn; workspace hiện chưa thấy `latexmk`/`pdflatex` trên PATH. Nếu chưa cài được, chuẩn bị package và dùng môi trường LaTeX phù hợp; không claim compile pass.
- [ ] Nghiệm thu PDF: không missing assets/citations/references, không unresolved `%NNH`/TODO/TBC, không tràn bảng; số liệu/prose/figures/response nhất quán. PDF nhìn trực tiếp các trang bảng/hình; `git diff --check` chỉ là kiểm bổ trợ.
- [ ] Commit từng nhóm source → notebook/protocol → evidence → manuscript/response, review diff với baseline; không tự submit journal/publish. Cập nhật `REVISION_STATUS.md` và tick todo tương ứng chỉ khi evidence gate đạt.

## Thứ tự triển khai và giới hạn hiện tại

1. Task 1 và 2 chuẩn bị evidence/protocol; Task 3 chốt E1 trước full evaluation.
2. Task 4 → Task 5 đóng E2/E3; chuẩn bị prose Task 8 có thể thực hiện khi E1 đã chốt, nhưng chưa thay kết quả thiếu evidence.
3. Task 6 đóng E4; Task 7 xử lý E5/E6 theo bằng chứng/testbed; Task 8 tích hợp cuối.

Đầu ra phục hồi đã tạo: `EVIDENCE_LEDGER.csv`, `SUBMITTED_RESULT_MAP.md`, `REVISION_STATUS.md`. Tiếp theo là khép contract E1 và artifact compatibility trước full Kaggle run. Không mặc định cần train lại toàn bộ. Khi audit xác định số liệu đủ bằng chứng, giữ lại; khi workload/predicate/accounting sai, rerun đúng phần bị ảnh hưởng và ghi khác protocol.

## Self-review của kế hoạch

- E1 ↔ Task 3; E2 ↔ Tasks 1/2/4/5; E3 ↔ Task 5; E4 ↔ Task 6; E5/E6 ↔ Task 7; manuscript/response ↔ Task 8.
- P0.1, P0.2, P0.3 ↔ Task 4; P0.4, P0.7, P0.8 ↔ Task 3; P0.5 ↔ Task 6; P0.6 ↔ Task 7. P1.1 ↔ Task 4; P1.2, P1.3 ↔ Task 6; P1.4, P1.5 ↔ Task 7; P1.6 ↔ Task 5; P1.7 ↔ Task 8.
- Training budget theo từng mạng, exact original run-time commit và missing checkpoints vẫn là audit inputs của Task 1/2; không âm thầm gán defaults lịch sử.
- Đây là kế hoạch, không phải báo cáo hoàn tất E1–E6. Đã sửa `rev1.tex` và công cụ audit lịch sử; chưa sửa runtime, train hay chạy experiment mới. Trạng thái chi tiết ở `REVISION_STATUS.md`.
