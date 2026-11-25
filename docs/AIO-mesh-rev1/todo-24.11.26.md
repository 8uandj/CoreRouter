# **Đánh giá các nội dung bắt buộc hiệu chỉnh của AIO-Mesh**

Sau khi rà soát lại bản thảo 24 trang và đối chiếu với các nhận xét gốc của reviewers, tôi xác định **7 nhóm vấn đề cần xử lý trước khi nộp lại FGCS**. Tôi loại bỏ các đề xuất mang tính tùy chọn, bao gồm việc đổi thêm tiêu đề, tổ chức lại cấu trúc bài, mở rộng topology hoặc cải tiến phương pháp HARP.

## **I. P0 – Các lỗi và mâu thuẫn bắt buộc phải sửa**

### **P0.1. Figure 5 không nhất quán với Tables 9–10**

**Vị trí:** Section 6.9, trang 19–20.

Figure 5 vẫn sử dụng đồ thị scalability cũ của SAF-H, trong khi Tables 9–10 và caption Figure 5 đã cập nhật kết quả matched timing study mới.

| Metric tại 100 nodes             | Figure 5 hiện tại (xấp xỉ) | Table 9   |
| -------------------------------- | -------------------------- | --------- |
| SAF-H decision P95               | 83.6 ms                    | 11.103 ms |
| SAF-H candidate construction P95 | 70.2 ms                    | 3.435 ms  |
| HARP decision P95                | Không có                   | 44.273 ms |

Đây là mâu thuẫn trực tiếp giữa hình, bảng và phần diễn giải, ảnh hưởng đến việc đáp ứng Reviewer 4.2 và Reviewer 5.5.&#x20;

AIO-Mesh.rev1n(3).pdf

AIO-Mesh.rev1n(3).pdf



**Yêu cầu sửa:**

- Dựng lại panel bên phải Figure 5 từ đúng kết quả Table 9.
- Thể hiện cả HARP và SAF-H trên các topology 25, 50 và 100 nodes.
- Đồng bộ caption, Section 5.6 và Section 6.9.
- Sửa nhận xét về shared-host scheduling effects tại Section 6.10 để phân biệt với phép đo tuần tự mới.

Không cần chạy lại thực nghiệm cho vấn đề này.

### **P0.2. Table 6 chưa giải trình đầy đủ kết quả HIL**

**Vị trí:** Section 6.7, trang 15–16.

Table 6 hiện chưa phân loại đầy đủ 398 offered requests.

| Outcome                      | Số requests |
| ---------------------------- | ----------- |
| Admitted                     | 69          |
| Rejected: depth mismatch     | 231         |
| Rejected: exceeds switch MSD | 6           |
| **Chưa được giải trình**     | **92**      |
| Tổng                         | 398         |

Ngoài ra, trong 69 admissions có 57 migrations, nhưng phần mô tả experimental protocol nói campaign dừng sau khi đạt 30 net new VNFs. Hai thông tin này cần được giải thích bằng lifecycle accounting cụ thể.&#x20;

AIO-Mesh.rev1n(3).pdf

AIO-Mesh.rev1n(3).pdf



**Yêu cầu sửa:**

- Truy xuất log để phân loại chính xác 92 requests còn lại.
- Bổ sung các terminal outcomes còn thiếu vào Table 6.
- Xác nhận số VNF ban đầu, số deployment mới, số migration, số VNF cuối cùng và điều kiện dừng campaign.
- Phân biệt rejection do depth mismatch với rejection do actual MSD overflow.

Không tự động gán 92 requests còn thiếu cho `NO_SAFE_ACTION` nếu log không chứng minh điều đó.

**Reviewers liên quan:** R2.2, R5.1, R5.5.

### **P0.3. Figure 1 và Figure 2 chưa thống nhất với cơ chế masking và admission**

**Vị trí:** Figure 1, trang 8; Figure 2, trang 15.

Figure 1 vẫn đặt *Hardware-Safe Action Masking* sau *Candidate Orchestration Action*. Figure 2 tiếp tục mô tả Smart Admission bằng cụm *mask unsafe actions*.

