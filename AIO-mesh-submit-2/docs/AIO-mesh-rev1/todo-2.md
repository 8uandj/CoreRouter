# AIO-Mesh — TODO thực nghiệm và hoàn thiện revision FGCS

> **Trạng thái reset 2026-11-16:** người dùng xác nhận bản `rev1.tex` trước khi sửa có số liệu bịa; các dấu hoàn tất cũ không được dùng làm evidence. Các con số trong checklist là mục tiêu/claim cần kiểm chứng, không phải kết quả. Tiến độ thực tế ở `REVISION_STATUS.md`; bản checklist trước reset đã được backup.

**Nguyên tắc:** Chỉ xử lý concerns của reviewers; kế thừa tối đa bản đã nộp. Ưu tiên kiểm tra lại source/config/log gốc, chỉ chạy lại khi cần. Không suy diễn kết quả hoặc mở rộng safety claim vượt implementation.

## E1 — Action realization và admission (P0)
- [x] Audit source contract hiện tại: `/orchestrate` nhận một service type và policy chọn một placement/route pair; path/SID vật lý compile được khi có ingress/source. Đã index riêng evidence lịch sử về nhiều VNF và packet tới một Pod; không suy ra từ đó rằng người dùng chưa từng dựng chain. Xem `PAIR_ACTUATION_AUDIT.md`.
- [x] Ghi rõ CPU/RAM tính vào placement, MSD áp dụng theo SID-list/path và route profile, cùng các physical switch trên path; đây là source contract, chưa phải bằng chứng packet.
- [x] Ghi rõ admission version/lock, reservation/release và freshness limitation trong `SEMANTICS_CONTRACT.md`; chưa có transaction phân tán với Kubernetes/P4.
- [ ] Đối soát experiment chain nhiều VNF đã dựng trước đây bằng artifact xác định được thứ tự function, request/path và packet/application observations; song song xác định rõ current API/policy boundary. Không kết luận testbed không thể dựng chain chỉ từ schema hiện tại.
- [x] (2026-11-22, `results/rev1/hil_e2e_20261121`, Tab. `tab:hil_e2e`) Chứng minh `admitted SID list → installed rules → packet forwarding` bằng request-correlated packet capture/counter evidence. Chưa được đánh dấu forwarding hoàn tất.
- [x] Giới hạn mô tả hiện tại ở pair-level checks và controller-visible rule-installation status; không claim chain soundness, packet delivery, forwarding stability hoặc zero downtime.

## E2 — Baselines, thống kê và acceptance accounting (P0)
- [x] Thêm CSPF-style pair reference và hoàn tất benchmark 20 seed × 3 workload × 3 topology. Có 180 per-seed rows; trace hashes khớp với HARP trong cả chín conditions. HARP--CSPF paired delta +0.18--+0.86 pp; sáu Holm-adjusted tests significant. Raw/manifest/statistics: `results/rev1/cspf_baseline/`. Định nghĩa baseline rõ là endpoint-pair adaptation, không phải ingress-to-egress CSPF đầy đủ vì simulator chỉ có placement/routing pair.
- [ ] Đối soát offered/admitted/safe-admitted/deployed/violated theo request ID; định nghĩa mẫu số, phân loại rejection không trùng lặp.
- [ ] Sửa Elephant/Chaos nếu generator trùng hoặc sai; điền GEANT2 Chaos từ dữ liệu gốc.
- [ ] Tính paired bootstrap CI95, Wilcoxon, Holm, rank-biserial effect; tái sinh load sweep 0.2–1.5× với CI và rejection reasons.
- [x] Đo missed-feasible rejections bằng exhaustive pair-action oracle trên Vietnam; so sánh gain–cost HARP/SAF-H. Đã hoàn tất 2026-11-17: 10 seeds, 120 sampled states/seed, cùng simulator snapshot và TTL-expiry transition; HARP có 30/1,200 sampled rejections với alternative được nhận (per-seed conditional mean 5.02%, SD 2.66%), SAF-H 33/1,200 (5.70%, SD 2.32%). Controlled serialized cost: Vietnam, 10 seeds × 3,000 steps; mean seed-level decision p50/p95/p99 HARP 1.925/2.131/2.481 ms, SAF-H 0.339/0.494/0.527 ms. Bằng chứng: `results/rev1/nonhil_studies/20261117_233441/`.

