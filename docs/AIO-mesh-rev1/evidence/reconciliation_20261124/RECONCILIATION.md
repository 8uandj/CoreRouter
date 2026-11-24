# Trạng thái bản nộp rút gọn — 24/11/2026

Bản chính hiện tại: `docs/AIO-mesh-rev1/rev1.tex`; PDF marked/clean ở cùng thư mục. Bản nền là `docs/AIO-mesh-submitted 1/submitted-1.tex`. Bundle `AIO-mesh-submit-2` được dùng để audit dữ liệu, không phải bản nộp mới nhất.

## Phạm vi trình bày đã sửa theo yêu cầu mới

- Rút bản PDF từ 36 xuống 20 trang, gồm references; không đặt appendix chi tiết trong bản chính.
- Giữ 5 contributions và thứ tự của submit1. Abstract được sửa trực tiếp từ bản gốc, chủ yếu ở các claim implementation/safety và kết quả không còn đúng. Giữ tên bài, tác giả, bảy section chính, formulation tổng quát, Funding/CRediT và declarations theo bản đã nộp.
- Chỉ giữ 10 bảng cốt yếu trong bản chính. Tất cả là float một cột, không còn `table*`. Benchmark được dàn thành bốn cột theo từng topology để đọc được ở cỡ chữ nhỏ, không ép bảy cột quá hẹp.
- Bảng vẫn nằm trực tiếp trong source `.tex`; không tách các hàng bảng thành tệp input. Số ±SD tiếp tục là superscript.
- Supplementary là tài liệu riêng có S1–S27: giữ S1–S25, thêm S26 chứa chi tiết hai long run và S27 chứa timing SAF-H tuần tự lịch sử. Không chạy thêm thí nghiệm và không đổi các giá trị đã xác minh.

| Bảng chính | Nội dung và lý do giữ |
|---:|---|
| 1 | Hard constraints → failure modes, đáp ứng R5.2. |
| 2 | Safe acceptance của năm policies trên ba topology/ba workloads. |
| 3 | Paired HARP–SAF-H statistics; pointwise CI và Holm-adjusted p-values. |
| 4 | Ablation: acceptance, seed-level decision P95 và admitted violations. |
| 5 | Proposed/admitted hard violations với mẫu số offered requests. |
| 6 | E2E campaign: đủ 398 terminal outcomes, lifecycle accounting, probes và timing cốt yếu. |
| 7 | Protected/bypass MSD fault experiments và counter deltas. |
| 8 | Tóm tắt 12-hour control-plane và hai 3-hour probe/admission runs. |
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
| P1.2 | Tables 9–10/S25 có timer predicates riêng. Chưa có đầy đủ crossed size × occupancy × service-count study hoặc multi-hour repeated admission-to-actuation experiment; giới hạn được nêu trong bài/response. |
| P2.1 | Giữ mean/sample SD, exact conditional Wilcoxon với ties/zeros, 20,000 paired bootstrap resamples, pointwise CI, Holm families và mẫu số. Tất cả bảng S1–S25 vẫn có trong supplement. |
| P2.2 | Response đã remap số bảng 1–10/S1–S27; 20 reviewer comment blocks gốc được giữ nguyên. |

## Kiểm tra

`check_tex_inputs.py` kiểm tra main labels/assets/citations. `check_evidence.py` kiểm tra 209 điều kiện, gồm hashes, bảng giữ lại ở main hoặc supplement, toàn bộ 45 benchmark mean/SD cells, compact E2E/MSD/stability cells và các baseline guards. Snapshot đối chiếu số liệu được pin ở commit `2271d032`, không dựa vào HEAD có thể thay đổi.

Đã build marked, clean, supplementary và response; không undefined reference/citation hoặc missing glyph. Text marked/clean trùng nhau. Đã xem Abstract/Introduction và các trang bảng quan trọng. Các hbox warnings nhỏ của footer/run-in heading không phải lỗi bảng tràn cột.

Đối chiếu trực tiếp với submit1: `BASELINE_REVIEW.md`, `submit1_paragraph_review.json`, `SUBMIT1_TO_REV1.diff`. Đây là nghiệm thu biên tập và dữ liệu hiện có, không thay cho các testbed experiments còn thiếu mà người dùng dự định chạy trên server khác.