Điều này không phù hợp với Eqs. (19)–(21), theo đó policy-side masking diễn ra trước action selection, còn runtime admission kiểm tra độc lập proposal đã được chọn.

Quy trình cần thể hiện thống nhất trong cả hai hình

Graph Encoder & Actor Logits

Policy-Side Action Masking

Candidate Action Selection

Independent Runtime Validation & Reservation

Admitted

Lifecycle actuation

Rejected

NO_SAFE_ACTION

Ngoài ra, Figure 1 vẫn dùng *Adaptive SLA and Migration Penalty*, trong khi Eq. (24) sử dụng action-switching penalty, không phải chi phí migration thực tế.

**Yêu cầu sửa:** Giữ nguyên thiết kế hai hình, chỉ hiệu chỉnh các khối, nhãn và mũi tên liên quan. Đổi *Migration Penalty* thành *Action-Switching Penalty*.&#x20;

AIO-Mesh.rev1n(3).pdf

AIO-Mesh.rev1n(3).pdf



**Reviewers liên quan:** R2.1, R2.2, R2.5, R5.4.

### **P0.4. Mô hình masked policy chưa hoàn chỉnh đối với empty mask**

**Vị trí:** Section 5.3, Eq. (21); Section 5.5 và Algorithm 2.

Eq. (21) hiện định nghĩa:

\\[ \pi\_\theta^M(a\mid s_t)= \frac{\exp(\widetilde z_a)} {\sum\_{b\in\mathcal A}\exp(\widetilde z_b)}. \\]

Nếu tất cả actions đều bị mask, mẫu số bằng 0 và phân phối xác suất không được xác định.

Trong khi đó, Section 5.5 xác nhận simulator cho phép unmasked proposal khi mask rỗng. Algorithm 2 chưa thể hiện tường minh nhánh xử lý này.&#x20;

AIO-Mesh.rev1n(3).pdf

AIO-Mesh.rev1n(3).pdf



**Yêu cầu sửa:**

- Giới hạn Eq. (21) cho trường hợp tập feasible actions khác rỗng.
- Bổ sung nhánh empty-mask handling vào Algorithm 2 theo đúng implementation.
- Phân biệt cách xử lý empty mask trong training, simulator evaluation và live runtime.
- Sửa câu *“The flat-action main and ablation policies optimize this policy using PPO”* vì NoMask và SoftMSD không sử dụng masked distribution như Full.
- Làm rõ bandwidth predicate thuộc simulator mask, simulator admission hay cả hai; bảo đảm nhất quán giữa Eq. (17), Eq. (18) và implementation.

Đoạn LaTeX tối thiểu cần bổ sung sau Eq. (21):

```
\newrev{The masked distribution in Eq.~(21) is defined only when $\mathcal{F}_{\mathrm{loc}}(s_t)\neq\emptyset$. Empty-mask states are handled separately through the fallback mechanism described in Section~5.5. Regardless of the proposal-generation mechanism, independent runtime admission retains the authority to reject infeasible actions before actuation.}
```

**Reviewers liên quan:** R2.2, R2.4, R5.4.

### **P0.5. Requested SID depth và materialized SID depth chưa được mô hình hóa nhất quán**

**Vị trí:** Eqs. (1), (5), (18); Sections 4.5 và 6.7.

Đây là vấn đề quan trọng vì MSD là đóng góp khoa học trung tâm của bài.

Section 4.5 yêu cầu requested SID depth phải bằng materialized SID-list depth, nhưng Eq. (1) chưa định nghĩa tường minh requested depth trong request model.

Hiện có ba đại lượng khác nhau:

| Đại lượng                | Ý nghĩa                                                     |
| ------------------------ | ----------------------------------------------------------- |
| \\(d_q^{\mathrm{msd}}\\) | Requested SID depth                                         |
| \\(h\_{q,v}(a_t)\\)      | SID depth thực tế được xử lý tại forwarding profile \\(v\\) |
| \\(m_v^{\mathrm{msd}}\\) | MSD limit của forwarding profile \\(v\\)                    |

