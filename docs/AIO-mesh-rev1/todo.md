# AIO-Mesh FGCS Major Revision — TODO

## Mục tiêu của vòng revise

Bản revise phải tách rõ hai lớp đóng góp: **(i) runtime safety contract của AIO-Mesh** là nguồn của thuộc tính fail-closed trước actuation; **(ii) HARP** là một policy có thể thay thế, có nhiệm vụ cải thiện chất lượng/hiệu quả của candidate actions. Không tiếp tục diễn đạt PPO, GAT hoặc invalid-action masking như các thuật toán mới. Claim về safety chỉ giới hạn trong các hard constraints đã mô hình hóa (CPU, memory, SRv6 MSD) và trạng thái mà controller quan sát được.

## P0 — Bắt buộc hoàn thành trước khi resubmit

| ID | Reviewer concern | Công việc phải làm | Đầu ra cần cập nhật trong paper |
|---|---|---|---|
| P0.1 | R2: Elephant và Chaos có số liệu giống hệt nhau | Audit workload generator, config aliases, seed handling, cached CSV/result files và mapping tên scenario. Lưu hash/config của từng workload. Nếu lỗi alias/config, sửa và chạy lại toàn bộ Elephant/Chaos trên Vietnam, NSFNET, GEANT2. Nếu hai workload thực sự cùng tham số, bỏ một workload hoặc định nghĩa lại Chaos. | Thay các dòng liên quan trong Table `simulation_acceptance_summary`, cập nhật mọi prose/figure phụ thuộc số liệu. |
| P0.2 | R2: safety chưa được tách khỏi policy | Chạy **cùng admission boundary** cho Greedy, DAI, SAF-H và HARP. Khuyến nghị thiết kế paired: policy × {unprotected, protected} trên cùng workload trace/seed. | Bảng mới: candidate hard-infeasible rate, rejection CPU/MEM/MSD, safe acceptance, admitted violations, decision latency. Nếu mọi protected policy đều 0 violation, ghi rõ safety thuộc runtime contract. |
| P0.3 | R2: HARP vs SAF-H có margin nhỏ, chưa significance | Tăng số matched seeds: tối thiểu 10, ưu tiên 20 nếu chi phí cho phép. Với HARP vs SAF-H dùng paired Wilcoxon signed-rank trên cùng seed; báo 95% bootstrap CI, paired rank-biserial effect size; Holm correction khi thực hiện nhiều comparisons. Không chỉ báo mean±std. | Bổ sung thống kê vào bảng chính hoặc bảng phụ; prose phải dùng “statistically significant” chỉ khi test hỗ trợ. |
| P0.4 | R2: compact action/anchor chưa xác định đầy đủ chain | Đối chiếu code để xác định chính xác `v_place` áp dụng cho function nào/chain-level template nào; mô tả thuật toán dựng `phi_q`, các segment paths và full SID list từ `(v_place,v_anchor,m)`. Tạo test với chain ≥3 VNFs và đối chiếu `h_q` giữa mask/admission/controller. | Hoàn thiện Sec. System Model, HARP MDP, Algorithm 2; không để TODO semantics. |
| P0.5 | R2/R4/R5: không có end-to-end decision latency/scalability | Đo riêng: state construction, feasible-set/mask construction, HARP inference, heuristic inference, final admission validation, controller handoff, total decision latency. Báo median/P95/P99 và throughput decisions/s. Vary topology size + active chains + concurrent requests. | Subsection/figure/table scalability; cập nhật Complexity và Limitations. |
| P0.6 | R2: path cache có thể tạo false infeasibility | Chạy sensitivity với `K={1,3,5,10}` (thêm 20 nếu chi phí thấp). Cùng workload/seeds. Đo safe acceptance, no-feasible-cached-realization rate, mask time, cache memory, average feasible alternatives/action. Không gọi cache miss là “global infeasibility”. | Figure/table K-sensitivity; sửa terminology toàn paper. |
| P0.7 | R2: Hybrid predicate chưa định nghĩa | Trích đúng logic `IsStable(T_t)` từ code: biến telemetry, threshold, window, hysteresis, alert trigger, migration trigger. Nếu logic hiện tại ad-hoc, chuẩn hóa trước khi rerun Hybrid. | Sec. Architecture + Algorithm 1 + Experimental Setup. |
| P0.8 | R5: feature normalization, mask frequency, stale state, TOCTOU | Liệt kê đúng 6 node features + 13 global features, unit/source, normalization/clipping; ghi mask refresh trigger/frequency; telemetry interval; state timestamp/version; freshness TTL. Kiểm tra có resource reservation/version check hay chỉ revalidation. Nếu chưa có atomic reservation, không được claim là đã có. | Table feature definitions; Sec. HARP encoder/masking; Sec. Telemetry Freshness; Limitations. |

