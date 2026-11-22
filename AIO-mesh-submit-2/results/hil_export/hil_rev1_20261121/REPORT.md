# Gói bằng chứng HIL/testbed cho bản sửa AIO-Mesh (rev1) — 2026-11-21

Máy: `3s-com` (server testbed "246"), repo `/home/CoreRouter`, nhánh `HARP`, commit `6515a54` (không có thay đổi tracked). Gói này **không sửa** bất kỳ log, checkpoint, cấu hình hay số liệu cũ nào và **không sửa manuscript**. Mọi số dưới đây sinh từ script trong `scripts/`; `scripts/check_export.py` kiểm tra lại checksum và tái sinh byte-identical.

Phân loại: **[CŨ]** = dữ liệu gốc 17–18/11/2026, chép nguyên byte (đối chiếu SHA-256); **[MỚI]** = thí nghiệm chạy ngày 21/11/2026.

## 0. Kiểm kê trước khi thao tác

- Process/tmux: tmux `corerouter-p4` chạy Mininet + 10 BMv2 (`simple_switch` khởi động 2026-11-17 18:16:40–48 UTC, không restart từ đó), SDN controller `:8765`, backend container `3s-com-backend` (khởi động 2026-11-17 18:07 UTC, 0 restart). Không có runner/benchmark nào đang chạy. Các container khác (ONAP, zerotrust, fe, ids-agent…) không thuộc dự án — không chạm.
- Tài nguyên: 32 CPU, load ~4, RAM còn ~55 GiB, **disk `/` 95% (còn ~11 GB)** → gói giữ ở ~70 MB; pcap 95 MB chỉ tham chiếu.
- Hướng dẫn: `docs/hil/PLAN_RUN_TESTBED_246.md` (Gate 5: không chạy HIL đầy đủ khi chưa có mapping→readback→packet đã kiểm), `docs/hil/DEPLOYMENT.md` (cấm sửa host). Snapshot: `00_inventory/at_start/`.
- Không dùng sudo; không đổi route/bridge/firewall/qdisc; không đụng switch live, Mininet, VM hay `/home/dis/deploy/*`.

## 1. Artifact gốc HIL 12 giờ [CŨ] — tìm thấy, bảo toàn, đối chiếu

| Yêu cầu | Kết quả | Vị trí trong gói |
|---|---|---|
| 12.325 request | Có. `all_records.csv` = 12.325 dòng; bản trong `scenarios/` và `benchmark_results.json` trùng khít (hash/chuỗi status) | `01_hil12h/original/e6_12h_control_plane/runs/20261117_190242/` |
| 720 mẫu readiness | Có. 720 mẫu, cách 60,00–60,06 s, 7/7 Deployment và 7/7 replica Ready ở mọi mẫu, 0 lỗi | cùng thư mục |
| Run manifest / lệnh / commit / cấu hình / thiết bị | `run_manifest.json` (seed 42, 3,5 s, 1 worker, no reset, MSD 10/10/5/5/4/8/4/5/10/5, 32 CPU, Python 3.8.10, torch 2.4.1, sb3 2.4.1), `run_provenance.json` (commit `a2276588`, image backend, hash source), `preflight.json`, `CONTROL_PLANE_SCOPE.json` | cùng thư mục |
| SHA-256 | 6/6 hash trong `docs/AIO-mesh-rev1/evidence/run_index/hil12h.json` khớp. Hash source runner/sampler (5 file) và backend trong container (8 file) đều khớp hash ghi lúc chạy và khớp repo hiện tại. 710/752 mục trong 35 manifest SHA-256 ngày 17/11 khớp; 5 lệch là báo cáo được sửa 4–36 phút sau khi ghi hash cùng ngày 17/11; 32 lệch là file nguồn/manifest cố ý thay đổi; 5 thiếu là file `/tmp` và seed đã di chuyển | `generated/recorded_hash_verification.csv`, `ORIGINAL_SOURCE_INVENTORY.csv` (1.398 file nguồn được hash; 306 file chép, 306/306 khớp sau khi chép) |
| Log controller/Kubernetes | Access log backend (docker) cho cửa sổ 19:02–07:03: **12.325 POST `/api/orchestrate` (1.455×200, 10.870×409), chuỗi mã trạng thái trùng từng vị trí với log client**; 1.455 `/free` (200) khớp 1.455 lần nhận, không lần free nào đi trước admission tương ứng; lệch thời gian client−server P50 0,68 ms. Console controller: 0 dòng trong cửa sổ (không có hoạt động P4). Kubernetes: **0 PipelineRun được tạo trong cửa sổ**; events đã hết hạn lưu | `01_hil12h/recovered_logs/`, `generated/hil12h/crosscheck_hil12h.json` |
| Counter `msd_drops` | Preflight 19:02: 0 ở cả 10 switch; runner đọc lại cuối run: `msd_drop_delta = 0`; đọc lúc export (21/11): vẫn 0 (switch không restart). **Run không gửi gói nào qua P4**, nên đây không phải phép đo drop | `crosscheck_hil12h.json` → `msd_drops` |
| Inventory 50 Deployment | Có. Snapshot 2026-11-17 ~12:36 UTC: 50/50 Ready, trùng danh sách 50 tên; 7 giữ + 43 retire; sau retire đúng 7. **Không phải trạng thái trong run 12h** | `03_inventory50/`, `generated/inventory50_summary.json` |
| Log forwarding/pcap | Chỉ có probe chẩn đoán ngày 17/11 (xem mục 2). Không có `results/raw/forwarding` | `02_forwarding_overmsd/original/` |

