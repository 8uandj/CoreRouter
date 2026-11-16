import subprocess
import json
import shutil
from pathlib import Path

# FILE LƯU CẤU HÌNH TẠM THỜI
CONFIG_FILE = Path(".kaggle_config.json")
WORKSPACE   = Path("/home/hung8uandj/Study/CoreRouter")

def get_kaggle_cmd():
    paths = ["kaggle", str(Path.home() / ".local/bin/kaggle"), "/usr/local/bin/kaggle"]
    for p in paths:
        try:
            subprocess.run(f"{p} --version", shell=True, check=True, capture_output=True)
            return p
        except: continue
    return "python3 -m kaggle"

KAG_CMD = get_kaggle_cmd()

def load_config():
    if CONFIG_FILE.exists():
        with open(CONFIG_FILE, "r") as f:
            return json.load(f)
    return {"dataset": "chua-dat-ten", "kernel": "chua-dat-ten"}

def save_config(dataset, kernel):
    with open(CONFIG_FILE, "w") as f:
        json.dump({"dataset": dataset, "kernel": kernel}, f)
    print(f"✅ Đã lưu cấu hình:\n   Dataset: {dataset}\n   Kernel:  {kernel}")

def list_all():
    """Liệt kê toàn bộ tài nguyên trên Kaggle của bạn."""
    print("\n--- 📂 DANH SÁCH DATASETS CỦA BẠN ---")
    subprocess.run(f"{KAG_CMD} datasets list --mine", shell=True)
    
    print("\n--- 📓 DANH SÁCH NOTEBOOKS CỦA BẠN ---")
    subprocess.run(f"{KAG_CMD} kernels list --mine", shell=True)
    print("\n💡 Hãy copy chính xác tên (dạng username/slug) để dùng lệnh 'config'.")

def push_code():
    cfg = load_config()
    print(f"🚀 Đang đẩy code lên Dataset: {cfg['dataset']}...")
    zip_name = "jo_vppm_thesis_ready.zip"
    
    # Nén với các filter loại bỏ rác và file nhạy cảm
    # -x "*.env" loại bỏ file ẩn .env
    # -x "**/env/*" loại bỏ folder env (như venv)
    # Chúng ta vẫn giữ env.py vì nó không khớp pattern folder/
    exclude_patterns = [
        "**/venv/*", "**/env/*", "**/node_modules/*", 
        "**/.git/*", "**/*.pyc", "**/__pycache__/*",
        "**/.env", "results/*", "logs/*", "*.zip"
    ]
    exclude_str = " ".join(f'-x "{p}"' for p in exclude_patterns)
    
    cmd = f'zip -r {zip_name} src data requirements.txt {exclude_str}'
    subprocess.run(cmd, shell=True, cwd=WORKSPACE)
    
    # Push
    cmd = f'{KAG_CMD} datasets version -p {zip_name} -m "Auto-update code"'
    result = subprocess.run(cmd, shell=True, cwd=WORKSPACE)
    if result.returncode == 0: print("✅ Đã đẩy code thành công!")

def pull_results():
    cfg = load_config()
    print(f"📥 Đang tải kết quả từ Kernel: {cfg['kernel']}...")
    
    # Tải thẳng về thư mục gốc
    cmd = f'{KAG_CMD} kernels output {cfg["kernel"]} -p "{WORKSPACE}"'
    result = subprocess.run(cmd, shell=True)
    
    if result.returncode == 0:
        print(f"✅ Tải thành công! Đang kiểm tra cấu trúc...")
        
        # Nếu kết quả về dưới dạng file ZIP (Kaggle tự nén)
        kernel_slug = cfg["kernel"].split("/")[-1]
        potential_zip = WORKSPACE / f"{kernel_slug}.zip"
        
        if potential_zip.exists():
            print(f"📦 Giải nén {potential_zip.name}...")
            # Giải nén đè để khôi phục results/
            subprocess.run(f"unzip -o {potential_zip} -d {WORKSPACE}", shell=True)
            os.remove(potential_zip)
            
        print(f"✨ HOÀN THÀNH! Kết quả đã được cập nhật vào {WORKSPACE / 'results'}")
    else:
        print("❌ Lỗi: Không thể tải kết quả từ Kaggle.")

if __name__ == "__main__":
    import sys
    args = sys.argv
    if len(args) < 2:
        print("Cách dùng:")
        print("  python3 kaggle_manager.py list                    -> Xem danh sách")
        print("  python3 kaggle_manager.py config <data> <kernel>  -> Chọn mục tiêu")
        print("  python3 kaggle_manager.py push                    -> Đẩy code")
        print("  python3 kaggle_manager.py pull                    -> Lấy model")
    elif args[1] == "list":
        list_all()
    elif args[1] == "config" and len(args) == 4:
        save_config(args[2], args[3])
    elif args[1] == "push":
        push_code()
    elif args[1] == "pull":
        pull_results()
