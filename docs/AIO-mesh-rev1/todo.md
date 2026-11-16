# AIO-Mesh FGCS Major Revision — TODO

## Mục tiêu của vòng revise

Bản revise phải tách rõ hai lớp đóng góp: **(i) runtime safety contract của AIO-Mesh** là nguồn của thuộc tính fail-closed trước actuation; **(ii) HARP** là một policy có thể thay thế, có nhiệm vụ cải thiện chất lượng/hiệu quả của candidate actions. Không tiếp tục diễn đạt PPO, GAT hoặc invalid-action masking như các thuật toán mới. Claim về safety chỉ giới hạn trong các hard constraints đã mô hình hóa (CPU, memory, SRv6 MSD) và trạng thái mà controller quan sát được.

## Trạng thái hiện tại và nguồn sự thật

### Đã có

- `submitted.tex` là **baseline số liệu hiện hành** của paper. Giữ nguyên các số này khi rà soát; chỉ thay sau khi tái chạy, đối chiếu seed/config và xác nhận artifacts.
- `thesis.tex` là **nguồn concept và lý thuyết** để mở rộng paper: mô hình substrate/SFC, hard và soft constraints, MDP/action, GAT/MaskablePPO, migration/MBB, kiến trúc runtime và HIL. Không lấy các số liệu hay claim thực nghiệm trong thesis làm kết quả mới nhất nếu chúng khác submitted.
- `AIO-Mesh.rev1.tex` đã có phần định vị lại novelty theo hướng runtime-first, HARP là policy instance, phân biệt policy mask với admission boundary, cùng nhiều đoạn bổ sung về MSD, safety scope, evaluation questions và limitations. Các phần này là bản nháp, chưa được xem là xác nhận của implementation.
- Benchmark config cũ đã từng ánh xạ `elephant_stress` sang `heavy_tail`; hiện `chaos` đã có nhánh generator riêng gồm burst peak và heavy-tail draw. Đây mới là bước tách profile trong simulation env, chưa phải rerun và chưa có kết quả revision.
- Notebook `notebook/harp-ablation-nsfnet.ipynb` hiện train các ablation variants rồi đánh giá 3 workload bằng 5 seeds; code benchmark cũ nằm lẫn trong notebook nhưng dùng evaluator/action-space khác. Không gộp kết quả hai evaluator vào cùng một bảng.
- Đã kiểm tra thư mục `kaggle/results_kaggle` trong workspace: có benchmark algorithm NSFNET cho 3 workload (`elephant_stress`, `burst_surge`, `chaos`) × 4 thuật toán × 5 seed (60 dòng); ablation có raw NSFNET 3 workload × 6 variant × 5 seed (90 dòng), cùng summary 5-seed cho cả NSFNET/GEANT2/Vietnam (18 hàng/topology). Các artifact này là kết quả lịch sử để đối chiếu, chưa được xác nhận tái lập theo source/protocol Rev1 và không thay thế rerun.
- Snapshot `CoreRouter` trong `kaggle/results_kaggle` còn chứa kết quả testbed 2026-05-17, checkpoint/model, dữ liệu và mã nguồn cũ. Không nhập chúng vào kết quả notebook mới; nếu cần dùng trên Kaggle, gắn folder như dataset riêng để notebook chỉ inventory/hash.
- Đã tạo `notebook/rev1-benchmark-ablation-kaggle.ipynb`: smoke trên ba topology trước, full run bật thủ công sau khi smoke pass; notebook train checkpoint mới từ source snapshot hiện hành, hỗ trợ 10 seed và ghi manifest/hash. Notebook chỉ inventory folder `results_kaggle` nếu folder đó được attach vào `/kaggle/input`; chưa có cell nào được chạy trên Kaggle.
- Code hiện có action simulation dạng cặp `(place, route)` trên không gian (N^2), observation gồm 6 node features và 13 phần tử request/service/global-context, cùng GAT hai lớp. Cần mô tả đúng pipeline cụ thể của từng experiment/model thay vì suy rộng từ thesis.
- Đã thêm bảng đặc tả 6 node + 13 global features dựa trên `src/core/state_manager.py`; nêu rõ `VecNormalize` running mean/variance và các trường SLA/priority/src-dst/active-VNF/TTL/PPS không phải phần tử riêng của vector đang audit. Bảng constraint mô tả hậu quả vận hành có điều kiện; không gán mức giảm throughput 50% cho recirculation vì testbed BMv2 chưa đo hiệu ứng ASIC đó.
- Đã chuẩn hóa bố cục các bảng Rev1 theo quy ước IEEE hai cột: caption phía trên, `booktabs` không kẻ dọc, bảng nhiều cột dùng `table*`, bỏ co toàn bảng bằng `resizebox` và tăng cỡ chữ cho bảng kết quả. Cần compile PDF ở template nộp cuối để kiểm tra float placement và xác nhận không bảng nào tràn lề.