**Request ID:** run không ghi request ID tường minh. Gói dùng khóa suy ra `hil12h-20261117T190242-step<NNNNNN>` (step duy nhất 12.325/12.325); request được nhận có `vnf_name` do server sinh (1.455 tên duy nhất). Không bịa ID khác.

**Table 11 tái sinh từ log gốc trong gói: trùng byte với `docs/AIO-mesh-rev1/generated/table11.tex`.** Các trường còn thiếu trong log gốc: thân HTTP/thông điệp lỗi của 10.870 request bị từ chối; placement/route của request bị từ chối; operation ID/realization của request được nhận; chuỗi counter theo thời gian; events Kubernetes.

### Sai lệch diễn giải cần tác giả sửa (không tự sửa số)

1. **Dòng "MSD rejection 9.672 (78,47%)"**: nhãn `msd_violation` được gán khi thông điệp lỗi chứa chữ "msd" (`orchestration_router.py`). Với workload `normal_load`, `msd_req` = 1 (URLLC/VoIP) hoặc 2 (Data/Video); `compile_pair_path` đòi `msd_req` **bằng** độ sâu path vật lý source→placement (≥ 2 vì source ≠ placement); MSD nhỏ nhất = 4. Do đó **không request nào trong run có thể vượt giới hạn MSD**: 4.501 ca `msd_req=1` là lệch độ sâu chắc chắn theo cấu trúc; 5.171 ca `msd_req=2` chỉ có thể là placement không kề source. Đề xuất đổi nhãn thành "SID-depth/path mismatch" (`generated/hil12h/reject_decomposition.csv`).
2. **Câu "MSD counters were read only during preflight" (rev1.tex dòng 877)**: runner còn đọc ở cuối run (`msd_drop_delta = 0`). Nên viết: delta đầu–cuối = 0 nhưng không có traffic P4.
3. **0 từ chối CPU/RAM**: mỗi request được nhận bị giải phóng sau TTL (10–50 bước generator) qua `/free` (1.455/1.455); lỗi `placement_node_full` được ánh xạ sang `placement_capacity` (cũng 0).
4. **Policy = Hybrid:DRL dù preflight ghi `hybrid_mode: heuristic`**: cổng hysteresis (bật 0,45 / nhả 0,35); utilization nền 0,426 giữ mode DRL (mode hiện tại vẫn `drl`).
5. "Other no-safe-action" (1.198) là nhánh mặc định; thông điệp gốc không được lưu nên không phân rã thêm được.

