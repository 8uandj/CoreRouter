# Đối chiếu comment mentor

Xem [hướng dẫn tái lập](../../REPRODUCE.md) và [kết quả chạy lại từng ô](evidence/rerun_report.md). Các mục “một phần” vẫn mở theo tiêu chí nghiệm thu của mentor.

| Mục | Trạng thái | Kết quả hoặc phần còn thiếu |
|---|---|---|
| A1 | Một phần | Có chỉ mục 10 giao thức và hash của các tệp còn lưu. Thiếu manifest gốc của một số run, nên các trường lệnh, commit, checkpoint và trace hash chưa đủ cho toàn bộ giao thức. |
| A2 | Một phần | Tái tạo Bảng 9–11, hình offered-intensity, hai sơ đồ và phụ lục thống kê. Bảng 12 đọc phần hàng đã sinh trước đó. Phần còn lại cần log gốc. |
| A3 | Một phần | Manuscript và thư dùng chung macro cho tổng request, abstract và kết luận dùng macro cho mức chênh lệch theo tải. Chưa có sổ cho tất cả số liệu. |
| A4 | Một phần | Vietnam/Bursty/42 chạy xong. Thiếu dòng gốc để đối chiếu. NSFNET thiếu checkpoint. GEANT2 cần môi trường tương thích normalizer NumPy. |
| A5 | Một phần | Có log đầy đủ 12.325 dòng và 720 mẫu, metadata và generator. Log không giữ toàn bộ HTTP body, không có chuỗi bộ đếm trong run, pcap còn lại chỉ là probe endpoint. |
| A6 | Một phần | Trích metadata và hash 3 checkpoint chính và normalizer. Thiếu lệnh gốc, dữ liệu huấn luyện, tài nguyên máy và checkpoint ablation. |
| A7 | Mở | Chưa có gói dữ liệu đủ để công bố bằng DOI. |
| B1 | Mở | Thiếu per-seed benchmark và CSPF để dùng một quy trình thống nhất cho Bảng 5–6. |
| B2–B3 | Đã sửa | Tính đủ 21 dòng với Wilcoxon exact, cách xử lý ties và zero, Holm, khoảng tin cậy từ bootstrap. Sửa ba đoạn về đỉnh ở 1.2 và giảm ở 1.5. |
| B4–B5 | Một phần | Làm rõ mẫu số của ablation, thiết kế ghép cặp và trace Bursty lặp lại. Bảng 4 vẫn ghi SD tổng thể như export hiện có. Chưa xác minh mọi phần biến thiên của các run gốc. |
| B6–B7 | Một phần | Bổ sung so sánh mô tả với baseline tốt nhất và làm rõ mẫu oracle. Thiếu log bước Greedy/DAI, per-seed benchmark và oracle để tính kiểm định và tỷ lệ toàn run. |
| B8–B9 | Một phần | Bảng 9 thêm tỷ lệ mask rỗng và pruning khi mask không rỗng, bỏ cột từ chối suy ra được. SD mô tả 80 ô seed × workload. Thiếu joint counts để giải thích nguyên nhân và hai ô timing để bổ sung Bảng 8. |
| B10–B12 | Một phần | Tách P95 vòng quyết định và thời gian thành phần có dữ liệu, sửa cách mô tả phần đuôi. Chưa có phân bố timing theo seed, cùng giao thức cho đủ năm policy hoặc log SLA/λ của mọi biến thể. |
| B13 | Đã sửa theo log | Bảng 11 và đoạn HIL báo độ sâu được yêu cầu, profile MSD, mã từ chối, nhánh của các yêu cầu được chấp nhận, RTT, timing backend, tỷ lệ nhận theo giờ và phạm vi readiness. Không suy từ mã MSD ra packet drops. |
| C1–C5 | Một phần | Phân biệt factorized-head và flat-action, xác nhận deterministic inference, sửa GAT, bổ sung định nghĩa ablation, workload và substrate. Cần manifest gốc cho toàn bộ siêu tham số, tọa độ và lịch huấn luyện. |
| C6–C8 | Một phần | Đối chiếu depth theo route anchor và depth của danh sách triển khai. Tách BW simulator khỏi runtime. Chưa hoàn thành bảng ký hiệu và bảng cấu hình theo từng nút. |
| C9–C12 | Đã sửa mô tả chính | Đồng bộ ngưỡng và trọng số reward, bổ sung fallback, phạm vi Hybrid, local version check và simulator empty mask. Giá trị lịch sử của variant vẫn phụ thuộc training archive. |
| D1 | Một phần | Có bảng unprotected theo topology/load từ 84 ô. Cần archive để lập bảng benchmark unprotected. |
| D2 | Mở | Bỏ tuyên bố packet đi tuần tự qua chuỗi nhiều VNF khỏi bản nộp hiện tại. Cần log lịch sử ghép theo packet hoặc phép đo forwarding có ghi đủ. |
| E1–E5 | Một phần | Viết lại abstract và kết luận, thu hẹp diễn giải GAT, thêm giới hạn thí nghiệm, chuẩn MSD/nén SID và related work. Abstract còn một số số liệu chưa được sinh từ macro. |
| E6–E10 | Một phần | Chuẩn hóa nhiều từ viết tắt, nhãn, nguồn tham khảo và tách tải khỏi timing. Cần rà lượt cuối với bản PDF và bảng/hình còn lại. |
| E11 | Một phần | Bản marked dùng xanh lá, có entry point LaTeX cho bản sạch. Hai PDF sẽ được xuất từ Overleaf. |
| F1–F6 | Đã sửa bố cục chính | Vẽ lại sơ đồ, đổi panel so sánh theo SAF-H, đổi timing sang cột và thêm decision P95, chuyển hình trùng số liệu sang phụ lục, mở rộng Bảng 4/13. Cần kiểm tra bản in 100% và vị trí float trên Overleaf. |
| G1–G2 | Một phần | Cập nhật phản hồi Editor và reviewer, giữ nội dung comment gốc, hiệu chỉnh phạm vi và tham chiếu. Cần PI duyệt đoạn mở đầu và so lại đánh số trên PDF. |
| G3 | Chờ PI | Bản nộp đầu ghi **KC-4.0-56/19-30**, bản sửa ghi **KC.01.06/21-30**. Chưa có hồ sơ xác nhận mã đúng hoặc lý do thay đổi. |
| P1-1–P1-9 | Mở | Chưa có thí nghiệm bổ sung đủ tiêu chí. Bản nộp khoanh phạm vi theo các kết quả hiện có, gồm độ thưa topology, triển khai/steering, HARP scaling, trace lặp và Hybrid. |
| P2-1–P2-4 | Mở | Các thí nghiệm tùy chọn chưa chạy. |
