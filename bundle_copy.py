import os

# Định nghĩa cấu trúc tầng của dự án CoreRouter 3S-COM
STRUCTURE = {
    "TẦNG I: ANALYTICS & AI": ["src/analytics"],
    "TẦNG II: ORCHESTRATION & CONTROL": ["src/orchestration", "3S_COM_PoC"],
    "TẦNG III: INFRASTRUCTURE (NFV & P4)": ["infrastructure"],
    "GIAO DIỆN QUẢN TRỊ": ["src/portal/backend/app"],
    "CẤU HÌNH HỆ THỐNG": ["kind.yaml", "README.md"]
}

# Các định dạng file quan trọng cho dự án
EXTENSIONS = ('.py', '.yaml', '.p4', '.json', '.md')
OUTPUT_FILE = "docs/3S_COM_FULL_CONTEXT.md"

def generate_context():
    if not os.path.exists("docs"): os.makedirs("docs")
    
    with open(OUTPUT_FILE, "w", encoding="utf-8") as out:
        out.write("# 3S-COM SYSTEM FULL CONTEXT\n")
        out.write("Tài liệu tổng hợp toàn bộ mã nguồn và cấu trúc hệ thống CoreRouter.\n\n")

        for layer, paths in STRUCTURE.items():
            out.write(f"\n## {layer}\n")
            for path in paths:
                if os.path.isfile(path):
                    process_file(path, out)
                else:
                    for root, _, files in os.walk(path):
                        if "node_modules" in root or "venv" in root or "__pycache__" in root:
                            continue
                        for file in files:
                            if file.endswith(EXTENSIONS):
                                process_file(os.path.join(root, file), out)
    print(f"✅ Đã tạo file ngữ cảnh tại: {OUTPUT_FILE}")

def process_file(file_path, out):
    try:
        with open(file_path, "r", encoding="utf-8") as f:
            content = f.read()
            out.write(f"\n### FILE: {file_path}\n")
            ext = file_path.split('.')[-1]
            out.write(f"```{ext}\n{content}\n```\n")
    except Exception as e:
        pass

if __name__ == "__main__":
    generate_context()