# 3S-COM Orchestrator (CoreRouter)

Dự án này tập trung vào việc Tối ưu hóa Kết hợp Phân bổ VNF và Di dời Chủ động (JO-VPPM - Joint Optimization of VNF Placement and Proactive Migration) dưới các ràng buộc phần cứng khắt khe của Data Plane (chẳng hạn như Maximum Segment Depth - MSD trong mạng SRv6). Hệ thống sử dụng Deep Graph Reinforcement Learning (DGRL - cụ thể là MaskablePPO + GAT) để ra quyết định điều phối trên mạng Backbone phân tán.

> **⚠️ CHÚ Ý DÀNH CHO CÁC AI AGENT:**
> 
> Bộ não kiến thức (Knowledge Base), quy tắc (Rules), các kịch bản hành động (Workflows), và thiết lập phân vai (Roles) của dự án này **KHÔNG NẰM Ở ĐÂY**. 
> 
> Bạn **BẮT BUỘC phải đọc** các file trong thư mục `.ai/` trước khi thực hiện bất kỳ thay đổi nào trong codebase để tránh phá vỡ kiến trúc học thuật của luận văn.
>
> Bắt đầu tại đây: `.ai/1_context/project.md`

## Cấu trúc thư mục (Tóm tắt)
- `.ai/`: 🧠 **[BẮT BUỘC ĐỌC]** - Não bộ kiến thức dành cho AI Agent.
- `src/`: Mã nguồn chính (RL Environment, GAT Policy, Orchestrator Logic, Infrastructure).
- `data/`: Dữ liệu topologies và traffic patterns.
- `results/`: Kết quả chạy mô phỏng và models đã train.
- `docs/`: Tài liệu học thuật (Thesis).