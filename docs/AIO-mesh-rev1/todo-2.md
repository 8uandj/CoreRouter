# AIO-Mesh — TODO thực nghiệm và hoàn thiện revision FGCS

> **Trạng thái reset 2026-11-16:** người dùng xác nhận bản `rev1.tex` trước khi sửa có số liệu bịa; các dấu hoàn tất cũ không được dùng làm evidence. Các con số trong checklist là mục tiêu/claim cần kiểm chứng, không phải kết quả. Tiến độ thực tế ở `REVISION_STATUS.md`; bản checklist trước reset đã được backup.

**Nguyên tắc:** Chỉ xử lý concerns của reviewers; kế thừa tối đa bản đã nộp. Ưu tiên kiểm tra lại source/config/log gốc, chỉ chạy lại khi cần. Không suy diễn kết quả hoặc mở rộng safety claim vượt implementation.

## E1 — Action realization và admission (P0)
- [ ] Xuất trace từ policy pair → placement đầy đủ (chuỗi ≥3 VNF) → path/SID list → MSD từng profile → admission → forwarding; xác định rõ mapping trong code.
- [ ] Kiểm tra CPU/RAM khi reuse, routing-only và make-before-break; MSD là giới hạn *từng SID list*, không cộng dồn nhiều flow.
- [ ] Đối chiếu local predicate với full-chain realization; kiểm tra stale telemetry, admission đồng thời, reservation/release; cố định normalization theo checkpoint.
- [ ] Nếu chưa chứng minh full-chain soundness, giới hạn kết luận ở **pair-level checks** và controller-visible state.

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
- [x] Đo topology-size simulator trên 25/50/100-node synthetic grids với SAF-H (10 seeds × 300 decisions) và HARP-vs-SAF-H local decision cost ở Vietnam (10 nodes; 10 seeds × 3,000 steps). Kết quả p50/p95/p99 cùng node/edge/action-space counts ở §Scalability và `results/rev1/nonhil_studies/20261117_235132/`. Chỉ xác nhận chi phí simulator của SAF-H theo N; không có size-matched HARP checkpoints.
- [x] Tách active-chain occupancy ở 0/25/50/100 background chains, 20 seeds, trên ba topology; xem Table~\ref{tab:active_chain_stress} và `results/rev1/e4_active_chains/`.
- [ ] Arrival-rate-only runner đã được viết: năm arrival probabilities, TTL cố định 100--500, Bursty demand profile giữ nguyên, 20 seed, 3 topology; supervisor chạy sau HARP synthetic training. Còn chờ raw data, aggregate, figure và manuscript insertion. Synthetic HARP 25/50/100 đang huấn luyện; supervisor sẽ đánh giá sau khi đủ final checkpoints. Live request concurrency/queueing vẫn chưa đo.
- [x] Ghi decision P50/P95/P99 và offline runner throughput (completed simulator decisions / measured run wall time) trong cùng process cho HARP/SAF-H; actuation và end-to-end timestamps chưa có trong các lượt offline này. Không suy throughput từ p95 hoặc gán con số này cho API.
- [ ] Thu riêng timestamps cho queue/state/admission/deployment/readiness/steering và actuation latency trên testbed/API; không thay bằng simulator timing.
- [x] Offline throughput dùng completed simulator decisions / measured run wall time; manifests pin hardware/software, worker count, seeds, data/checkpoint hashes và warm-up.
- [ ] Live API throughput dưới concurrent requests/queueing; không suy ra từ offline simulator throughput.
- [ ] Không lấy tổng các component làm P95; không lấy nghịch đảo P95 làm throughput; không gán benchmark queue cho FastAPI nếu chưa đo.

## E5 — Candidate-path cache (chỉ khi có trong runtime cuối)
- [ ] Nếu có cache: cùng codebase, thử K=1/3/5/10/20; đo safe acceptance, time, memory, missed-feasible so với oracle.
- [ ] Nếu không có cache: **bỏ bảng/hình K-cache từ code khác**, sửa mô tả và giải thích trong response; không cần chạy E5.

## E6 — HIL 24 giờ, fault injection, migration (P0)
- [ ] Đối soát 24h: 25,000 requests; 17,820 deployed; 5,910 CPU/RAM rejects; 1,270 MSD rejects; lưu per-hour logs, errors, migrations và latency drift.
- [ ] Injection SID depth 7 > MSD 4: lưu P4/BMv2 config, packet captures, parser error, counter deltas và fallback outcome.
- [ ] Kiểm tra make-before-break qua readiness, steering confirmation và packet traces; không khẳng định zero downtime thiếu bằng chứng.
- [ ] Giới hạn kết luận ở BMv2/software forwarding, không suy rộng sang carrier-grade ASIC.

## Hoàn thiện manuscript và response
- [ ] Chốt novelty là **policy-independent pre-actuation admission trong AIOps SRv6/P4**, không nhận GAT/PPO/shielding là thuật toán mới; abbreviation first-use audit đã được cập nhật ở lượt này nhưng cần rà soát lại sau khi chèn kết quả CSPF/synthetic/arrival.
- [ ] Chỉ giữ kết quả có raw evidence trong Abstract, §6, Conclusion và response letter; nêu limitations trung thực, không để TBC trong bản nộp.
- [ ] Với nội dung còn phụ thuộc thực nghiệm, để comment đúng vị trí: `%NNH: cần hoàn thiện sau khi thực nghiệm [E1]: ...` (thay E1 bằng E2–E6). Xóa comment **sau khi** đối soát hoàn tất.

**Ưu tiên:** E1 → E2 → E3 → E4 → E6; E5 có điều kiện. Không cần tạo E7/E8.
