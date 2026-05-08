# Định dạng Đầu ra (Output Style cho AI Agent)

Hỡi AI Agent, khi trả lời các câu hỏi hoặc sinh code cho dự án này, bạn BẮT BUỘC phải tuân theo các quy tắc sau:

1. **Ngắn gọn & Trực tiếp (Terse):** Không nói "Vâng", "Dạ", "Tôi hiểu rồi", "Chắc chắn rồi". Đi thẳng vào vấn đề hoặc đưa ra code luôn.
2. **Code Snippets:**
   - Cung cấp code có thể chạy được, tránh viết những đoạn code giả (pseudo-code) chung chung.
   - Luôn kèm theo comments giải thích TẠI SAO lại làm vậy (đặc biệt là liên quan đến các giới hạn phần cứng, MSD, GAT Matrix).
3. **Không giải thích thừa:** Nếu tôi yêu cầu "fix bug ở dòng X", chỉ đưa ra dòng X đã sửa. Đừng giải thích nguyên lý hoạt động của Python trừ khi tôi hỏi "Tại sao?".
4. **Báo cáo Lỗi Cứng Rắn:** Nếu code của tôi vi phạm luật vật lý của dự án (VD: tạo 1 mảng 15 SIDs trong khi MSD của node chỉ có 10), hãy TỪ CHỐI THỰC THI lệnh đó và báo cáo thẳng: "Lỗi: Vi phạm ràng buộc cứng MSD (15 > 10)".
5. **Định dạng Markdown:** Luôn bọc code bằng markdown với syntax highlighting phù hợp (`python`, `bash`, `p4`). Dùng gạch đầu dòng để liệt kê các thay đổi bạn vừa thực hiện.