### Chưa có / chưa xác nhận

- Chưa có lượt rerun nào được hoàn tất cho revision này; chưa có paired protected-baseline study, significance analysis, latency/scalability, K-sensitivity hay long-running HIL mới. Các output đã có trong `kaggle/results_kaggle` vẫn là historical artifacts, chưa audit đủ provenance để thay số submitted.
- Các con số trong thesis khác submitted ở một số phần và không thay thế baseline submitted.
- Semantics chain nhiều VNF so với action `(place, route)`, cách tính full SID list/MSD, mask-empty behavior, telemetry freshness/TOCTOU, và chính xác hybrid gate cần được xác minh từ runtime và artifacts trước khi mô tả như tính năng đã triển khai.
- Draft còn các `REVISION TODO`, kết quả lặp Elephant/Chaos, câu chữ ở thì tương lai và các chỗ cần cập nhật sau khi có số mới.

### Quy tắc làm việc

1. Đối chiếu claim/công thức từ thesis với code; chỉ đưa vào Rev1 khi khớp implementation hoặc ghi rõ đó là mô hình khái quát/limitation.
2. Tái tạo kết quả submitted trước để xác nhận baseline; sau đó chạy các thí nghiệm mới reviewer yêu cầu. Mọi bảng/figure sửa phải truy được về config, seed và result artifact.
3. Không tự điền số ước lượng vào paper. Nếu experiment không thể chạy, nêu rõ giới hạn và thu hẹp claim tương ứng.

## Thứ tự công việc tiếp theo

1. **Audit và khóa protocol**: lập mapping từng bảng/figure submitted tới script, config, model checkpoint, seeds và artifacts; xác định phiên bản code/runtime đang đại diện cho paper.
2. **Chốt semantics hệ thống**: xác minh chain/action/anchor/SID/MSD, admission, mask rỗng, hybrid predicate, feature normalization và telemetry freshness. Sửa mô hình và công thức trong Rev1 cho đúng trước khi chạy experiment phụ thuộc chúng.
3. **Tái lập baseline**: chạy lại kết quả chính submitted theo đúng topology/scenario/baseline hiện có; so sánh với số đã công bố và ghi nguyên nhân mọi sai lệch.
4. **Sửa và chạy evaluation bắt buộc**: tách Elephant/Chaos thành workload thật sự khác nhau hoặc bỏ một profile; chạy cùng admission boundary cho các policy; dùng matched seeds và thống kê; cập nhật load sweep.
5. **Bổ sung operational evidence**: đo decision-latency breakdown, scalability theo topology/chain/concurrency và K-sensitivity; thực hiện HIL dài hạn/controlled over-MSD nếu testbed và thời gian cho phép.
6. **Hoàn thiện paper**: tích hợp concept/công thức đã xác minh, thay toàn bộ số liệu/prose/hình bằng kết quả đã audit, xóa TODO/placeholder, rà abbreviation và rút gọn conclusion.

## Lộ trình resubmit sớm (số liệu mới nhận, cần audit artifact)

Người dùng xác nhận dùng bộ trong attachment: benchmark chính giữ thang safe-acceptance của submitted, Chaos HARP là 18.12% (người dùng xác nhận đây là kết quả thực nghiệm); HIL giữ các tỷ lệ submitted và thêm các hàng Greedy/DAI Protected; ablation Heavy-Tail/Bursty giữ safe-acceptance của submitted và bổ sung candidate infeasibility. Các bảng đã chuyển về bộ này, thay cho bộ bảng gửi ngay trước attachment. Raw artifacts/seeds vẫn cần audit. K-cache và scalability từ số liệu gửi trước đó vẫn được ghi riêng; K-cache thuộc source tree khác workspace hiện tại. Không tự nội suy hoặc tuyên bố ý nghĩa thống kê từ số tổng hợp.

Thứ tự tối thiểu trước khi gửi:

