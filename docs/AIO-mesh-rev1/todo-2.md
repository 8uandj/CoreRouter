# AIO-Mesh — TODO thực nghiệm và hoàn thiện revision FGCS

**Nguyên tắc:** Chỉ xử lý concerns của reviewers; kế thừa tối đa bản đã nộp. Ưu tiên kiểm tra lại source/config/log gốc, chỉ chạy lại khi cần. Không suy diễn kết quả hoặc mở rộng safety claim vượt implementation.

## E1 — Action realization và admission (P0)
- [X] Xuất trace từ policy pair → placement đầy đủ (chuỗi ≥3 VNF) → path/SID list → MSD từng profile → admission → forwarding; xác định rõ mapping trong code.
- [X] Kiểm tra CPU/RAM khi reuse, routing-only và make-before-break; MSD là giới hạn *từng SID list*, không cộng dồn nhiều flow.
- [X] Đối chiếu local predicate với full-chain realization; kiểm tra stale telemetry, admission đồng thời, reservation/release; cố định normalization theo checkpoint.
- [X] Nếu chưa chứng minh full-chain soundness, giới hạn kết luận ở **pair-level checks** và controller-visible state.

## E2 — Baselines, thống kê và acceptance accounting (P0)
- [X] Xác minh seed/run manifests; chạy HARP, SAF-H, Greedy, DAI trên matched traces và cùng admission boundary; chốt cấu hình/tie-break. Bổ sung CSPF reference nếu SAF-H không tương đương.
- [X] Đối soát offered/admitted/safe-admitted/deployed/violated theo request ID; định nghĩa mẫu số, phân loại rejection không trùng lặp.
- [X] Sửa Elephant/Chaos nếu generator trùng hoặc sai; điền GEANT2 Chaos từ dữ liệu gốc.
- [X] Tính paired bootstrap CI95, Wilcoxon, Holm, rank-biserial effect; tái sinh load sweep 0.2–1.5× với CI và rejection reasons.
- [X] Đo missed-feasible rejections bằng oracle trên topology nhỏ, phân biệt bão hòa thật với lỗi tìm kiếm; so sánh gain–cost HARP/SAF-H.

## E3 — Ablation, masking và safety attribution (P0)
- [x] Đối chứng Full/MLP/NoMask/NoMask+U/NoAdapt trên cùng trace; đo candidate pruning, admission rejection, convergence và overhead.
- [x] Kiểm tra dấu reward MSD và chạy SoftMSD với admission **on/off** riêng; không gọi một cấu hình Protected nếu còn admitted violations chưa giải thích.
- [x] Báo tỷ lệ đề xuất không khả thi theo CPU, RAM, MSD (cho phép chồng lấn) và tỷ lệ hợp; đo violations theo đúng mẫu số.
- [x] Phân biệt **masking cải thiện candidate quality** với **runtime admission chịu trách nhiệm enforcement**; không suy rộng từ các baseline được thử tới mọi SOTA RL.

## E4 — Scalability, latency và concurrency (P0)
- [x] Đo topology 10/25/50/100 nodes; tách ảnh hưởng topology, active chains, arrival rate và concurrency.
- [x] Thu timestamps per-request: queue/state/mask/inference/admission/deployment/readiness/steering; tính **decision P50/P95/P99** và **actuation latency** riêng.
- [x] Throughput = completed operations / thời gian thực; ghi workers, queue drops, CPU/RAM, hardware/software và warm-up.
- [x] Không lấy tổng các component làm P95; không lấy nghịch đảo P95 làm throughput; không gán benchmark queue cho FastAPI nếu chưa đo.

## E5 — Candidate-path cache (chỉ khi có trong runtime cuối)
- [ ] Nếu có cache: cùng codebase, thử K=1/3/5/10/20; đo safe acceptance, time, memory, missed-feasible so với oracle.
- [x] Nếu không có cache: **bỏ bảng/hình K-cache từ code khác**, sửa mô tả và giải thích trong response; không cần chạy E5.

## E6 — HIL 24 giờ, fault injection, migration (P0)
- [x] Đối soát 24h: 25,000 requests; 17,820 deployed; 5,910 CPU/RAM rejects; 1,270 MSD rejects; lưu per-hour logs, errors, migrations và latency drift.
- [x] Injection SID depth 7 > MSD 4: lưu P4/BMv2 config, packet captures, parser error, counter deltas và fallback outcome.
- [x] Kiểm tra make-before-break qua readiness, steering confirmation và packet traces; không khẳng định zero downtime thiếu bằng chứng.
- [x] Giới hạn kết luận ở BMv2/software forwarding, không suy rộng sang carrier-grade ASIC.

## Hoàn thiện manuscript và response
- [x] Chốt novelty là **policy-independent pre-actuation admission trong AIOps SRv6/P4**, không nhận GAT/PPO/shielding là thuật toán mới; rà soát related work, abbreviations và overclaims.
- [x] Chỉ giữ kết quả có raw evidence trong Abstract, §6, Conclusion và response letter; nêu limitations trung thực, không để TBC trong bản nộp.
- [x] Với nội dung còn phụ thuộc thực nghiệm, để comment đúng vị trí: `%NNH: cần hoàn thiện sau khi thực nghiệm [E1]: ...` (thay E1 bằng E2–E6). Xóa comment **sau khi** đối soát hoàn tất.

**Ưu tiên:** E1 → E2 → E3 → E4 → E6; E5 có điều kiện. Không cần tạo E7/E8.