## P1 — Nên hoàn thành để vòng major revision thuyết phục

| ID | Reviewer concern | Công việc đề xuất | Đầu ra |
|---|---|---|---|
| P1.1 | R2: load sweep chỉ có một curve | Regenerate load sweep 0.2x–1.5x cho HARP, SAF-H, Greedy+Admission, DAI+Admission trên matched traces. | Thay `VN_load_sweep.pdf`; nên thể hiện safe acceptance + rejection/infeasible pressure; admitted violation có thể ở panel riêng nếu luôn 0. |
| P1.2 | R4/R5: topology nhỏ | Thêm topology synthetic/extended khoảng 50, 100, 200 nodes nếu runtime cho phép; nếu 200 quá nặng, báo giới hạn thực nghiệm và dùng 25/50/100. Giữ normalized load tương đương. | Scalability figure/table. |
| P1.3 | R5: services/concurrent chains | Vary active chains và concurrent requests, ví dụ các mức thấp/trung bình/cao phù hợp implementation; ghi rõ queueing policy. | Scalability table + throughput/latency curves. |
| P1.4 | R5: long-running stability | Chạy HIL liên tục tối thiểu vài giờ; ưu tiên 24 h nếu khả thi. Ghi total requests, admitted/rejected, rejection by constraint, migrations, controller/deployment failures, telemetry/mask refresh failures, latency drift, admitted MSD violations. | Subsection “Extended HIL stability”. Không gọi là production case study nếu không chạy trên carrier production. |
| P1.5 | R5: practical MSD consequence | Tạo controlled over-MSD test: cố ý tạo SID list > MSD, ghi controller/admission outcome và BMv2/P4 counter/log. Phân biệt rõ target-specific behavior; không suy rộng BMv2 thành mọi ASIC. | 1 đoạn motivation + 1 row/table/log summary; có thể dùng appendix nếu dài. |
| P1.6 | R2/R5: masking role | **Hoàn tất 2026-11-17:** đã báo tỷ lệ candidate bị mask, runtime rejection, admitted hard violations và safe acceptance trên matched traces cho Vietnam, NSFNET, GEANT2 (20 evaluation seeds × 4 workload × 7 variants); paired SoftMSD admission bật/tắt dùng cùng checkpoint. | Bảng/prose E3 trong `rev1.tex`; tổng hợp và provenance tại `evidence/e3/`. |
| P1.7 | R4: abbreviations | Audit toàn bộ source: expand first occurrence only cho AIOps, MLOps, SFC, VNF, SRv6, MSD, PPO, GAT... | Clean source; không lặp long form sau first definition. |

## Hình cần sửa/bổ sung

1. **`figs/overview.pdf`**: làm rõ ba khối theo thứ tự `Policy/Heuristic -> independent runtime admission -> actuation`. Gắn nhãn HARP là “replaceable policy instance”; không vẽ masking như nguồn duy nhất của safety. Thêm state version/freshness vào đường telemetry nếu implementation có.
2. **`figs/VN_load_sweep.pdf`**: thay single-method curve bằng multiple protected baselines; ưu tiên 2 panels: (a) safe acceptance; (b) runtime rejection/hard-infeasible pressure. Nếu admitted violation của tất cả protected methods đều 0 thì có thể biểu diễn bằng annotation thay vì curve chồng nhau.
3. **`figs/testbed.pdf`**: thể hiện rõ protected vs bypass path; mọi protected policy phải đi qua cùng Admission Boundary. Nếu thêm protected Greedy/DAI, figure không cần đổi logic nhưng caption phải nói common boundary.
4. **Hình mới — K sensitivity**: x=`K`; y1=safe acceptance, y2=mask latency/cache memory hoặc dùng bảng nếu figure quá dày.
5. **Hình mới — Scalability/latency**: x=number of substrate nodes; đường riêng state/mask/inference/validation/total hoặc dùng stacked bars cho latency decomposition. Không gộp actuation time vào decision latency; báo actuation riêng.
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
- Conclusion: sau khi hoàn tất experiments, thay câu mang tính kế hoạch bằng 1–2 quantitative findings mạnh nhất; giữ conclusion khoảng 2 đoạn