1. Hoàn tất phần có thể làm bằng code/text: novelty runtime-first; action/feature/gate/mask đúng implementation; giới hạn chain-level, K-cache và stale-state nói thẳng; xóa claim migration/path reconstruction không được code hỗ trợ; rút ngắn conclusion và rà abbreviation.
2. Chạy smoke notebook trên Kaggle và chỉ dùng nó để xác nhận pipeline/checkpoint compatibility. Nếu không đủ thời gian cho full rerun, đừng trình bày smoke như validation thực nghiệm.
3. Đối chiếu số liệu mới với raw outputs: run manifest, source commit cho benchmark và source tree riêng của K-cache, config, seeds, phần cứng, mẫu số và định nghĩa metric. Candidate infeasibility trong ablation dùng mẫu số candidate actions; xác minh nốt mẫu số của rejection/acceptance, statistic của ±, fixed Chaos generator, paired seeds/CI và raw HIL logs cho các hàng Protected bổ sung. Nếu artifact chưa có, giữ bảng xanh ở trạng thái user-reported/preliminary.
4. Trước khi nộp, rà toàn văn để không còn thì tương lai (“will report”), TODO kỹ thuật, placeholder lộ ra trong bản PDF, hoặc khẳng định “significant/superior/zero-violation” vượt khỏi đúng tập thí nghiệm đã chạy.

Không nên chọn trước một mức chênh lệch HARP–SAF-H rồi cố làm kết quả khớp. Một kết quả thuyết phục cần báo chênh lệch theo **percentage points** trên cùng seed/trace, paired 95% CI, paired test đã chọn trước, effect size và hiệu chỉnh Holm nếu có nhiều comparison. Hãy diễn giải: (a) khoảng tin cậy có loại trừ 0 hay chưa; (b) độ lớn có ý nghĩa vận hành so với biến thiên/chi phí hay không; (c) dấu hiệu có ổn định qua topology/workload hay chỉ xuất hiện ở một ô; và (d) safety/admitted-violation có giữ nguyên dưới cùng admission boundary không. Nếu CI rộng hoặc chứa 0, mô tả là chưa kết luận được; không đặt một ngưỡng phần trăm hậu nghiệm để gọi là “đủ thuyết phục”.

Các task dưới đây là checklist chi tiết của các bước này. Trạng thái mặc định là **chưa làm trong vòng revision** trừ khi được ghi rõ ở mục “Đã có”.

### Nhật ký thực hiện P0

- **Đã nhận số tổng hợp mới từ người dùng:** benchmark Vietnam Elephant/Burst/Chaos, NSFNET/GEANT2 Elephant/Burst; ablation Heavy-Tail/Bursty; HIL năm kịch bản; scalability 10–100 nodes; cache K=1,3,5,10,20 từ source tree riêng. Đã nhập vào `AIO-Mesh.rev1.tex` màu xanh lá, giữ nguyên giá trị được gửi. Candidate infeasible ablation dùng mẫu số candidate actions. Còn thiếu artifact/provenance, seeds/variance, request-level metric definitions, raw logs cho Protected baselines, xác minh fixed Chaos generator và lineage của cache-enabled tree. P0 hiện ở trạng thái *đã nhập số, chờ audit*, chưa complete.


- **P0.1 — đã nhận bảng kết quả, audit source/artifact pending:** bảng chọn hiện ghi Chaos (Fixed Generator) với HARP safe acceptance 18.12%; người dùng xác nhận đây là số thực nghiệm. Workspace environment hiện định nghĩa Chaos khác; ghép source/config/seed của fixed generator với run artifact trước khi đóng P0.1.
- **P0.2 — đã nhận protected/unprotected benchmark và HIL summary, audit pending:** bảng được chọn giữ nguyên acceptance/violation submitted và thêm Greedy/DAI Protected; cần xác minh các hàng bổ sung có run logs thật, cùng traces và admission code, trước khi kết luận về boundary.
- **ACTION-COMPAT — source alignment implemented; Kaggle smoke pending:** env/trainer/evaluator/runtime share flat `Discrete(N*N)`, a pairwise `N²` mask, topology-sized observation and adjacency checks, and matching feature construction. The new notebook trains fresh checkpoints and calls the production runtime adapter on all three topologies. Historical `MultiDiscrete` checkpoints remain incompatible and are not used. Close this engineering blocker only after all three runtime smoke runs pass.
- **P0.4 — manuscript scope narrowed; implementation gap remains:** Rev1 now distinguishes the general chain-level system model from the actual request-level placement--routing pair. The policy does not emit a complete multi-VNF mapping or operation mode; the local pair checks do not prove a fully expanded chain SID list. A full-chain claim requires corresponding controller implementation and a >=3-VNF integration trace; otherwise keep the narrowed claim.
- **P0.7 — code audit and manuscript correction prepared:** the gate uses `u=max(mean CPU utilization, mean MSD utilization)`, engages DRL at `u>0.45` or active alert, and releases at `u<0.35` with no active alert. `choose_mode` has no averaging/dwell window. Rev1 now states this predicate; verify mode transitions in the runtime smoke before closing.
- **P0.8 — implementation limitation documented:** observation features and normalizer contract are aligned; local `try_reserve` checks and updates state under a process lock. There is no telemetry version/TTL or atomic transaction spanning Kubernetes/P4 actuation. Rev1 states this boundary. Close only the documentation part unless freshness/versioning/actuation transaction is implemented and measured.
- **P0.6 — có số K-sensitivity từ source khác:** source tree riêng được người dùng xác nhận; còn audit commit, implementation, manifest, và relationship với benchmark source chính. Không gán số liệu này cho runtime source hiện tại.

