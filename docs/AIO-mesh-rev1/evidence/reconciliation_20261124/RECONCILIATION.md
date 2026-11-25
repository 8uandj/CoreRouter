# Trạng thái bản nộp rút gọn — 24/11/2026

Bản chính hiện tại: `docs/AIO-mesh-rev1/rev1.tex`; PDF marked/clean ở cùng thư mục. Bản nền là `docs/AIO-mesh-submitted 1/submitted-1.tex`. Bundle `AIO-mesh-submit-2` được dùng để audit dữ liệu, không phải bản nộp mới nhất.

## Phạm vi trình bày đã sửa theo yêu cầu mới

- Rút bản PDF từ 36 xuống 20 trang, gồm references; không đặt appendix chi tiết trong bản chính.
- Giữ 5 contributions và thứ tự của submit1. Abstract được sửa trực tiếp từ bản gốc, chủ yếu ở các claim implementation/safety và kết quả không còn đúng. Giữ tên bài, tác giả, bảy section chính, formulation tổng quát, Funding/CRediT và declarations theo bản đã nộp.
- Chỉ giữ 10 bảng cốt yếu trong bản chính. Tất cả là float một cột, không còn `table*`. Benchmark được dàn thành bốn cột theo từng topology để đọc được ở cỡ chữ nhỏ, không ép bảy cột quá hẹp.
- Bảng vẫn nằm trực tiếp trong source `.tex`; không tách các hàng bảng thành tệp input. Số ±SD tiếp tục là superscript.
- Supplementary là tài liệu riêng có S1–S30: giữ S1–S25, thêm S26 cho hai admission/probe long run, S27 cho timing SAF-H tuần tự lịch sử, S28 cho campaign repeated exact-old lifecycle ba giờ, S29 cho crossed synthetic matrix, và S30 cho live admission-only sweep.

| Bảng chính | Nội dung và lý do giữ |
|---:|---|
| 1 | Hard constraints → failure modes, đáp ứng R5.2. |
| 2 | Safe acceptance của năm policies trên ba topology/ba workloads. |
| 3 | Paired HARP–SAF-H statistics; pointwise CI và Holm-adjusted p-values. |
| 4 | Ablation: acceptance, seed-level decision P95 và admitted violations. |
| 5 | Proposed/admitted hard violations với mẫu số offered requests. |
| 6 | E2E campaign: đủ 398 terminal outcomes, lifecycle accounting, probes và timing cốt yếu. |
| 7 | Protected/bypass MSD fault experiments và counter deltas. |
| 8 | Tóm tắt 12-hour control-plane, hai 3-hour probe/admission runs, và repeated exact-old lifecycle ba giờ ở Supplementary S28. |
| 9 | HARP/SAF-H synthetic timing: candidate, inference/selection, validation và decision. |
| 10 | Admission-predicate timing tại 0/25/50/100 background chains trên named substrates. |

## Đối chiếu checklist

| Mục | Trạng thái hiện tại |
|---|---|
| P0.1 | Figure 5 và Table 9 dùng cùng dữ liệu audit được. Bộ 44.273/11.103 ms cũ không dùng theo chỉ đạo người dùng. Phân biệt concurrent benchmark với historical serialized study ở S27. |
| P0.2 | Table 6: 398 = 69 admitted + 231 mismatch + 6 MSD overflow + 43 ingress=placement + 49 resilience-search failure. Baseline 39; 12 deployments không replacement, 57 migrations, cuối 51. Target 30 là số active names không thuộc baseline. |
| P0.3 | Figures 1–2: logits → masking → selection → independent validation/reservation; có admitted/rejected branches và Action-Switching Penalty. |
| P0.4 | Masked distribution hiện là Eq. 23, chỉ có nghĩa khi feasible set khác rỗng; training/simulator/live fallback và bandwidth predicates được phân biệt trong Sections 5.3/5.5 và Algorithm 2. |
| P0.5 | Requested depth, materialized depth, depth-consistency và hardware-MSD feasibility được tách rõ. |
| P1.1 | Đã giải thích pair realization, anchor, compiler và no-cache. Cited campaigns chưa tự chứng minh ordered multi-VNF traversal; không suy ra hệ thống không có khả năng đó. |
| P1.2 | Đã hoàn thành các phép đo theo kế hoạch. Crossed simulator đủ 240/240 ô, 480 policy rows, 12 topology/occupancy cells × 20 seed; cặp HARP/SAF-H có trace hash khớp và mọi protected run có zero admitted hard violations (Supplementary S29). Ở 100 nodes, total-decision P95 là 106.67–118.45 ms cho HARP và 251.53–257.11 ms cho SAF-H qua các occupancy. Live admission-only không reset đạt 30/30 cleanup; P95 35.05/28.60/26.24 ms tại concurrency 1/2/4 trên profile 10 node (S30). Repeated exact-old lifecycle 3 giờ đạt 18/18 cycles, 4,952/4,952 packets, gap tối đa 339.8 ms (S28). Phạm vi reviewer được đáp ứng một phần ở khía cạnh live/generalization: occupancy trong simulator là profile cố định; live admission chỉ đo 10-node; lifecycle chỉ cover vVOC trên một profile và không chứng minh production, multi-day, hay ordered full-chain forwarding. |
| P2.1 | Giữ mean/sample SD, exact conditional Wilcoxon với ties/zeros, 20,000 paired bootstrap resamples, pointwise CI, Holm families và mẫu số. Tất cả bảng S1–S25 vẫn có trong supplement. |
| P2.2 | Response hiện remap số bảng 1–10/S1–S30; 20 reviewer comment blocks gốc được giữ nguyên. |

## Kiểm tra

`check_tex_inputs.py` kiểm tra main labels/assets/citations. `check_evidence.py` kiểm tra 209 điều kiện, gồm hashes, bảng giữ lại ở main hoặc supplement, toàn bộ 45 benchmark mean/SD cells, compact E2E/MSD/stability cells và các baseline guards. Snapshot đối chiếu số liệu được pin ở commit `2271d032`, không dựa vào HEAD có thể thay đổi.

Ở snapshot đối chiếu trước khi tích hợp các kết quả P1.2 mới, marked, clean, supplementary và response đã build; không undefined reference/citation hoặc missing glyph, và text marked/clean trùng nhau. Sau cập nhật, `check_tex_inputs.py` chạy thành công (1 manuscript input, 32 references, 5 figures, 53 citation keys); bảng S29 được đối chiếu lại với raw data (24 rows × 4 metrics, mean/sample SD khớp), S30 có đủ ba concurrency rows; matrix đủ 240 cells và 480 policy rows. Các cập nhật lifecycle, simulator matrix và live admission mới trong rev1, supplement và response chưa được build lại cục bộ theo workflow Overleaf; cần kiểm tra compile, label/table numbering và số trang trên Overleaf trước khi khóa gói nộp. `AIO-mesh-submit-2` còn chứa một snapshot manuscript/response và PDF cũ, khác đáng kể với các file làm việc hiện tại; bundle đó chưa được cập nhật và không nên dùng làm gói nộp cho đến khi được đối chiếu sau compile. Các hbox warnings nhỏ đã ghi nhận ở snapshot trước là footer/run-in heading, không phải lỗi bảng tràn cột.

Đối chiếu trực tiếp với submit1: `BASELINE_REVIEW.md`, `submit1_paragraph_review.json`, `SUBMIT1_TO_REV1.diff`. Đây là nghiệm thu biên tập và dữ liệu hiện có, không thay cho các testbed experiments còn thiếu mà người dùng dự định chạy trên server khác.
