# Đối soát revision — 24/11/2026

Bản làm việc: `docs/AIO-mesh-rev1/rev1.tex`. Bản neo: `docs/AIO-mesh-submitted 1/submitted-1.tex`. Nguồn bổ sung được người dùng chỉ định: `AIO-mesh-submit-2/docs/AIO-mesh-rev1/rev1.tex` cùng raw records và manifests trong bundle đó. Không sửa bản đã nộp hoặc bundle nguồn.

Giữ tiêu đề, tác giả, bảy section chính và thứ tự lập luận của bản đã nộp; phục hồi phần mở đầu Abstract và ngữ cảnh Introduction còn phù hợp. Giữ các hiệu chỉnh khoa học cần thiết do phản biện, không phục hồi các tuyên bố hiệu năng/safety rộng hơn evidence. Hai citation keys của bản cũ (`cSDAID22`, `jOptimizeSlice24`) không có trong các bibliography được cung cấp: giữ ngữ cảnh tổng quát, bỏ quy kết tới các nghiên cứu không xác định, không tạo bibliography giả.

Tất cả bảng/hàng bảng và macro số liệu của main manuscript đã được gộp trực tiếp vào `rev1.tex`; không còn `input` bảng hoặc tệp số liệu. Supplementary có source độc lập, cũng chứa trực tiếp toàn bộ bảng. Các artifact/generator gốc vẫn được giữ để audit. Các số ±SD được trình bày bằng superscript; không thay mean/SD/CI/p-value cũ nếu bảng gốc được xác nhận.

| Checklist | Hiệu chỉnh và vị trí thực tế |
|---|---|
| P0.1 | Figure 5 và Table 23 dùng cùng sáu nhóm 20-seed synthetic Burst-surge HARP/SAF-H, kiểm tra trace hashes theo seed. 100 nodes: HARP decision P95 26.101 ms; SAF-H 416.242 ms. Đây là benchmark chạy đồng thời trên shared host. SAF-H tuần tự lịch sử 83.562 ms được giữ riêng ở Appendix A.1, không trộn phép đo hoặc quy nguyên nhân tail cho scheduling. Theo chỉ đạo tiếp theo của người dùng, không dùng bộ 44.273/11.103 ms cũ. Đồng bộ Sections 5.6, 6.9 và 6.10. |
| P0.2 | Table 12 giải trình 398 = 69 admitted + 231 depth mismatch + 6 switch-MSD overflow + 43 ingress=placement + 49 resilience-search failure. CSV có đúng 57 migrations, 12 deployments không thay thế. Baseline 39, cuối 51. Target 30 là số tên active không thuộc baseline, không phải tăng ròng 30 VNF; cuối còn 21 tên baseline và 30 tên mới so với baseline. |
| P0.3 | Giữ thiết kế bốn khối hiện có của Figures 1–2; sửa thứ tự logits → mask → selection → independent validation/reservation, nhánh admitted tới lifecycle và nhánh rejected tới NO_SAFE_ACTION; nhãn Action-Switching Penalty. |
| P0.4 | Eq. 21 chỉ áp dụng khi feasible set khác rỗng. Sections 5.3/5.5 và Algorithm 2 phân biệt finite-logit fallback trong training, all-true prediction mask khi simulator evaluation, guarded search/rejection khi live runtime. NoMask/SoftMSD dùng unmasked distribution và PPO ratio tương ứng. BW nằm ở cả simulator mask và admission, không ở live local reservation. |
| P0.5 | Requested depth được thêm vào request tuple. Section 4.5 phân biệt depth consistency với hardware feasibility, lý do exact-depth contract và cách kiểm tra từng profile. Không dùng mismatch làm bằng chứng overflow. |
| P1.1 | Sections 3.2–3.3/4.5–4.6 giải thích placement, routing-profile anchor, BFS ingress→placement, SID wire order và thời điểm kiểm tra profile; xác nhận không dùng cached candidate paths. Full-chain soundness vẫn là yêu cầu chưa được chứng minh, không tuyên bố hoàn tất multi-VNF validation. |
| P1.2 | Table 23 và Appendix A.2/S25 tách admission-predicate timer khỏi mask/inference. Dùng log sẵn có: synthetic sizes 25/50/100 tại stress, và occupancy 0/25/50/100 trên named substrates 10/14/23 nodes. Chưa có crossed synthetic-size × occupancy/service-count experiment. Không gọi đây là live API admission overhead. Response R5.5 ghi rõ chỉ đáp ứng một phần: 12h không actuation; 3h probe VNF đã steer, không deploy/steer 209 admissions mới. |
| P2.1 | Pointwise bootstrap CI không multiplicity-adjusted; Holm áp dụng p-values. Sửa số resamples primary từ mô tả 10,000 thành 20,000 theo generator thực tế; không đổi kết quả. Nêu exact sign-flip, average-rank ties, drop zeros và all-zero p=1. Timing SD là SD của seed-level P95. Tỷ lệ proposed/admitted violations cùng dùng mẫu số offered requests. Khai triển HIL ở Section 4.4. S1–S24 giữ kết quả của source; S25 bổ sung bảng validation từ raw logs đã có. |
| P2.2 | Sửa `docs/response_rev1.tex`, giữ nguyên cả 20 comment blocks gốc. Dẫn chiếu theo số hình/bảng thực tế sau khi gộp bảng, và nêu rõ các giới hạn chưa có thực nghiệm. |

