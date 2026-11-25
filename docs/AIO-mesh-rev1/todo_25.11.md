# TODO — Hoàn thiện lần cuối AIO-Mesh.rev1n(4)

**Manuscript:** FGCS-D-26-03249. **Nguồn chuẩn theo checklist:** `AIO-Mesh.rev1n(4).pdf` (21 trang). Chỉ sửa các điểm dưới đây; giữ nguyên title, số liệu chưa có bằng chứng, reviewer comments; sửa mới dùng `\newrev{...}`. Mỗi đoạn LaTeX một dòng. SD hiển thị superscript.

## Trạng thái rà soát 25.11

Đã đồng bộ phần văn bản có thể kiểm chứng trong `rev1.tex`, `supplement.tex`, và `response_rev1.tex`. Hai asset Figure 1–2 vẫn để nguyên theo yêu cầu của tác giả. Các mục phụ thuộc hình hoặc PDF build chưa thể chốt.

## P0 — Bắt buộc trước khi chốt bản nộp

### P0.1 — Figures 1–2 và Abstract attribution (R2.1, R2.2, R2.5, R5.4)

- [ ] **Tác giả chỉnh:** Figure 1: đưa policy mask vào HARP trước chọn action; sau candidate là independent runtime validation/reservation. Nhánh heuristic bỏ qua learned-policy mask. Đổi `Adaptive SLA and Migration Penalty` thành `Adaptive SLA and Action-Switching Penalty`; reward không phải inference-time action transform.
- [ ] **Tác giả chỉnh:** Figure 2: đổi `Smart Admission — mask unsafe actions` thành `Smart Admission — validate/reserve selected proposal`; phân biệt policy mask và runtime admission; nhánh 409 không actuation.
- [x] Abstract: HARP là replaceable proposal policy; independent admission và migration thuộc runtime. Claim hardware-safety được giới hạn vào implemented predicates trên controller-visible state; không hàm ý full-chain guarantee.
- [ ] Sau khi sửa hình, đối chiếu captions với Sections 4.1–4.6, 5.3–5.6, Algorithms 1–2, Eqs. (19)–(24); giữ compile/path checks và SID-list payload guard trước actuation.

### P0.2 — Timing/scalability (R2.3, R2.5, R4.2, R5.5)

- [x] Table 9/Figure 5 dùng cùng 20-seed shared-host concurrent records. Giá trị bất thường SAF-H ở 100 nodes được giữ nguyên; không gọi là lỗi cộng P95.
- [x] Source/log xác nhận ms, timer boundary, 25/50/100-node topology, edge counts, implementation, 20 seeds và trace hashes. Manifest thiếu CPU model, thread count và concurrency theo job; bản thảo ghi rõ các run concurrent trên shared host và không quy mức tăng SAF-H 100-node cho scheduling hay nguyên nhân cụ thể nào.
- [x] Không có matched serialized HARP–SAF-H raw study đủ điều kiện. Giữ Table 9/Figure 5 là concurrent; S27 (SAF-H-only serialized) tách riêng. Không suy isolated algorithmic latency advantage.
- [x] Table 10 cho admission predicate tại 0/25/50/100 background chains; S29 bổ sung crossed 25/50/100 nodes × 0/25/50/100 modeled chains, gồm inference/selection và total decision P95. Nói rõ đây là simulator occupancy, không phải live Kubernetes concurrency.
- [x] Sửa câu complexity: Table 9 có candidate/selection/admission; Figure 5 chỉ plot candidate và total decision P95.
- [x] Phân biệt timer simulator (predicate checks, dừng trước state mutation) với timer live (reservation call gồm lock, state mutation, durable checkpoint). Đã nêu software versions còn trong manifest và metadata host còn thiếu.
- [x] Bỏ claim chung “at greater decision cost”; giữ timing comparison theo đúng protocol/cell. API RTT P95 169.95 ms và submission-to-steering P95 31.6 s còn trong manuscript.

### P0.3 — Freshness, empty-mask PPO và safety scope (R2.2, R2.4, R5.4)

- [x] Section 4.3 mô tả local snapshot-version/lock, `CORE_ROUTER_TELEMETRY_TTL_S` tùy chọn (không có default TTL), telemetry chưa ingest và thay đổi lúc deployment/steering nằm ngoài kiểm tra. Không có fault-injection log đủ để khôi phục claim thử nghiệm stale telemetry.
- [x] Mô tả `-1e8` float32 all-false uniform fallback và likelihood ratio với cùng mask ở rollout/update; ghi version train sb3-contrib 2.7.1.
- [x] Section 6.6/S12: 0 rejection trong các pre-step nonempty-mask states trên 180,000 offered decisions. Full 41.642% proposed hard-invalid union là metric khác, có thể chứa empty-mask fallback; không suy tỷ lệ từ marginal summaries.
- [x] `NO_SAFE_ACTION` chỉ có nghĩa các proposal/fallback đã thử đều không qua predicate, không chứng minh global infeasibility. Path/SID compile và admission trước actuation; controller payload được so với admitted SID list trước REST actuation. Không claim distributed transaction.