Cần phân biệt hai điều kiện:

\\[ d_q^{\mathrm{msd}}=|S_q(a_t)| \\]

là depth-consistency condition, còn

\\[ h\_{q,v}(a_t)\leq m_v^{\mathrm{msd}} \\]

là hardware-feasibility condition.

Vi phạm điều kiện thứ nhất không nhất thiết dẫn đến vi phạm điều kiện thứ hai. Điều này đặc biệt quan trọng khi 231/398 requests trong Table 6 bị từ chối vì depth mismatch.

**Yêu cầu sửa:**

- Bổ sung requested SID depth vào Eq. (1) hoặc định nghĩa tường minh đây là một thuộc tính của request.
- Giải thích vì sao implementation sử dụng exact-depth matching thay vì maximum-depth constraint.
- Phân biệt hai predicates trong Section 4.5.
- Thống nhất cách gọi rejection categories trong Table 6 và Section 6.7.
- Không sử dụng tỷ lệ depth-mismatch rejection làm bằng chứng trực tiếp cho tỷ lệ hardware MSD overflow.



AIO-Mesh.rev1n(3).pdf

AIO-Mesh.rev1n(3).pdf



**Reviewers liên quan:** R2.5, R3.1, R5.1, R5.2.

## **II. P1 – Các yêu cầu reviewers chưa được đáp ứng đầy đủ**

### **P1.1. Hoàn thiện trả lời Reviewer 2.5 về pair-to-chain realization và cached paths**

Reviewer 2.5 đặt vấn đề trực tiếp về cách một routing anchor xác định placement và routing cho toàn bộ chuỗi VNF, cũng như ảnh hưởng của cached path table đến việc xác định feasible actions.

Bản hiện tại đã giới hạn đúng phạm vi pair-level, nhưng vẫn chưa trả lời đầy đủ cơ chế hiện thực hóa.

**Yêu cầu sửa tại Sections 3.2–3.3 và 4.5–4.6:**

| Nội dung             | Yêu cầu hoàn thiện                                                         |
| -------------------- | -------------------------------------------------------------------------- |
| Placement node       | Giải thích chính xác vai trò trong single-VNF realization                  |
| Routing anchor       | Giải thích cách anchor được sử dụng khi xây dựng SID list                  |
| Path compilation     | Mô tả cách xác định đường đi và thứ tự SIDs                                |
| MSD validation       | Xác định profile nào được kiểm tra và thời điểm kiểm tra                   |
| Cached paths         | Xác nhận pipeline nào còn sử dụng cache, nếu có                            |
| Full-chain soundness | Giữ Eq. (8) là điều kiện cần đạt, không phải thuộc tính đã được chứng minh |

Nếu current implementation không còn sử dụng cached path table, cần nói rõ điều đó để giải quyết trực tiếp nhận xét của reviewer, thay vì tiến hành cache sensitivity experiment không còn phù hợp.

Đồng thời, Section 3.2 trang 5 vẫn mô tả testbed chủ yếu liên quan control-plane requests và baseline readiness, trong khi Section 6.7 đã có single-VNF deployment và packet-forwarding campaigns. Cần đồng bộ câu này.

**Không bắt buộc mở rộng thành một thuật toán full-chain mới.** Tuy nhiên, nếu không bổ sung multi-VNF validation thì phải thừa nhận yêu cầu về full-chain realization chỉ được đáp ứng một phần.

### **P1.2. Hoàn thiện Reviewer 5.5 về validation overhead và long-running stability**

Reviewer 5.5 yêu cầu đánh giá inference latency và safety-validation overhead khi tăng số nodes, services và concurrent service chains; đồng thời yêu cầu bằng chứng ổn định trong thời gian dài.

Bản hiện tại vẫn còn hai khoảng trống.

**A. Safety-validation overhead**

Table 9 báo cáo mask construction, inference/selection và tổng decision latency. Tuy nhiên, policy-side masking không đồng nghĩa với independent runtime admission.