## E3 — Ablation, masking và safety attribution (P0)
- [x] Đối chứng bảy ablation variants trên cùng trace; đo candidate pruning, admission rejection và simulator timing. Đã hoàn tất 12 topology--workload groups × 20 seeds × 7 variants; trace hashes khớp trong từng seed. Raw per-seed timed records: `results/rev1/e3_timed/`. **Còn thiếu:** retained training-convergence logs; không tuyên bố convergence nếu không có đường cong huấn luyện hợp lệ. Timing không bao gồm external controller/deployment latency.
- [x] Kiểm tra dấu reward MSD và chạy SoftMSD với admission **on/off** riêng; reward coefficient $-50$, cùng checkpoint cho cặp on/off; số violation admitted và giới hạn paired-state đã ghi tại §E3 và evidence.
- [x] Báo tỷ lệ đề xuất không khả thi theo CPU, RAM, BW, MSD (cho phép chồng lấn), hard-invalid union và admitted unique violations trên mẫu số offered requests; bảng pooled ở §E3.
- [x] Phân biệt mask/candidate quality với independent runtime admission/enforcement; giới hạn so sánh Full–NoMask và phạm vi simulator được nêu tại §E3.

## E4 — Scalability, latency và concurrency (P0)
- [x] Đo topology-size simulator trên 25/50/100-node synthetic grids với SAF-H (10 seeds × 300 decisions) và HARP-vs-SAF-H local decision cost ở Vietnam (10 nodes; 10 seeds × 3,000 steps). Archive per-seed và manifest SAF-H có trong `AIO-mesh-submit-2/results/rev1/nonhil_studies/`. Sau đó đã train checkpoint HARP N² theo từng kích thước và benchmark 20 seed × 3 workload; kết quả HARP được trình bày riêng trong `rev1.tex`. Timing SAF-H serialized và timing HARP từ benchmark chạy đồng thời không dùng chung một phép đo cô lập.
- [x] Tách active-chain occupancy ở 0/25/50/100 background chains, 20 seeds, trên ba topology; xem Table~\ref{tab:active_chain_stress} và `results/rev1/e4_active_chains/`.
- [ ] Arrival-rate-only runner dùng năm arrival probabilities, TTL cố định 100--500, Bursty demand profile giữ nguyên, 20 seed, 3 topology và checkpoint N² corrected. Session `arrival_rate_only` đang chạy; chờ raw data, aggregate, figure và manuscript insertion. Live request concurrency/queueing vẫn chưa đo.
- [x] Ghi decision P50/P95/P99 và offline runner throughput (completed simulator decisions / measured run wall time) trong cùng process cho HARP/SAF-H; actuation và end-to-end timestamps chưa có trong các lượt offline này. Không suy throughput từ p95 hoặc gán con số này cho API.
- [x] (Tab. `tab:hil_e2e`; queue wait trong `run/actuation_burst`) Thu riêng timestamps cho queue/state/admission/deployment/readiness/steering và actuation latency trên testbed/API; không thay bằng simulator timing.
- [x] Offline throughput dùng completed simulator decisions / measured run wall time; manifests pin hardware/software, worker count, seeds, data/checkpoint hashes và warm-up.
- [ ] Live API throughput dưới concurrent requests/queueing; không suy ra từ offline simulator throughput.
- [ ] Không lấy tổng các component làm P95; không lấy nghịch đảo P95 làm throughput; không gán benchmark queue cho FastAPI nếu chưa đo.

## E5 — Candidate-path cache (chỉ khi có trong runtime cuối)
- [ ] Nếu có cache: cùng codebase, thử K=1/3/5/10/20; đo safe acceptance, time, memory, missed-feasible so với oracle.
- [ ] Nếu không có cache: **bỏ bảng/hình K-cache từ code khác**, sửa mô tả và giải thích trong response; không cần chạy E5.