### Source-code checklist đã đối chiếu (2026-11-09)

Các kết luận dưới đây là source audit, không phải xác nhận thực nghiệm hay HIL. Chi tiết đường dẫn và giới hạn nằm ở `todo_2.md`, mục “Source-code audit”.

- **Đã xác nhận trong source:** action `(place, route)` trên `Discrete(N²)`; codec nhất quán; observation `6N+13`; runtime pair mask; local CPU/RAM/MSD admission dưới process lock; empty runtime mask chuyển safe search; hard rejection trả HTTP 409; hybrid hysteresis predicate; MBB orchestration có readiness polling và steer confirmation trước break.
- **Đã chốt phạm vi claim:** request/runtime hiện chọn một placement-route pair và tạo SID list bounded từ request `msd_req`; chưa có full multi-VNF chain mapping/trace. Safety evidence của source chỉ là local pre-actuation admission trên controller-visible CPU/RAM/MSD state, không gồm link capacity, telemetry freshness/versioning, hay transaction nguyên tử với Kubernetes/P4.
- **Chưa có trong runtime tree:** candidate-path K-cache, telemetry TTL/version, distributed reservation, API stage-level latency/concurrency instrumentation. Không coi summary từ source tree khác là source evidence hiện tại.
- **Có code nhưng chưa đủ bằng chứng:** benchmark simulator có protected baselines, per-request fields, decision latency và summary; MBB có readiness/steer flow; P4 tree có MSD enforcement source/test. Cần raw manifests/logs, packet traces và đúng source/config lineage trước khi dùng làm bằng chứng kết quả.
- **Không đánh dấu đã hoàn tất:** matched-seed rerun, paired statistics, request accounting đối chiếu deployment, multi-VNF integration trace, K-cache audit, latency/scalability measurement, HIL 24h, controlled over-MSD packet evidence. Các việc này cần artifacts hoặc chạy thực nghiệm, không thể hoàn tất bằng đọc/sửa source.

**Commit plan:** phần runtime empty-mask fail-closed được tách commit source riêng; hai checklist được tách thành hai commit tài liệu riêng. Các thay đổi manuscript/notebook/figures đang có trong worktree không thuộc các commit này.

## Kế hoạch chạy lại trên Kaggle (không chạy benchmark local)

### Kế hoạch hành động và đầu ra gắn với P0