Cần kiểm tra timing instrumentation và bổ sung kết quả đo riêng của runtime admission/validation nếu đã có log.

Nếu chưa có, tôi đề nghị thực hiện một phép đo nhỏ sử dụng chính benchmark hiện tại:

| Thông số             | Cấu hình                                                                                     |
| -------------------- | -------------------------------------------------------------------------------------------- |
| Topology sizes       | 25, 50, 100 nodes                                                                            |
| Policies             | HARP và SAF-H                                                                                |
| Measurements         | Inference/selection P95, mask construction P95, admission-validation P95, total decision P95 |
| Background occupancy | Sử dụng các mức đã thực nghiệm: 0, 25, 50, 100 background chains                             |

Không cần huấn luyện lại models. Mục tiêu chỉ là bổ sung đúng thành phần overhead reviewer yêu cầu.

**Kết quả triển khai 25/11/2026:** crossed matrix đã hoàn tất đủ 240/240 ô, 20 seed × 1.000 bước cho mỗi cặp topology/occupancy, tổng cộng 480 policy rows. Tất cả 12 cells có đủ seed, trace hash của HARP/SAF-H khớp và không có protected admitted hard violation. Ở 100 nodes, total-decision P95 mean theo occupancy là 106.67–118.45 ms (HARP) và 251.53–257.11 ms (SAF-H); chi tiết đủ 12 cell tại Supplementary S29 và artifacts trong `results/rev1/p1_2_simulator/crossed_matrix_1000steps_fixed/`. Các con số là simulator với background-chain profile cố định, không phải live Kubernetes load.

**B. Long-running stability**

Phép thử 12 giờ không thực hiện deployment hoặc forwarding. Hai phép thử ba giờ trước đó có packet probes nhưng chỉ kiểm tra các VNF đã được steering từ trước; 209 requests mới được admitted không được deploy hoặc steer. Đã bổ sung một campaign riêng để đo lặp lifecycle request-to-actuation dưới điều kiện có kiểm soát.

Campaign exact-old kéo dài ba giờ đã hoàn tất trên testbed live: 18 lần thay vVOC theo make-before-break ở chu kỳ khoảng 10 phút; cả 18 lần đạt readiness, xác nhận steering, xóa VNF cũ, đối soát inventory/lock và kiểm tra flow. Tổng 4,952/4,952 packet nhận được; gap nhận lớn nhất mỗi cycle 339.8 ms; không có MSD counter increment. Đây là bằng chứng repeated lifecycle cho một service và một profile, không chứng minh ordered multi-VNF traversal, zero downtime tổng quát, nhiều service hay multi-day stability. Xem `results/hil/p1_2_lifecycle_20261124/three_hour_retry/` và Supplementary Table S28.

AIO-Mesh.rev1n(3).pdf

AIO-Mesh.rev1n(3).pdf



Hai phép thử admission/probe này tự chúng không chứng minh stability của admission-to-actuation. Campaign exact-old bổ sung bằng chứng lifecycle lặp trong ba giờ, nhưng chỉ với một service/profile và cadence cố định; vì vậy phản hồi reviewer cần mô tả đây là cải thiện có giới hạn, không tuyên bố đã giải quyết toàn bộ yêu cầu long-running hoặc production.

**Cập nhật triển khai 25/11/2026:** Live admission-only overhead trên testbed 10 node (30 selection-only requests, concurrency 1/2/4, không reset) và campaign repeated exact-old lifecycle ba giờ đã hoàn tất; lần lượt xem Supplementary S30 và S28. Crossed simulator matrix đã hoàn tất đủ 240/240 ô và được tích hợp ở Supplementary S29. Bằng chứng P1.2 theo kế hoạch đã đủ và được đồng bộ vào main text, supplement, response và ledger. Giới hạn còn lại được nêu rõ: simulator occupancy là profile mô phỏng cố định; live admission latency chỉ được đo trên profile 10 node; lifecycle 3 giờ chỉ cover vVOC trên một profile, không chứng minh production/multi-day/ordered full-chain forwarding. Cần xác nhận compile và số trang trên Overleaf trước khi chốt bundle nộp.

