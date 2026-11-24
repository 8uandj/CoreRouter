# Neo bản revision vào submit1

Văn bản nền: `docs/AIO-mesh-submitted 1/submitted-1.tex`, SHA-256 `8a0a936c540a17e4d17dd791864759dc17a3e29a525ab15e8dc77202a0976113`. Bản gốc không được sửa.

Theo yêu cầu mới, bản chính là một revision rút gọn, không phải hồ sơ gom toàn bộ evidence:

- Abstract được sửa trực tiếp từ Abstract gốc; giữ phần mở đầu và cách trình bày, chỉ sửa claim về action/migration, admission và kết quả theo code/log.
- Introduction giữ mạch lập luận và **5 contribution items theo đúng thứ tự gốc**. Hai item đầu và item đánh giá giữ câu chữ gốc; item HARP/masking chỉ sửa để không gán novelty của GAT/PPO hoặc safety của runtime cho policy.
- Giữ bảy section chính, thứ tự MDP → encoder → mask → reward → admission → procedure, cùng mạch observe–decide–admit–actuate–verify. Giữ formulation tổng quát; implementation reward được giải thích riêng.
- Funding, CRediT, competing-interest và AI declarations giữ nguyên bản đã nộp.
- Phần chính có 10 bảng một cột và 5 figures. Bảng/protocol/audit chi tiết chuyển sang supplementary, không chèn tất cả vào bản nộp. Số liệu đầy đủ vẫn được bảo toàn và kiểm tra ở main hoặc supplement.

Các thay đổi khoa học cần giữ: N² pair action thay cho action mode không có trong policy; no-cache compiler thay cho cached K-shortest paths; normalization/reward/fallback theo owning source; và kết quả/denominators theo raw artifacts. Không phục hồi số liệu hoặc claim cũ chỉ để giống submit1.

`BASELINE_REVIEW.md` và `submit1_paragraph_review.json` lập mục 42 phần gốc và 117 đoạn văn; `SUBMIT1_TO_REV1.diff` là diff source trực tiếp. Trạng thái lexical không phải tỷ lệ chứng nhận nội dung tương đương. `check_evidence.py` kiểm tra dữ liệu và các baseline guards riêng.

Phạm vi HIL: campaign E2E và long run xác nhận nhiều VNF cùng hoạt động và probes tới từng VNF, nhưng record được trích dẫn chưa tự xác nhận cùng một luồng đi qua chuỗi nhiều VNF theo thứ tự. Giới hạn chỉ gắn với bộ record hiện có, không phủ định khả năng kiến trúc. Người dùng dự định bổ sung testbed trên server khác.