| Chặng | Việc làm / artifact đầu ra | P0 được giải quyết khi artifact được kiểm tra |
|---|---|---|
| A. Chuẩn hóa implementation (local code) | Action codec `a=v_place*N+v_route`; runtime mask `N²`; agent kiểm tra `Discrete(N*N)`, observation/normalizer/adjacency theo topology; feature construction khớp trainer; all-false mask chuyển sang safe search/HTTP 409 nếu hết cặp; notebook smoke gọi runtime agent và kiểm tra gate trên cả ba topology, ghi `runtime_action_smoke.csv`. | Đóng engineering blocker ACTION-COMPAT và xác nhận smoke behavior sau khi Kaggle chạy pass; hỗ trợ benchmark rerun nhưng chưa giải quyết P0.3 significance nếu chưa có >=10 matched seeds và thống kê. |
| B. Main benchmark và strict ablation (Kaggle) | Full checkpoint HARP/variants theo topology; benchmark per-seed cho `thesis` gồm normal, Elephant, Burst, Chaos; strict ablation per-seed cho uniform/bursty/heavy-tail; manifest/source/data/checkpoint hashes; paired Wilcoxon, bootstrap CI, rank-biserial, Holm. | P0.1 sau khi Elephant/Chaos khác profile và đủ artifacts; reviewer P0.3 sau khi đủ matched seeds/statistics. |
| C. Protected baseline study (Kaggle CPU simulation) | Cùng trace/seed chạy candidate policy × admission protection; per-request CSV, rejection reason, candidate hard-infeasible, safe acceptance, admitted violation, latency. Đây là offline software simulation, không phải HIL. | P0.2 khi so sánh đủ policy variants qua cùng admission boundary và báo metrics yêu cầu. |
| D. Code audit + manuscript corrections (local) | Rev1 được bổ sung màu xanh cho action `Discrete(N²)`, encode/decode, feature vector `6N+13`, gate hysteresis, pair-vs-chain semantics, mask/reservation boundary và giới hạn K-cache/migration claims. | Chuẩn bị câu trả lời P0.4/P0.7/P0.8 bằng thu hẹp claim; P0.4 còn cần xác nhận controller semantics. P0.6 có sensitivity summary từ source tree riêng; audit lineage và khả năng đối chiếu với benchmark source chính còn pending. |
| E. Operational measurements (Kaggle/code instrumentation) | Bổ sung breakdown timing state/mask/inference/admission/controller; sweep topology/request concurrency; xuất p50/p95/p99 và decisions/s. | P0.5 sau khi instrumentation và kết quả scalability được audit. |

Không có artifact Kaggle nào tự giải quyết được P0.4/P0.6/P0.7/P0.8 nếu semantics hoặc tính năng tương ứng chưa có trong runtime; khi đó phải sửa code hoặc giới hạn claim paper.

### 0. Đóng băng input và smoke check

1. Tạo một Kaggle Dataset/version duy nhất chứa source snapshot và `data/real_telecom_combined.csv`, kèm manifest ghi Git commit/source SHA-256. Notebook mới tự train checkpoint smoke/full; không cần đóng gói checkpoint v11 cũ. Nếu cần đối chiếu lịch sử, attach `kaggle/results_kaggle` thành dataset riêng để inventory/hash, không trộn `results/` vào source snapshot.
2. Dùng một notebook worker cho mỗi topology: `nsfnet`, `vietnam`, `geant2`. Cùng Python/package versions, cùng topology data, cùng workload configs và seeds.
3. Chạy smoke stage trong notebook mới trên ba topology: notebook train các checkpoint ngắn từ source hiện hành, rồi chạy benchmark và strict ablation với 64 request steps. Xác nhận action space/model match, mask output, output CSV có topology/seed/scenario/variant. Smoke check chỉ xác nhận pipeline; không đưa số vào paper.
4. Notebook cũ `notebook/harp-ablation-nsfnet.ipynb` gọi module path cũ `src.analytics.ablation_study` và không dùng cùng evaluator/action interface. Dùng notebook mới `notebook/rev1-benchmark-ablation-kaggle.ipynb`; notebook này train checkpoint smoke/full từ source snapshot hiện hành và không nạp checkpoint v11 cũ. Chỉ bật full stage sau khi smoke pass; historical outputs trong `kaggle/results_kaggle` chỉ dùng đối chiếu sau khi xác nhận provenance.

### 1. Khôi phục benchmark chính (P0.1, P0.3)

- Với checkpoint v11 historical/submitted, vẫn phải sửa/kiểm tra evaluator: ánh xạ action pair `(place, route)` từ `MultiDiscrete([N,N])` sang biểu diễn mà benchmark environment nhận, hoặc cung cấp adapter environment có cùng action space. Notebook mới né phụ thuộc đó bằng cách train checkpoint mới từ cùng source/environment hiện hành; kết quả mới vì vậy cần được mô tả là rerun theo pipeline hiện tại, không khẳng định là tái lập checkpoint v11 cũ.
- Historical results trong `kaggle/results_kaggle` có benchmark NSFNET 3 workload × 5 seed và ablation 3 topology × 3 workload × 5 seed. Trước khi dùng làm đối chứng, truy source/checkpoint/config hash và xác định vì sao benchmark hiện chỉ có NSFNET; các aggregate CSV dạng `mean ± std` không đủ thay raw per-seed results.
- Chạy lại cấu hình submitted để làm đối chứng: scenario gốc, 3 topology, 5 seed cũ `[42,100,2024,8888,9999]`, 3000 steps/seed. So sánh từng seed với `docs/Submit_1/results`; không thay số paper nếu chưa giải thích sai lệch.
- Sau khi baseline tái lập được, chạy P0.1 workload tách biệt: `elephant_stress` và `chaos` (cùng seed set, topology, steps, load, model/checkpoint). Lưu config thực tế sau resolve, input hash, checkpoint hash, source hash, package/hardware info và per-step/per-seed CSV.
- Chạy thống kê paired HARP vs SAF-H trên tối thiểu 10 matched seeds (nên dùng 20 nếu thời gian GPU cho phép). Dùng cùng seed làm cặp trong cùng workload/topology; báo bootstrap 95% CI, Wilcoxon signed-rank, paired rank-biserial, và Holm correction cho family comparisons đã định trước. Giữ riêng 5-seed historical reproduction với 10/20-seed revision run.