## P1 — Bằng chứng reviewer

### P1.1 — HIL repeated lifecycle (R5.5)

- [x] S28/raw trace: 18/18 replacements, 4,952/4,952 request IDs, zero duplicate/loss, max 339.8 ms giữa hai successful response liên tiếp trong một cycle, zero MSD-counter increment.
- [x] Sửa phạm vi: mỗi cycle có cửa sổ sequential HTTP `/echo` probe, recorded mean send interval 0.233–0.236 s (sleep 0.2 s cộng thời gian response), ít nhất hai response baseline trước submission, tiếp diễn đến 10 s sau xóa old Deployment. Client đổi /32 SRv6 route từ old Pod IP sang Ready new Pod IP sau steering confirmation; đây không phải stable service address hay một TCP flow duy trì suốt 3 giờ. Định nghĩa exact-old, request-ID denominator và max-gap window trong S28.
- [x] Phân biệt campaign 57 migrations (không đo continuous-flow preservation) với 18-cycle S28. Không tuyên bố zero downtime, arbitrary traffic continuity, multi-service hay multi-day.
- [x] Table 6 accounting giữ theo request logs; `no feasible resilience pair` được giới hạn ở bounded candidate search, không phải global infeasibility. Table 8 không bị nhầm thành bảng 18 lifecycle cycles.

### P1.2 — Pair-to-chain và R2.5

- [x] Section 4.5: ingress-to-placement BFS, route-anchor profile check, exact-depth contract, không cache trong pipeline này. Eq. (8) là desired full-chain soundness implication chưa được chứng minh; prototype evidence pair/single-VNF.
- [x] Response nêu Hybrid thresholds 0.45/0.35, alert override, và không đánh giá riêng Hybrid transitions/superiority.

## P2 — Khóa hồ sơ nộp

- [x] Scripts/manifests ghi means/sample SD, seed-level timing P95, exact signed-rank zero/tie handling, Holm families 9 HARP–SAF-H / 9 HARP–CSPF / 15 arrival / 21 intensity, và 20,000 bootstrap resamples. Không thay p-values.
- [ ] **Một phần:** supplementary hiện có S1–S30 và mapping/raw artifacts liên quan. Data and Code Availability chưa pin immutable revision ID của đúng source/evidence snapshot; funding code vẫn cần đối chiếu hồ sơ tác giả.
- [x] R4.1: bổ sung abbreviation lần đầu trong Abstract/main gồm AIOps, SRv6, VNF, P4, PPO, BMv2, NFVI, TTL, RTT, GAT, API, DAI, SAF-H, CSPF.
- [x] S29 dùng macro `\SD{}` superscript; các bảng trước giữ cách hiển thị superscript hiện có. PDF render vẫn cần kiểm tra sau build.
- [ ] **Một phần:** response đã đồng bộ timing, S12, HIL scope, full-chain và package-version uncertainty; reviewer comments được giữ. Chốt references to figures/page/table numbers sau khi sửa Figure 1–2.
- [ ] **Overleaf chờ tác giả:** compile PDF 21 trang với bibliography/assets, rà Figures 1–2, Figure 5, cross-references, revision marks, S29 superscript render và clean/revision-marked exports. Không compile cục bộ theo workflow hiện tại.

## Việc còn mở

1. Tác giả chỉnh Figure 1–2; sau đó đồng bộ response/captions và rà PDF.
2. Mục timing shared-host được chốt với limitation hiện tại; chỉ bổ sung CPU/thread/job-concurrency metadata nếu tìm thấy trong archive gốc, không chạy lại hoặc thay số liệu.
3. Tìm train-time package manifest của corrected checkpoints hoặc giữ limitation đã ghi.
4. Pin immutable code/evidence revision trong Data and Code Availability; xác minh funding code.
5. Hoàn tất Overleaf build và PDF review.

## Điều kiện chốt bản nộp

Không xác nhận đã đáp ứng thuộc tính chưa đo. Các giới hạn còn công bố: ordered full-chain forwarding, live admission scaling theo topology/heterogeneous services, ASIC behavior, stable-address/general zero downtime, multi-day operation, và training package provenance nếu archive không bổ sung được.
