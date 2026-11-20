# Thiết kế vòng revise AIO-Mesh — 2026-11-16

Trạng thái: người dùng yêu cầu triển khai ngay; đang phục hồi `rev1.tex` và audit evidence trước experiments.

## Mục tiêu và nguồn tham chiếu

Chuẩn bị bản major revision FGCS trả lời đầy đủ `review.txt`, kế thừa tối đa submitted và chỉ công bố kết quả truy được về evidence. Định vị đóng góp ở runtime admission cho CPU/RAM/SRv6 MSD; HARP là policy có thể thay thế. Không coi GAT/PPO/masking là thuật toán mới.

Lineage người dùng đã xác nhận:

- Concept: `docs/thesis_JOVPPM/`.
- Baseline manuscript và số liệu: `docs/AIO-mesh-submitted 1/submitted-1.tex`.
- Historical source chung ba topology: `CoreRouter/` trên `HARP-model`.
- Workflow Kaggle chung: `notebook/vietnam.ipynb`; chỉ thay config theo mạng. Chưa chốt mọi override của NSFNET/GEANT2.
- Revise tại `docs/AIO-mesh-rev1/`; historical source/results giữ nguyên.

Reference tải về: `1badfd486d5d303ecdeba2f04cd7626163b3a8bd`. Đây là mốc audit hiện có, không tự nhận là commit chính xác tại thời điểm chạy Kaggle.

## Các hướng đã cân nhắc

1. **Kế thừa submitted, audit rồi sửa/rerun có mục tiêu — lựa chọn đề xuất.** Tận dụng raw per-seed có sẵn, thu hẹp claim không có bằng chứng; mọi kết quả thay đổi phải có lineage và protocol rõ. Phù hợp nguyên tắc của `todo-2.md` và context đã chốt.
2. Chỉ chỉnh manuscript theo checklist đã tick: ít công nhưng chưa giải quyết evidence/protocol và các lỗi semantic.
3. Xây lại toàn bộ runtime, chain realization, K-cache và train tất cả từ đầu: phạm vi lớn, thay đổi đối tượng đánh giá; chỉ phù hợp nếu audit chứng minh bắt buộc. Không chọn làm mặc định.

## Phạm vi và ranh giới

- E1 → E2 → E3 → E4 → E6; E5 chỉ khi runtime cuối thực sự có K-cache. Không tạo E7/E8.
- Sửa documentation dựa trên implementation thật; không tự phát triển full-chain runtime, distributed transactions hay cache chỉ để khớp prose.
- Tuy vậy, nếu predicate CPU/RAM/MSD sai thì thu hẹp prose không đủ: phải sửa predicate và rerun thí nghiệm bị ảnh hưởng trước khi gọi cấu hình đó là MSD-safe.
- Benchmark/training dài chạy trên Kaggle, HIL trên testbed tương ứng; local chỉ inventory, unit/integration smoke, phân tích artifact và biên tập.
- Tách historical reproduction khỏi revision evaluation; train mới không được gọi là khôi phục checkpoint cũ.
- Bảo toàn các thay đổi người dùng đang có, gồm việc chuyển Python notebook exports vào `notebook/`. Không dùng `git add -A` để commit công việc revise khi còn thay đổi không thuộc task.

## Các chốt kỹ thuật trước thực nghiệm

1. Chốt pair-level action, observation/normalization, empty-mask behavior, hybrid gate và giới hạn controller-visible state bằng tests/trace.
2. Audit riêng MSD theo độ sâu từng SID list với cách cộng `_state[...,2]` hiện có; audit resource reuse/routing-only/MBB/release. Không dùng resource accounting tích lũy làm chứng minh parser-depth safety.
3. Chốt model/normalizer theo topology/variant bằng đường dẫn và hash rõ ràng. Tránh model auto-resolution đổi từ main v11 sang ablation `harp_full` sau khi bổ sung file.
4. Matched seed chưa đủ nếu policies tiêu thụ RNG khác nhau: phải replay cùng request trace bất biến.
5. Metric contract phân biệt offered/admitted/safe-admitted/deployed/violated, candidate và request denominators, sample/population std của số cũ.

## Nghiệm thu tổng thể

- Mọi reviewer concern có response, vị trí sửa và evidence hoặc limitation cụ thể.
- Mọi số mới có manifest, raw outputs, config, seeds, source/data/model hashes; không suy từ checklist hoặc aggregate không có provenance.
- E1 soundness/claim scope đã được chốt trước khi chạy E2/E3; mọi benchmark sửa semantics/workload đều lưu protocol mới.
- Manuscript Rev1 build được với template `elsarticle` của submitted, không TODO/placeholder, undefined references hoặc missing assets. Không tự chuyển sang IEEE chỉ vì todo cũ nhắc tới.
- Chưa có HIL/log tương ứng thì không tuyên bố 24h, carrier-grade, full-chain soundness hoặc zero downtime.

Chi tiết task và tiêu chí đóng nằm trong `REVISION_PLAN.md`. Các quyết định phạm vi ở đây là đề xuất của kế hoạch; các xác nhận nguồn lịch sử ở trên là thông tin người dùng đã chốt.

## Chronology có hiệu lực từ xác nhận mới nhất

`todo.md` là yêu cầu gốc; draft `rev1.tex` được sửa từ submitted với các số liệu mới do người dùng xác nhận đã bịa; `todo-2.md` là yêu cầu tiếp theo của mentor. Vì vậy không dùng số liệu mới hoặc completion ticks làm evidence. Sửa trực tiếp draft hiện có, backup trước thay đổi; giữ historical submitted/raw artifacts bất biến. Priorities: integrity recovery → E1 → E2 → E3 → E4 → E6; E5 có điều kiện. Không bịa số thay thế và không xây lại toàn bộ runtime khi chưa audit.