## Kiểm tra tái lập

- `python scripts/paper/check_tex_inputs.py`: 1 source chính, 50 references nội bộ, 8 figures, 52 citation keys.
- `python docs/AIO-mesh-rev1/evidence/reconciliation_20261124/rebuild_timing.py`: tái tính mean/sample SD của seed-level P95 từ raw CSV hiện có; không chạy lại simulator.
- `python docs/AIO-mesh-rev1/evidence/reconciliation_20261124/check_evidence.py`: 170 checks, gồm input/output SHA-256, 398 terminal outcomes, lifecycle accounting, số liệu bảng giữ lại, 45 cặp mean/SD acceptance được tính lại, timing cells và supplementary lineage. Chi tiết và hashes ở `checks.json`.
- Figure 5: `MPLCONFIGDIR=/tmp/aio-mpl venv/bin/python scripts/rev1/plot_nonhil_studies.py --cost results/rev1/nonhil_studies/20261117_233441/controlled_policy_cost.json --scale results/rev1/nonhil_studies/20261117_235132/topology_scalability.json --matched-summary docs/AIO-mesh-rev1/evidence/reconciliation_20261124/timing_summary.json --output docs/AIO-mesh-rev1/figs/policy_cost_scalability.pdf`.
- Figures 1–2: `MPLCONFIGDIR=/tmp/aio-mpl venv/bin/python scripts/paper/make_architecture_figures.py`.
- Tectonic đã build main marked, main clean, supplementary và response; không unresolved citation/reference, không missing glyph. Hai main PDF có text trích xuất giống nhau. Còn cảnh báo hbox nhỏ của bố cục Elsevier/footnote và hai bảng supplementary; không phải lỗi compile. Đã xem các trang chứa bảng acceptance, HIL, timing, các hình và appendix validation.

Đây là nghiệm thu hiệu chỉnh/source và kiểm tra dữ liệu giữ lại; không chứng nhận thực nghiệm full-chain, ASIC, continuity hoặc multi-hour lifecycle mà artifacts chưa cung cấp.

## Bổ sung sau xác nhận của người dùng

Đã đối soát tiếp với submit1, phục hồi 11 đoạn/khối và Algorithm 1 theo câu chữ/mạch lifecycle gốc. Bảy section chính trùng tên và thứ tự với submit1; xem `SUBMIT1_ANCHOR.md`. Xác minh lại campaign E2E/long run mà người dùng nhắc tới: các record được trích dẫn xác nhận nhiều VNF cùng hoạt động và probe từng VNF; không suy ra phủ định khả năng multi-VNF của hệ thống. PDF marked/clean đã được build lại, text trích xuất trùng nhau, không undefined citation/reference hoặc missing glyph. Citation keys hiện là 53 sau phục hồi citation gốc có bibliography hợp lệ.

## Hoàn tất đối soát baseline toàn bản

Đã rà 42 phần gốc và lập mục 117 đoạn văn, lưu diff trực tiếp submit1→rev1. Hàm mục tiêu tổng quát, MDP/state, evaluation questions và các declaration đã được phục hồi theo submit1; số liệu/công thức implementation vẫn theo evidence. Kiểm tra hiện tại: 175 evidence/baseline checks; 52 references, 8 figures, 53 citation keys. Main marked/clean và response đã build lại, không unresolved citation/reference hoặc missing glyph; text marked/clean giống nhau. Xem `BASELINE_REVIEW.md` và `SUBMIT1_TO_REV1.diff`.
