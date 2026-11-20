# Phục hồi integrity của bản Rev1

Người dùng xác nhận ngày 2026-11-16: `todo.md` là yêu cầu ban đầu; draft `rev1.tex` được sửa từ submitted với số liệu bịa; mentor sau đó đưa `todo-2.md`. Không coi draft/checklist là bằng chứng thí nghiệm.

Backup trước sửa: `.workspace-sync/rev1-recovery-20261116T103938Z/`, có `manifest.json` và SHA-256. Không thay historical source/raw artifacts.

Đã rút khỏi active manuscript: revised 20-seed benchmark/ablation, CI/p/effect/significance claims, ten-run HIL count, 24h counts/latency drift, injection packet-loss result, timing/scalability/concurrency tables và biểu đồ liên quan. Số trong checklist E6 cũng chưa phải target phải đạt hoặc evidence: draft ghi 18,150/5,620/1,230 còn checklist ghi 17,820/5,910/1,270; không chọn một bộ vì tổng khớp.

Thay bằng descriptive historical CSV reconstruction cho Vietnam/NSFNET, giữ nhãn historical. 120 benchmark rows dùng population SD (ddof=0 theo exporter); 180 ablation rows dùng sample SD (ddof=1 theo notebook). Điều này giải thích một số SD khác paper; không chỉnh raw để khớp paper. Mẫu số MSD/admitted/SLA của ablation trong source là offered non-skipped steps, không phải admitted requests như draft cũ mô tả. Bảng hiện chỉ dùng historical safe-acceptance field và latency; không tái diễn giải thành chứng minh physical safety.

Đã rút implementation claims về RealizeChain/ValidateAndUpdateReservation. Model hệ thống đầy đủ được giữ như requirement; source limitations được mô tả riêng. Current simulator, runtime policy interface, corrected main retrains, and existing ablation variants use flat `Discrete(N²)` pair actions. Archived pre-retrain v10/v11 checkpoints have factorized `2N` heads and remain supported only through the compatibility adapter; they are not the current primary benchmark inputs. Agent has a shadow-mode branch and fallback on inference errors; a method label does not prove a learned model was run. See the 2026-11-20 action-space update in `REVISION_STATUS.md`.

Test output và tiến độ ở `REVISION_STATUS.md`. `git diff --check`/static LaTeX checks không thay thế compile PDF hoặc thực nghiệm.