### 2. Ablation HARP (P0.3, P1.6)

- Dùng notebook ablation riêng (`notebook/harp-ablation-nsfnet.ipynb`) làm template; mỗi worker chỉ đổi `WORKER_TOPOLOGY`. Train variant checkpoints một lần cho topology với seed/config cố định (hoặc nêu rõ nếu dùng checkpoint đã đóng băng), sau đó evaluate cùng các variants trên workload traces/seeds matched. Không train lại model cho từng evaluation seed.
- Giữ 3000 evaluation steps và ba workload hiện có (`uniform`, `bursty`, `heavy_tail`) để có thể đối chiếu lịch sử. Dùng ít nhất 10 evaluation seeds cho revision; ghi riêng training seed và evaluation seed.
- Giữ benchmark algorithm rerun tách khỏi ablation. Ablation trả lời đóng góp của GAT/mask/penalty; benchmark trả lời HARP so với SAF-H/Greedy/DAI. Không gọi hai script trên cùng checkpoint nếu action space không tương thích.
- Export raw per-seed CSV và summary; thêm candidate count bị mask loại, runtime reject count/reason, admitted hard violations. Không diễn giải ablation “without mask” là bỏ admission trừ variant được cấu hình cụ thể là unchecked admission.

### 3. P0 protected-baseline study

- Trên Kaggle CPU, chạy testbed paired protected study từ cùng workload generator và seeds: `jo_vppm`, `heuristic`, `greedy`, `greedy_protected`, `decoupled`, `decoupled_protected`. So sánh unprotected/protected bằng cùng request trace; protected policies phải gọi cùng `NetworkStateManager.try_reserve`.
- Xuất candidate hard-infeasible rate, acceptance/safe acceptance, rejection theo CPU/MEM/MSD, admitted violations, decision latency median/P95/P99. Ghi rõ đây là offline software simulation; không dùng làm bằng chứng HIL.
- Lưu per-request records, per-seed summaries, metadata JSON và notebook output; không chỉ tải dashboard/aggregate.

### 4. Chặn trước / việc cần giải quyết ngoài Kaggle

- **P0.4:** code runtime hiện chưa chứng minh multi-VNF chain mapping; việc chạy Kaggle không giải quyết được. Thu hẹp paper thành semantics đơn request `(place, route)` hoặc triển khai chain-level runtime + tests trước khi mô tả chain tổng quát.
- **P0.5:** đo latency decision components và scalability là benchmark được, nhưng phải thêm instrumentation trước. Kaggle cần CPU-only profile tách state/mask/inference/admission; nếu đo GPU thì báo riêng và không so trực tiếp.
- **P0.6:** Có K-sensitivity summary từ source tree riêng. Cần audit commit/source lineage, implementation cache, manifest, và định nghĩa false infeasibility để xác định có thể đưa kết quả này làm bằng chứng bổ trợ hay không.
- **P0.7/P0.8:** paper sửa từ code audit trước; Kaggle không tạo ra telemetry freshness/TTL, versioning, hay atomic cloud+P4 reservation nếu runtime chưa hỗ trợ.
- Long-running HIL và controlled BMv2/P4 over-MSD cần testbed tương ứng, không thay thế bằng Kaggle simulation.

### 5. Artifact checklist cho mỗi Kaggle run

- `run_manifest.json`: topology, scenario, workload parameters, train/eval seeds, steps, model/normalizer/source/data SHA-256, action/observation spaces, git commit, Python/library versions, Kaggle accelerator/CPU/RAM.
- `per_request.csv`, `per_seed_summary.csv`, `aggregate_summary.csv`, `paired_statistics.csv` (nếu so sánh), config-resolved JSON, logs và notebook `.ipynb` output.
- Tải archive về và kiểm tra seed coverage/row count/NaN/failed runs trước khi dùng. Giữ artifacts raw bất biến; tạo paper tables/figures bằng script riêng từ các artifacts đã xác nhận.