## 2. Bằng chứng chuỗi nhiều VNF [CŨ] — không tìm thấy

Đã tìm: `results/hil/{rebuild_20261117T123405Z, rebuild_20261117T122432Z, manual-20261117_094746}`, `results/rev1/{e6_12h,e6_24h}_control_plane`, `results/benchmark_testbed/2026051*` (11 run API tháng 5: không có thứ tự function, pcap hay migration thành công; `msd_drop_delta=0`), `results/raw` (không tồn tại), mọi `*.pcap*` dưới `/home/CoreRouter` và `/home/dis` (18 file, đều ở `rebuild_20261117T123405Z`), `docs/hil`, `docs/AIO-mesh-rev1/evidence/run_index/forwarding.json`. Không có manifest request, thứ tự function hay trace theo từng VNF cho chuỗi nhiều VNF.

Probe đã có (`generated/forwarding_history_evidence_matrix.csv`), đều thủ công, không gắn request, đích là **một** Pod placeholder (`alpine sleep`, không listener):

| Probe 17/11 | SID list | Rule/readback | Bằng chứng từng điểm | Kết luận |
|---|---|---|---|---|
| phase12 | s1→s6→s9 (độ sâu 3) | /bootstrap HTTP 500 (lỗi comparator s9) | counter s1 15, s6 92, s9 385; `phase12_s6_out.pcap` 935.092 gói | Thất bại — vòng lặp khi OVS còn hoạt động |
| phase13–14 | như trên | HTTP 200, readback 3/3 | advance s1/s6 = 5, terminal s9 = 6; capture h9 = 0 | Một phần — không thấy frame sau s9 |
| phase16–19 (ICMP id 246 seq 15) | như trên | không đọc lại | 1 frame tại s9-eth1, h9-eth0, veth h9, veth host, vxlan.calico (TTL 64/63/62); không capture trong Pod; không reply | **Chỉ là endpoint probe**, không phải bằng chứng toàn chain |
| isolated-v1 (14:48) | 2 BMv2 cô lập | CLI, readback 3 entry | 1 gói trong giới hạn tới sink; 1 gói độ sâu 5 bị drop (counter +1) | n=1, không có đối chứng admission |

## 3. Thí nghiệm mới trên testbed live có actuation — CHƯA CHẠY (cần quyết định)

Source hiện tại có đủ chuỗi admission → Tekton → Ready → `/steer` → controller cài rule + readback → `confirm_steer_done` (chỉ nhánh DRL + forecast alert). Tôi **không** chạy vì: (a) tạo Deployment mới trong `core-router` và cài rule lên 10 BMv2 live dùng chung, controller không có API teardown rule; (b) gửi/bắt gói trong namespace Mininet host/Pod cần quyền tương đương root (container `--privileged` + `nsenter`), trái ràng buộc "không sudo nếu chưa được phép"; (c) Pod baseline là placeholder không có listener, cần dựng VNF có endpoint (vd. `vnf-voc` `/echo`). Xem mục "Cần quyết định".

## 4. Đối chứng over-MSD protected/bypass trên BMv2 [MỚI]

Môi trường: container dùng một lần `p4lang/p4app` (`--network none`, chỉ `NET_ADMIN/NET_RAW` trong namespace riêng), BMv2 1.13.0, JSON profile **trùng hash** với profile đang nạp trên s1–s10 live. Quyết định admission và rule do **code thật của repo** sinh offline (`compile_pair_path`, `compile_p4_forwarding_rules`); mỗi trial khởi động switch mới, cài local SID như controller bootstrap, readback toàn bộ bảng, đọc counter trước/sau, gửi 100 gói đánh số, bắt gói ở egress từng switch và sink. 3 trial/ô. Lệnh: `04_new_experiments/overmsd_isolated_20261121/COMMAND.txt`.

