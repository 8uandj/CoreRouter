# HIL end-to-end trên testbed 3s-com — 2026-11-21

Phạm vi: Mininet + 10 BMv2 (profile MSD 10/10/5/5/4/8/4/5/10/5), MicroK8s `core-router` (node 3s-com, k8s-master, worker1, worker2), Tekton, backend `3s-com-backend` (model DGRL v11 như run 12h), SDN controller `:8765`. Mọi số dưới đây sinh từ file trong thư mục run này; không có số nào được điền tay hay ép cho khớp kỳ vọng. Đây là **BMv2 phần mềm**, không phải ASIC.

## 1. Chuỗi e2e theo request

Mỗi request có khóa duy nhất (`vnf_name` = `request_id` của `admitted_realization`) và các mốc:
admitted (HTTP 200 + SID list/switch path) → deployment initiated (log `PHASE: MAKE`, PipelineRun) → Ready (log backend, condition Pod) → rule installed (log controller `[sX] route +…`) và read back (`table_dump` trên từng switch của path) → steering verified (`confirm_steer_done` của controller cho đúng request ID) → packet received (VNF vVOC trả lại đúng marker `/e2e/<request>/<seq>`; VNF khác: ICMP echo mang pattern sinh từ request ID).

Đường gói: Linux SRv6 encap trong namespace host nguồn `hS` (`segs` = SID list đã admit) → BMv2 `End`/route theo path → `End.DX4` ở switch placement → `hP` → host `br-k8s-mn` → `vxlan.calico` → Pod; chiều về đi IPv4 thường (không qua P4). Bắt gói ở 4 điểm + counter trước/sau trên từng switch của path.

### 1a. Chiến dịch backend (alert bật → nhánh DRL có actuation, backend tự làm MBB) — `campaign/`

| Chỉ số | Giá trị |
|---|---|
| Request gửi | 148 |
| Admitted (HTTP 200) | 31 |
| Từ chối | 117: "requested MSD depth does not match materialized P4 path depth" 105; "forwarding requires distinct ingress and placement nodes" 12 |
| Steering xác nhận + probe | 27 (+4 ca `BREAK_UNCONFIRMED` trước bản vá 2, steering đã CONFIRMED nhưng driver cũ không probe) |
| Readback đủ rule | 27/27 |
| Gói tới VNF | **540/540** (27 × 20; worker1 22 VNF, worker2 5 VNF) |
| Trong đó là MBB migration | 22 |

Khoảng thời gian (n = 27 request đã steer; P50 / P95 / P99, giây): submit→MAKE 0,186/0,228/0,234; PipelineRun 32/36/37; MAKE→Pod Ready (K8s, độ phân giải 1 s) 17,4/24,2/24,2; MAKE→backend thấy Ready 20,2/26,5/26,5; Ready→controller bắt đầu cài 0,027/0,049/0,082; cài rule + xác nhận 0,554/1,421/2,158; **submit→steering xác nhận 20,8/27,4/27,6**. API RTT (n = 148): 0,127/0,185/0,220. RTT ứng dụng qua SRv6 (P50 theo VNF): 4,1/10,6/10,8 ms. Các thành phần đo riêng, không cộng lại thành P95.

### 1b. Mở rộng inventory (driver điều phối: admission → `/api/deploy` → `/steer`) — `expand/`

Policy runtime vẫn chọn placement/route và admission vẫn kiểm độ sâu/MSD/CPU/RAM; ledger ghi profile dưới đúng tên; Deployment do lifecycle API tạo; steering gọi controller với đúng realization đã admit. 91 request → 19 admitted → 16 steering xác nhận + 3 ca s10 (xem 4.3). Readback 16/16. Probe: worker1/worker2 13/13 VNF nhận 20/20; **k8s-master 3/3 VNF nhận 0/20** (xem 4.4). Submit→steering xác nhận P50/P95/P99 = 20,1/34,2/40,6 s (n = 16).

### 1c. Inventory cuối