## **III. Các hiệu chỉnh thống kê và trình bày bắt buộc khi chốt bản thảo**

Các bảng hiện tại không cho thấy mâu thuẫn số học nghiêm trọng ngoài vấn đề HIL đã nêu. Tôi chỉ yêu cầu những điều chỉnh trực tiếp phục vụ việc kiểm tra kết quả:

| Vị trí        | Hiệu chỉnh cần thiết                                                                  |
| ------------- | ------------------------------------------------------------------------------------- |
| Table 3       | Ghi rõ bootstrap CI chưa điều chỉnh multiplicity, trong khi p-values đã Holm-adjusted |
| Table 4       | Ghi rõ P95 là Mean±SD của seed-level P95                                              |
| Table 5       | Xác định tường minh mẫu số của proposed và admitted hard-violation rates              |
| Section 6.1   | Ghi rõ phương pháp Wilcoxon và quy tắc xử lý ties/zeros cho từng nhóm kiểm định       |
| Supplementary | Kiểm tra đầy đủ S1–S25 và khả năng tái lập số liệu                                    |
| Section 4.4   | Viết đầy đủ Hardware-in-the-Loop (HIL) tại lần xuất hiện đầu tiên, theo R4.1          |

Không có căn cứ để thay đổi các mean, SD, CI hoặc p-values đang công bố nếu dữ liệu gốc xác nhận chúng.

## **IV. Danh sách công việc cuối cùng giao sinh viên**

### **Checklist nghiệm thu revision**

0/9 hoàn thành

**P0.1.** Dựng lại Figure 5 từ Table 9; đồng bộ timing discussion

R4.2, R5.5

**P0.2.** Giải trình 92 requests và lifecycle accounting của Table 6

R2.2, R5.1, R5.5

**P0.3.** Sửa masking/admission và penalty labels trong Figures 1–2

R2.1, R2.2, R2.5, R5.4

**P0.4.** Hoàn thiện empty-mask semantics, Eq. (21), Algorithm 2 và bandwidth predicate

R2.2, R2.4, R5.4

**P0.5.** Chuẩn hóa requested depth, materialized depth và MSD contract

R2.5, R3.1, R5.1–5.2

**P1.1.** Hoàn thiện pair realization và giải thích cached paths

R2.5

**P1.2.** Đã hoàn tất các phép đo đã định và đồng bộ giới hạn vào bản thảo; còn chờ Overleaf compile/đánh số trang trước khi khóa bundle.

R5.5

**P2.1.** Chuẩn hóa mô tả thống kê, abbreviations và supplementary

R2.3, R4.1

**P2.2.** Đồng bộ Responses to Reviewers với bản thảo cuối cùng

Editor và reviewers

&#x20;Sao chép checklist

## **V. Chỉ đạo hiệu chỉnh bản thảo cuối cùng**

Tôi đề nghị áp dụng nguyên tắc **minimal, reviewer-driven revision**:

- Giữ tối đa text từ bản nộp đầu tiên nếu nội dung vẫn chính xác.
- Chỉ hiệu chỉnh những đoạn liên quan trực tiếp đến các công việc nêu trên.
- Giữ nguyên toàn bộ kết quả thực nghiệm đã được xác minh.
- Sử dụng `\newrev{...}` màu xanh cho những nội dung sửa tiếp.
- Trong bản giải trình, giữ nguyên từng nhận xét gốc của reviewers, trả lời trực tiếp và dẫn chiếu đúng vị trí hiệu chỉnh.

**Kết luận:** Tôi đề nghị khóa phạm vi revision tại danh sách công việc trên, không tiếp tục phát sinh các yêu cầu cải tiến ngoài phạm vi phản biện. Sau khi giải quyết năm mục P0, hoàn thiện hai mục P1 và đồng bộ bản giải trình, có thể chốt bản nộp lại FGCS nếu các kiểm tra từ log và mã nguồn đều đạt. Không cần thêm một vòng viết lại toàn bộ bản thảo.