| Ca | Chế độ | Path (MSD) | Độ sâu | Admission | Rule (readback) | Gửi | Nhận | `msd_drops` |
|---|---|---|---|---|---|---|---|---|
| depth 2 | protected / bypass | s6(8)–s7(4) | 2 | admit / bypassed | 2 (2) | 300 / 300 | 300 / 300 | 0 / 0 |
| depth 4 = MSD s7 | protected / bypass | s2(10)–s1(10)–s6(8)–s7(4) | 4 | admit / bypassed | 4 (4) | 300 / 300 | 300 / 300 | 0 / 0 |
| **depth 5 > MSD s7** | **protected** | s2–s1–s6–s7(4)–s8(5) | 5 | **reject**: "materialized path exceeds physical switch MSD profile" | **0** (5 rule vắng khi readback) | **0** | 0 | 0 |
| **depth 5 > MSD s7** | **bypass** | như trên | 5 | bypassed | **5 (5)** | **300** | **0** | **300, tất cả tại s7** |

Trong ca bypass: egress s2, s1, s6 mỗi nơi 100 gói/trial, egress s7 = 0, log BMv2 s7 có 100× `SRv6SegmentDepthExceeded`/trial. Thời gian cài 5 rule bằng CLI: P50 352 ms; readback toàn bộ bảng 5 switch: P50 1.033 ms (3 trial; đây là thời gian CLI trong container, không phải độ trễ controller live). Bảng: `generated/overmsd/overmsd_table.{csv,tex}`. Lần chạy 1 dừng ở readback đầu tiên do lỗi regex của script (không gửi gói), lưu tại `attempt1_failed_parser_bug/`.

Giới hạn: BMv2 phần mềm trong container cô lập, không phải topology Mininet live hay ASIC; "protected" nghĩa là admission từ chối nên không có rule/gói nào được steer (không đo nguồn gửi gói trái phép); admission gọi hàm thật nhưng offline, không qua HTTP API.

Bổ sung cho E4 (mức ràng buộc MSD): trên đồ thị P4 10 switch thật, chỉ **8/90** cặp (source, placement) có path vượt MSD vật lý (đều độ sâu 5, qua s5 hoặc s7) — `plan.json` → `pair_depth_table`.

## 5. Tiêm SID độ sâu 7 > MSD 4 (todo-2 E6) [MỚI]

Cùng môi trường cô lập. Request ở độ sâu thật được `compile_pair_path` chấp nhận và rule được cài + readback; sau đó tiêm gói SRH 7 SID (SID của path + SID đã đi qua, Segments Left = độ sâu − 1). Đối chứng: gói đúng độ sâu trên cùng path. 3 trial × 100 gói.

| Path đã admit (MSD) | Gói | Gửi | Nhận | `msd_drops` | Advance trước điểm drop |
|---|---|---|---|---|---|
| s2(10)–s1(10)–s6(8)–s7(4), độ sâu 4 | đối chứng độ sâu 4 | 300 | 300 | 0 | s2, s1, s6: 300 mỗi switch |
| như trên | **tiêm độ sâu 7** | 300 | **0** | **300 tại s7** | s2, s1, s6: 300 mỗi switch |
| s7(4)–s6(8), độ sâu 2 | đối chứng độ sâu 2 | 300 | 300 | 0 | s7: 300 |
| như trên | **tiêm độ sâu 7** | 300 | **0** | **300 tại s7 (ingress)** | không có |

Bảng: `generated/injection7/`. "Fallback outcome": data plane chỉ drop và đếm; không có cơ chế fallback/BSID (đúng thiết kế P4), không có thông báo lên controller ngoài counter.

## 6. Concurrency của API admission trên testbed live [MỚI]

Script `scripts/run_admission_concurrency.py`: trace của `run_concurrency.build_request_trace` (seed 42/43/44 × 200 request), C = 1, 2, 4, 8, 16, tối đa C request đang bay; **không reset ledger, alert tắt, không có Attack/pps → không thể actuation**; mỗi reservation được nhận được giải phóng theo TTL qua `/free`, trạng thái được kiểm về 7 VNF baseline sau mỗi mức. Kết quả 2026-11-21 16:43–16:49 UTC: 3.000 request, 0 lỗi 5xx/timeout, 0 actuation, 353/353 lần giải phóng thành công, baseline và counter `msd_drops` không đổi (0).