## P0 — Bắt buộc hoàn thành trước khi resubmit

| ID | Reviewer concern | Công việc phải làm | Đầu ra cần cập nhật trong paper |
|---|---|---|---|
| P0.1 | R2: Elephant và Chaos có số liệu giống hệt nhau | **Đang làm.** Alias đã được xác nhận và Chaos đã được tách trong code thành burst + heavy-tail. Chạy tests, audit seeds/artifacts, rồi rerun Elephant/Chaos trên Vietnam, NSFNET, GEANT2; lưu config/hash cho từng run. | Thay các dòng liên quan trong Table `simulation_acceptance_summary`, cập nhật mọi prose/figure phụ thuộc số liệu. |
| P0.2 | R2: safety chưa được tách khỏi policy | Chạy **cùng admission boundary** cho Greedy, DAI, SAF-H và HARP. Khuyến nghị thiết kế paired: policy × {unprotected, protected} trên cùng workload trace/seed. | Bảng mới: candidate hard-infeasible rate, rejection CPU/MEM/MSD, safe acceptance, admitted violations, decision latency. Nếu mọi protected policy đều 0 violation, ghi rõ safety thuộc runtime contract. |
| P0.3 | R2: HARP vs SAF-H có margin nhỏ, chưa significance | Tăng số matched seeds: tối thiểu 10, ưu tiên 20 nếu chi phí cho phép. Với HARP vs SAF-H dùng paired Wilcoxon signed-rank trên cùng seed; báo 95% bootstrap CI, paired rank-biserial effect size; Holm correction khi thực hiện nhiều comparisons. Không chỉ báo mean±std. | Bổ sung thống kê vào bảng chính hoặc bảng phụ; prose phải dùng “statistically significant” chỉ khi test hỗ trợ. |
| P0.4 | R2: compact action/anchor chưa xác định đầy đủ chain | Rev1 hiện phân biệt mô hình chain tổng quát với action code thật: một cặp `(place, route)` cho một request/decision; policy không phát `m` hay mapping nhiều VNF. Cần xác nhận router/controller xử lý chain ở đâu và tạo trace integration chain ≥3 VNF; nếu không có, giữ claim hẹp và xóa TODO/thuật toán mô tả full-chain như tính năng đã chạy. | Cập nhật System Model/MDP/mask bằng semantics đã xác minh; đóng bằng full-chain trace hoặc thu hẹp claim + giải trình reviewer. |
| P0.5 | R2/R4/R5: không có end-to-end decision latency/scalability | Đo riêng: state construction, feasible-set/mask construction, HARP inference, heuristic inference, final admission validation, controller handoff, total decision latency. Báo median/P95/P99 và throughput decisions/s. Vary topology size + active chains + concurrent requests. | Subsection/figure/table scalability; cập nhật Complexity và Limitations. |
| P0.6 | R2: path cache có thể tạo false infeasibility | Đã nhận K-sensitivity summary từ source tree khác. Audit source revision, cache implementation, run manifest, hardware và false-infeasibility definition; không gán result đó cho workspace source hiện tại. | Table K-sensitivity đã có màu xanh; cần provenance và quan hệ với pipeline benchmark chính trước khi chốt claim. |
| P0.7 | R2: Hybrid predicate chưa định nghĩa | Rev1 hiện ghi đúng predicate `max(mean CPU, mean MSD)`, ngưỡng engage/release, active alert và không có window/dwell-time trong `choose_mode`. Notebook smoke kiểm tra action model nhưng chưa kiểm tra chuyển mode; thêm transition assertions hoặc xác nhận riêng bằng runtime trace. | Green formula trong Sec. Architecture; cần xóa placeholder generic `IsStable` và cập nhật Algorithm 1 theo đúng predicate trước khi resubmit. |
| P0.8 | R5: feature normalization, mask frequency, stale state, TOCTOU | Rev1 có 6 node + 13 global features, clipping, normalizer và local pair mask formula. Source dùng local lock cho reservation nhưng chưa có telemetry version/TTL hay transaction xuyên K8s/P4. Nếu không bổ sung freshness/versioning thì thu hẹp claim và ghi limitation; Kaggle không giải quyết phần này. | Green feature/mask description + Limitations; thêm measured telemetry age/atomic reservation only if implemented. |