**39 VNF** = 7 gốc + 32 mới; 39/39 có profile ledger đầy đủ (`cpu_req`, `ram_req`, `msd_req`, `v_place`, `v_route`, `accounting_unknown=False`), 39/39 Deployment Ready, `unaccounted_vnfs=[]`. Bảng: `inventory_*.csv` (cột `created_by` cho biết lớp bằng chứng).

## 2. Make-before-break — `analysis_mbb/`

23 migration (22 chiến dịch + 1 burst): **23/23 đúng thứ tự** VNF mới Ready ≤ steering xác nhận ≤ yêu cầu xóa VNF cũ. Ready→xác nhận P50 0,61 s; xác nhận→BREAK 1,42 s; BREAK→trạng thái cuối 30,4 s (P95 32,6). 19 `COMPLETED`, 4 `BREAK_UNCONFIRMED` (trước bản vá; VNF cũ thực tế đã bị xóa, ledger được đối soát sau). **Không có tuyên bố zero-downtime**: client gửi tới IP Pod, IP này đổi khi migrate; không đo luồng liên tục qua migration.

## 3. Đối chứng MSD trên data plane live

- **Protected (API live):** trong burst có 2 request bị admission từ chối với "materialized path exceeds physical switch MSD profile" (không tạo Deployment/rule).
- **Tiêm lỗi (bypass admission ở data plane)** trên path đã admit s2(10)–s1(10)–s6(8)–s5(4), 50 gói/độ sâu — `live_fault_injection/`:

| SRH | Echo reply | `msd_violation` +50 tại | advance trước điểm drop |
|---|---|---|---|
| 4 (= độ sâu admit) | 50/50 | — (s5 terminal +50) | s2, s1, s6 |
| 7 | 0 | s5 | s2, s1, s6 |
| 9 | 0 | s6 | s2, s1 |
| 11 | 0 | s2 | — |

Kết hợp với thí nghiệm cô lập trong gói export trước (protected/bypass, 300 gói/ô).

## 4. Sự cố, lỗi đã sửa, giới hạn