## E6 — HIL 12 giờ, fault injection, migration (P0)
- [x] Hoàn tất 12h control-plane HIL `results/rev1/e6_12h_control_plane/runs/20261117_190242` (2026-11-17 19:02:44–2026-11-18 07:02:44 UTC): 12,325 request, 1,455 admitted (11.81%), 10,870 rejected (88.19%; 9,672 MSD, 1,198 no-safe-action), 0 timeout, 0 actuation/deployment. API response P50/P95/P99 118.20/169.95/229.40 ms; hourly P95 164.60–175.30 ms. Kubernetes readiness 720/720 snapshots giữ 7/7 baseline Deployments/replicas Ready, không lỗi sampler. Raw records, hourly CSV, summary, PDF và run manifest nằm trong run directory. Vì `normal_load` không yêu cầu actuation, đây không phải deployment-success theo request. Các số 25,000/17,820/5,910/1,270 trong checklist là mục tiêu/claim cũ, không phải kết quả.
- [x] (chiến dịch e2e thay thế probe này) Sau khi run chính kết thúc, chạy probe lifecycle riêng qua `/api/deploy` → xác nhận PipelineRun và Deployment Ready → `/api/vnfs/{name}` delete/cleanup. `normal_load` không bật alert, không gửi `pps`, và weighted service không gồm `Attack`, nên không chủ động yêu cầu deployment theo request; không trộn probe này vào số liệu 12h.
- [x] (`run/live_fault_injection`: SRH 7 drop tại s5 MSD 4; cô lập depth 5 qua s7) Injection SID depth 7 > MSD 4: lưu P4/BMv2 config, packet captures, parser error, counter deltas và fallback outcome.
- [x] (57/57 và 23/23 đúng thứ tự; không tuyên bố zero downtime vì IP Pod đổi) Kiểm tra make-before-break qua readiness, steering confirmation và packet traces; không khẳng định zero downtime thiếu bằng chứng.
- [x] Giới hạn kết luận ở BMv2/software forwarding, không suy rộng sang carrier-grade ASIC.

**Phạm vi và giới hạn HIL:** pilot 24h `results/rev1/e6_24h_control_plane/runs/20261117_184721` dừng trước raw-record export và không được dùng làm kết quả; reservation duy nhất đã giải phóng, state trở về 7 baseline VNFs với `unaccounted_vnfs=[]`. Run 12h đã kết thúc; manifest, provenance, preflight, raw request records, hourly summary, aggregate summary, PDF và 720 hàng readiness được lưu tại `results/rev1/e6_12h_control_plane/runs/20261117_190242`. `normal_load` không tạo actuation, vì vậy readiness là quan sát baseline namespace, không phải kết quả deploy/readiness gắn request. Đây là control-plane HIL, không phát traffic qua P4 và không đóng các mục over-MSD, packet forwarding, migration steering, MBB, forwarding stability hay zero-downtime.

## Hoàn thiện manuscript và response
- [ ] Chốt novelty là **policy-independent pre-actuation admission trong AIOps SRv6/P4**, không nhận GAT/PPO/shielding là thuật toán mới; abbreviation first-use audit đã được cập nhật ở lượt này nhưng cần rà soát lại sau khi chèn kết quả CSPF/synthetic/arrival.
- [ ] Chỉ giữ kết quả có raw evidence trong Abstract, §6, Conclusion và response letter; nêu limitations trung thực, không để TBC trong bản nộp.
- [ ] Với nội dung còn phụ thuộc thực nghiệm, để comment đúng vị trí: `%NNH: cần hoàn thiện sau khi thực nghiệm [E1]: ...` (thay E1 bằng E2–E6). Xóa comment **sau khi** đối soát hoàn tất.

**Ưu tiên:** E1 → E2 → E3 → E4 → E6; E5 có điều kiện. Không cần tạo E7/E8.