## P1 — Nên hoàn thành để vòng major revision thuyết phục

| ID | Reviewer concern | Công việc đề xuất | Đầu ra |
|---|---|---|---|
| P1.1 | R2: load sweep chỉ có một curve | Regenerate load sweep 0.2x–1.5x cho HARP, SAF-H, Greedy+Admission, DAI+Admission trên matched traces. | Thay `VN_load_sweep.pdf`; nên thể hiện safe acceptance + rejection/infeasible pressure; admitted violation có thể ở panel riêng nếu luôn 0. |
| P1.2 | R4/R5: topology nhỏ | Thêm topology synthetic/extended khoảng 50, 100, 200 nodes nếu runtime cho phép; nếu 200 quá nặng, báo giới hạn thực nghiệm và dùng 25/50/100. Giữ normalized load tương đương. | Scalability figure/table. |
| P1.3 | R5: services/concurrent chains | Vary active chains và concurrent requests, ví dụ các mức thấp/trung bình/cao phù hợp implementation; ghi rõ queueing policy. | Scalability table + throughput/latency curves. |
| P1.4 | R5: long-running stability | Chạy HIL liên tục tối thiểu vài giờ; ưu tiên 24 h nếu khả thi. Ghi total requests, admitted/rejected, rejection by constraint, migrations, controller/deployment failures, telemetry/mask refresh failures, latency drift, admitted MSD violations. | Subsection “Extended HIL stability”. Không gọi là production case study nếu không chạy trên carrier production. |
| P1.5 | R5: practical MSD consequence | Tạo controlled over-MSD test: cố ý tạo SID list > MSD, ghi controller/admission outcome và BMv2/P4 counter/log. Phân biệt rõ target-specific behavior; không suy rộng BMv2 thành mọi ASIC. | 1 đoạn motivation + 1 row/table/log summary; có thể dùng appendix nếu dài. |
| P1.6 | R2/R5: masking role | Từ ablation hiện có, báo thêm number/rate of candidates eliminated by mask và runtime rejections with/without mask. | Cập nhật ablation table/prose để chứng minh masking = efficiency/quality, admission = safety. |
| P1.7 | R4: abbreviations | Audit toàn bộ source: expand first occurrence only cho AIOps, MLOps, SFC, VNF, SRv6, MSD, PPO, GAT... | Clean source; không lặp long form sau first definition. |

## Hình cần sửa/bổ sung

1. **`figs/overview.pdf`**: làm rõ ba khối theo thứ tự `Policy/Heuristic -> independent runtime admission -> actuation`. Gắn nhãn HARP là “replaceable policy instance”; không vẽ masking như nguồn duy nhất của safety. Thêm state version/freshness vào đường telemetry nếu implementation có.
2. **`figs/VN_load_sweep.pdf`**: đã tạo 3 panel từ bộ số liệu load-sweep người dùng cung cấp: safe acceptance, rejection pressure suy ra là `100% - safe acceptance`, và admitted MSD violations. Các protected policies dùng chung admission boundary; cần xác minh seed/trace và raw artifacts trước submission.
3. **`figs/testbed.pdf`**: đã tạo sơ đồ protected path và bypass path. HARP, Heuristic, Hybrid, Greedy và DAI protected cùng đi qua một Admission Boundary; Greedy/DAI unprotected đi bypass. Cần đối chiếu cấu hình controller/run logs trước submission.
4. **Hình mới — K sensitivity**: đã tạo `figs/k_sensitivity.pdf` từ summary riêng của cache-enabled source tree. Chưa xác minh source revision/manifest; không quy kết kết quả cho runtime hiện tại.
5. **Hình mới — Scalability/latency**: đã tạo `figs/scalability_latency.pdf` với decomposition state/mask/inference/validation, total P95 và throughput. Actuation không gộp vào decision latency; bộ số liệu scalability không cung cấp actuation-time breakdown riêng.
6. **Hình mới tùy chọn — Long-run HIL**: chưa tạo vì workspace chưa có chuỗi đo HIL kéo dài nhiều giờ với latency theo thời gian và cumulative rejection/violation. Không suy diễn từ các bảng HIL theo kịch bản hiện có.

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
- Conclusion: sau khi hoàn tất experiments, thay câu mang tính kế hoạch bằng 1–2 quantitative findings mạnh nhất; giữ conclusion khoảng 2 đoạn.