1. **Self-migration** (router coi VNF vừa reserve là VNF cũ) → sửa `orchestration_router.py`, test hồi quy.
2. **Pipeline `vnf-migrate-single` lỗi validation** (thiếu `deploymentName`) → vá trên cluster (YAML trước/sau đã lưu).
3. **Chờ Ready 30 s và chờ vắng mặt 30 s quá ngắn** → cấu hình được (180 s / 120 s); thêm `POST /orchestrate/reconcile/{vnf}` (chỉ giải phóng khi K8s xác nhận vắng); 4 bản ghi rò đã đối soát.
4. **Controller từ chối xác nhận mọi path kết thúc ở s10**: bộ so sánh readback hiểu sai MAC nén `0a` (h10). Rule đã cài đúng và gói đi được (probe bổ sung 60/60). Đã sửa code + test, **chưa áp dụng live** vì controller chạy trong tiến trình Mininet (restart = xóa rule của mọi path).
5. **Pod trên k8s-master từng không tới được từ 3s-com** do firewalld chặn Calico VXLAN UDP 4789 và chuyển tiếp từ `vxlan.calico`. Đã vá runtime lúc 18:57–18:58 UTC ngày 21/11 (không `--permanent`; có rollback), ping từ 3s-com tới 4 Pod đạt 3/3 mỗi Pod. Số 0/20 trong campaign là phép đo trước vá, giữ nguyên. Probe lại 4 VNF còn tồn tại đạt 20/20 từng VNF; VNF thứ năm đã bị thay bởi migration nên không thể kiểm lại. Xem `cluster_changes/k8s_master_vxlan/` và `supplemental_probes/corrected_model_after_vxlan_fix/reprobe_summary.json`. Chưa xác minh cấu hình còn hiệu lực sau reboot hoặc `firewall-cmd --reload`.
6. Pod trên worker cần MASQUERADE trên 3s-com để có đường về (rule có tag, có ROLLBACK).
7. Policy v11 dồn placement vào Hue/QuyNhon → với alert, phần lớn actuation là migration; hàng đợi: burst 8 client, request admit thứ 2/3 chờ 52,5/71,1 s ở migration lock trước MAKE.
8. MBB chọn "VNF cũ" theo placement **hoặc route anchor** (`get_vnfs_on_node`), nên có ca migrate một VNF đặt ở Hue sang NhaTrang — cần nêu rõ ngữ nghĩa.
9. Driver bị dừng tay 2 lần (#71, #149) → bản ghi request mất, bằng chứng control-plane được thu hồi (`campaign/recovered_*`), probe bổ sung.
10. Probe tool được sửa giữa chiến dịch (thêm checksum offload off lúc pilot, thêm `--mode icmp`, `--no-capture`); hash công cụ ghi theo từng lần chạy.

## 5. Long run 3 giờ với checkpoint đã sửa

Nguồn: `long_3h_corrected_model{,_released}/analysis/longrun_summary.json`, raw `admission/*/all_records.csv`, `kubernetes_readiness.csv`, `dataplane/stability_probes.csv`, `state_after_longrun.json`. Hai run dùng cùng checkpoint/normalizer đã hash trong summary; đây là hai trạng thái capacity khác nhau, không phải phép thử ghép cặp. `normal_load` chỉ đo admission; các probe data plane nhắm vào VNF đã steer sẵn, không phải 209 request vừa được nhận.

| Chỉ số | Capacity bão hòa (20:16–23:16 UTC, 21/11) | Sau giải phóng capacity (01:27–04:27 UTC, 22/11) |
|---|---:|---:|
| VNF active cuối run; Deployment Ready | 51; 180/180 mẫu, 51/51 | 17; 180/180 mẫu, 17/17 |
| Request; được nhận; timeout | 3.084; 0; 0 | 3.083; 209; 0 |
| Từ chối `msd_violation`; `no_safe_action` | 1.069; 2.015 | 2.585; 289 |
| Decision latency P50/P95/P99 (ms) | 81,434 / 200,214 / 423,067 | 127,563 / 178,671 / 234,335 |
| Data plane: round; VNF khác nhau; gói nhận/gửi | 90; 34; 1.800/1.800 | 90; 9; 1.800/1.800 |
| Pod IP đổi; counter MSD tăng; probe lỗi | 0; 0; 0 | 0; 0; 0 |
| `unaccounted_vnfs` cuối run | [] | [] |

Giữa hai run, lifecycle API giải phóng 34 VNF; log `capacity_release/console.log` ghi active 51→17, CPU ledger trung bình 97,4%→48,0%. Trong run sau giải phóng, 209/3.083 request được nhận (6,78%). Run bão hòa chứng minh từ chối an toàn trong trạng thái gần đầy; run sau giải phóng bổ sung admission thành công. Nhãn `msd_violation` trong workload này không được diễn giải là gói vượt giới hạn MSD vật lý; xem phân rã của run 12 giờ trong gói export cũ.

## 6. Kết luận và điều kiện đóng hồ sơ

Đã có bằng chứng request-correlated cho admission→Ready→rule/readback→steering→gói tới VNF đơn, migration MBB theo thứ tự, fault injection MSD trên BMv2, và hai long run 3 giờ. Không cần run 24 giờ E2E để kết luận trong phạm vi đã đo. Traversal có thứ tự qua chuỗi nhiều VNF vẫn cần một thí nghiệm riêng với thứ tự function, request/path và quan sát gói hoặc ứng dụng tại từng VNF nếu bản thảo muốn tuyên bố khả năng này. Zero-downtime khi migration chưa được đo. Lỗi s10 đã sửa trong source nhưng chưa triển khai vào controller live. Bản vá firewalld trên k8s-master chỉ ở runtime. Những giới hạn này phải đi cùng mọi bảng và phát biểu HIL khi đóng gói.
