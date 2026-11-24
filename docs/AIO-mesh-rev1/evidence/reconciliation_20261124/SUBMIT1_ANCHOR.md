# Neo revision theo bản đã nộp

Mốc văn bản là `docs/AIO-mesh-submitted 1/submitted-1.tex`, không phải bản rev1 do các phiên trước biên tập. SHA-256 bản gốc: `8a0a936c540a17e4d17dd791864759dc17a3e29a525ab15e8dc77202a0976113`.

Lượt đối soát bổ sung theo yêu cầu người dùng đã phục hồi 11 đoạn/khối theo câu chữ submit1: research question và ba challenges, đoạn giới thiệu HARP và cách khai triển tên, mở đầu Related Work, đoạn AIOps/MLOps liên quan, đoạn tổng quan learning-based orchestration và citations còn hợp lệ, bốn design principles, hai đoạn lifecycle actuation, hai đoạn phân biệt candidate/admitted, và cả mạch end-to-end lifecycle/Algorithm 1. Chỉ thay cụm từ cần thiết để phản ánh implementation và admission thực tế. Không thay bảng số liệu trong lượt phục hồi này.

| Phần của submit1 | Cách giữ và lý do phần sửa |
|---|---|
| Title, authors, affiliations, keywords; bảy section chính | Giữ nguyên tên và thứ tự của submit1. |
| Abstract | Giữ năm câu mở đầu gốc. Chỉ sửa định vị runtime và kết quả/giới hạn theo R2.1–R2.3 và raw artifacts. |
| Introduction | Giữ chuỗi lập luận gốc: hạ tầng → AIOps → SRv6/MSD → khoảng trống → research question/challenges → AIO-Mesh/HARP → contributions. Abbreviations theo R4.1; không phục hồi tuyên bố ưu thế stress hoặc migration action không phù hợp code. |
| Background and Related Work | Giữ năm subsection và các đoạn nền tảng gốc. Bổ sung safe-RL positioning theo R5.3; tránh biến tích hợp GAT/PPO/masking thành thuật toán mới theo R2.1/R3. |
| System Model | Giữ substrate, request/placement/full-path model, operational objective, requirements. Các sửa về pair action, requested/materialized depth, allocated instances và desired full-chain implication phục vụ P0.5/P1.1. |
| Architecture 4.1–4.2 | Giữ observe–decide–admit–actuate–verify và ba đoạn policy/state management gốc. Thêm Hybrid gate và sửa fallback để vẫn qua admission. |
| Architecture 4.3 | Phục hồi định nghĩa candidate/admitted từ gốc, bổ sung local reservation lock/version và scope state freshness theo R5.4. Không phục hồi các phản ứng lỗi mà artifacts chưa xác minh. |
| Architecture 4.4 | Phục hồi hai đoạn deployment/readiness/MBB/steering gốc, chỉ xác định realization đã đo. Inventory các protocol HIL là bổ sung, không thay thế mô tả kiến trúc. |
| Architecture 4.5 | Giữ vị trí phần giao tiếp data-plane; bổ sung compiler, anchor, SID order, exact-depth contract, MSD predicates và no-cache theo P0.5/P1.1. |
| Architecture 4.6 / Algorithm 1 | Phục hồi mạch toàn lifecycle của submit1. Pair-selection/reservation trở thành bước bên trong; thêm nhánh admission-only và tách migration context khỏi action policy. Không dùng mô tả một HTTP subservice để thay cả lifecycle. |
| HARP 5.1–5.6 | Giữ trình tự MDP → encoder → masking → reward → admission/migration → procedure. Sửa action head, encoder/reward theo owning source; empty-mask, bandwidth và action-switching theo P0.3–P0.4. |
| Evaluation | Giữ các mục benchmark/ablation/HIL/interpretation của gốc; bổ sung matched traces, thống kê, sensitivity và scaling theo phản biện. Dùng số audit được; không phục hồi số cũ chỉ để giống submit1. |
| Conclusion | Giữ hai đoạn kết luận và chủ đề AIO-Mesh. Cập nhật kết quả và diễn giải theo artifact; các giới hạn chỉ nói về bộ campaign được trích dẫn, không kết luận kiến trúc không thể chạy multi-VNF. |

Các bảng vẫn nằm trực tiếp trong main source. Mọi thay đổi tiếp theo phải có chỗ neo trong submit1 và lý do từ checklist/phản biện hoặc source/log; không đổi văn phong đơn thuần hay thiết kế lại paper.

## Xác minh lại campaign multi-VNF người dùng nhắc tới

Người dùng xác nhận đang nhắc campaign E2E và long run. Đã kiểm tra lại chính các record này: 69 admitted request có một `vnf_name`, một realization từ ingress qua các switch tới placement và một target Pod mỗi probe; long run probe lần lượt các VNF đã steer trước. Các run chứng minh nhiều VNF cùng hoạt động, migration ordering và delivery tới các VNF được probe. Các record đó chưa cung cấp quan sát cùng một luồng xử lý qua một chuỗi VNF có thứ tự. Mô tả giới hạn phải gắn với bộ record này, không suy ra kiến trúc không hỗ trợ multi-VNF.

Nguồn kiểm tra: `AIO-mesh-submit-2/results/rev1/hil_e2e_20261121/run/REPORT_E2E.md`, `campaign_corrected_model/requests/*.json`, `long_3h_corrected_model{,_released}/dataplane/targets.json`, và `AIO-mesh-submit-2/scripts/hil/e2e_packet_probe.py`.

## Đối soát đầy đủ sau yêu cầu nhắc lại

Đã lập mục toàn bộ 42 phần gốc và 117 đoạn văn đủ dài trong submit1, kèm đoạn đối ứng và lý do thay đổi. Không dùng số kiểm tra evidence để thay cho kiểm tra nền văn bản. Xem `BASELINE_REVIEW.md`, `submit1_paragraph_review.json` và diff trực tiếp `SUBMIT1_TO_REV1.diff`.

Đã phục hồi thêm hàm mục tiêu tổng quát của submit1 (tách khỏi reward implementation), MDP/state dạng công thức gốc, năm evaluation questions, câu hỏi saturation ở vị trí cũ, lời dẫn/kết cho Algorithm 2, và câu mở đầu Conclusion. Funding, CRediT, Declaration of Competing Interest và AI declaration hiện khớp nguyên văn submit1; grant quay về KC-4.0-56/19-30 vì checklist không yêu cầu đổi tài trợ. Các phần khoa học vẫn được sửa khi source hoặc phản biện buộc phải sửa, đặc biệt action interface/cached paths, reward, số seeds, baseline definitions, các kết quả cũ chưa xác minh và phân loại HIL.

Điểm không phục hồi máy móc: bảng Burst-surge đầy đủ metric cũ, biểu đồ Pareto-optimality và bảng HIL scenario cũ không có cùng bộ evidence xác minh như các kết quả hiện tại; các thay thế tương ứng được liệt kê trong bảng đối chiếu. Giữ revision dựa trên submit1 không đồng nghĩa tái sử dụng các tuyên bố sai về implementation hoặc số liệu chưa audit.