| C | Offered | Admitted | Ops/s (TB 3 seed) | RTT P50/P95/P99 (ms) | Handler P95ᵃ | Chờ ngoài handler P95ᵃ |
|---|---|---|---|---|---|---|
| 1 | 600 | 71 | 10,73 | 91,3 / 135,4 / 161,1 | 148,6 | 4,9 |
| 2 | 600 | 71 | 10,51 | 182,2 / 272,2 / 317,3 | 152,6 | 154,1 |
| 4 | 600 | 70 | 10,14 | 348,7 / 523,1 / 584,2 | 183,1 | 387,2 |
| 8 | 600 | 69 | 9,02 | 724,0 / 1.120,6 / 1.303,6 | 158,9 | 966,7 |
| 16 | 600 | 72 | 9,36 | 921,8 / 1.966,1 / 2.324,7 | 154,0 | 1.887,6 |

ᵃ Chỉ request được nhận (server chỉ trả timing kèm HTTP 200). "Chờ ngoài handler" = RTT client − `server_decision_ms`.

Diễn giải: throughput không tăng theo C (~9–11 ops/s) trong khi thời gian xử lý trong handler gần như không đổi, còn thời gian chờ tăng gần tuyến tính → backend (1 worker uvicorn, handler async gọi code chặn) **xử lý tuần tự**; concurrency chỉ tạo hàng đợi. Lý do từ chối giống run 12h (`msd_violation` = lệch độ sâu, `no_safe_action`). Ops/s chỉ đếm `/orchestrate`; các lệnh `/free` (353) cũng tải lên cùng server. Không đo deployment/readiness/steering/migration (không actuation).

Attempt 1 (16:36 UTC) **không hợp lệ**: script của tôi gửi `/free` thiếu trường bắt buộc → 37 lần HTTP 422, 37 reservation (chưa actuation, không có Deployment) tồn tại ~7 phút và làm đầy capacity. Đã giải phóng đúng 37 tên đó qua `/free` lúc 16:43 UTC; ledger trùng bản sao lưu trước khi chạy ở mọi trường trừ `state_version` tăng đơn điệu. Chi tiết: `04_new_experiments/admission_concurrency_attempt1_free_bug/NOTE.md`.

## 7. Gói export, kiểm tra và sao chép

- Ánh xạ mentor ↔ manuscript ↔ bằng chứng: `MENTOR_MAPPING.csv` (A5, B13, D2, P1-2, P1-3, E4/E6).
- Kiểm tra: `/home/CoreRouter/venv/bin/python scripts/check_export.py .` — xác minh `SHA256SUMS` và tái sinh byte-identical mọi bảng trong `generated/` từ dữ liệu trong gói.
- Trạng thái testbed sau cùng: 7 VNF baseline, `unaccounted_vnfs=[]`, alert tắt, mode `drl`, steer `idle`, `msd_drops` = 0 trên 10 switch; không có rule, Deployment hay PipelineRun mới. Snapshot: `00_inventory/at_end/`.
- Lệnh sao chép: `COPY_TO_SUBMIT2.md`.

## Cần quyết định (để làm P1-2, lifecycle probe, MBB)

1. Cho phép actuation trên testbed live: tạo VNF thử (đề xuất `vnf-voc` có `/echo`) qua `/api/orchestrate` với alert, để controller cài rule lên BMv2 live. Controller **không có API xóa rule**; rule sẽ còn đến khi topology restart, trừ khi cho phép xóa bằng `simple_switch_CLI table_delete` theo handle (như phase 12).
2. Cho phép quyền tương đương root để gửi/bắt gói trong namespace Mininet/Pod (container `--privileged` + `nsenter`, như phiên 17/11). Không có quyền này thì chuỗi chỉ dừng ở "steering verified", thiếu "packet received".
3. Có muốn thu log dài giờ (ví dụ 6–12 giờ, admission-only, `--no-reset`) không. Chưa chạy vì chưa có chỉ định.
