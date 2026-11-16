"""
visualize_benchmark.py — Phân tích & Trực quan hóa Kết quả Thực nghiệm JO-VPPM v10

Đọc file text: v10_benchmark_results.txt
Lưu Data Visualization vào: results/figures/
"""

import os
import re
import matplotlib.pyplot as plt
import seaborn as sns
import pandas as pd
from typing import List, Dict

def parse_benchmark_results(filepath: str) -> pd.DataFrame:
    data = []
    current_topology = None
    
    with open(filepath, 'r', encoding='utf-8') as f:
        lines = f.readlines()
        
    for line in lines:
        # Bắt tên Topology
        if 'ĐÁNH GIÁ MẠNG LƯỚI:' in line:
            current_topology = line.split(':')[-1].replace('---', '').strip().lower()
            continue
            
        # Bỏ qua các dòng không phải Data Row
        if not current_topology or line.startswith('=') or line.startswith('-') or 'Algorithm' in line or 'INFO' in line:
            continue
            
        # Tìm data row (e.g., Optimal ILP     | uniform      |    100.0% |     0.00% |     3.73 ms)
        if '|' in line:
            parts = [p.strip() for p in line.split('|')]
            if len(parts) >= 5:
                algo = parts[0]
                scenario = parts[1]
                
                # Parse numeric values
                acc = float(parts[2].replace('%', '').strip())
                sla = float(parts[3].replace('%', '').strip())
                lat = float(parts[4].replace('ms', '').strip())
                
                data.append({
                    'Topology': current_topology.upper(),
                    'Algorithm': algo,
                    'Scenario': scenario.capitalize(),
                    'Acceptance Rate (%)': acc,
                    'SLA Violation (%)': sla,
                    'Average Latency (ms)': lat
                })
                
    return pd.DataFrame(data)

def generate_plots(df: pd.DataFrame, output_dir: str):
    os.makedirs(output_dir, exist_ok=True)
    sns.set_theme(style="whitegrid", context="talk")
    
    metrics = ['Acceptance Rate (%)', 'SLA Violation (%)', 'Average Latency (ms)']
    
    for metric in metrics:
        fig = plt.figure(figsize=(16, 8))
        
        # Nhóm theo Topology trên trục X, Tách bằng màu theo Algorithm
        # Bỏ Scenario riêng rẽ hoặc Trung bình qua tất cả Scenario
        ax = sns.barplot(
            data=df,
            x="Topology", 
            y=metric, 
            hue="Algorithm",
            errorbar=None, # Show mean across scenarios
            palette="Set2"
        )
        
        plt.title(f"Comparison of {metric} across Topologies (Averaged Scaled Traffic)", pad=20, fontsize=16, fontweight='bold')
        plt.xlabel("Network Topology", fontweight='bold')
        plt.ylabel(metric, fontweight='bold')
        
        # Thêm hiển thị Text lên trên cột
        for container in ax.containers:
            ax.bar_label(container, fmt='%.1f', padding=3, fontsize=10)
            
        plt.legend(title='Orchestration Method', bbox_to_anchor=(1.05, 1), loc='upper left')
        plt.tight_layout()
        
        # Lưu file tên theo metric
        safe_name = metric.lower().replace(' ', '_').replace('(%)', 'perc').replace('(ms)', 'ms').replace('__', '_')
        outfile = os.path.join(output_dir, f"v10_{safe_name}.png")
        plt.savefig(outfile, dpi=300)
        plt.close()
        
        # Trực quan nhóm theo kịch bản (Scenario) thay vì mạng (chỉ trên VIETNAM)
        df_vietnam = df[df['Topology'] == 'VIETNAM']
        if not df_vietnam.empty:
            fig2 = plt.figure(figsize=(10, 6))
            ax2 = sns.barplot(
                data=df_vietnam,
                x="Scenario",
                y=metric,
                hue="Algorithm",
                palette="viridis"
            )
            plt.title(f"{metric} in Vietnam Network by Traffic Scenario", pad=15, fontweight='bold')
            plt.ylabel(metric)
            plt.xlabel("Traffic Scenario")
            for container in ax2.containers:
                ax2.bar_label(container, fmt='%.1f', padding=3, fontsize=10)
                
            plt.tight_layout()
            outfile_scen = os.path.join(output_dir, f"v10_vietnam_{safe_name}_scenarios.png")
            plt.savefig(outfile_scen, dpi=300)
            plt.close()

if __name__ == "__main__":
    BASE_DIR = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    LOG_FILE = os.path.join(BASE_DIR, 'v10_benchmark_results.txt')
    OUTPUT_DIR = os.path.join(BASE_DIR, 'results', 'figures')
    
    if not os.path.exists(LOG_FILE):
        print(f"[LỖI] Không tìm thấy file {LOG_FILE}. Đảm bảo đã chạy Benchmark v10!")
        sys.exit(1)
        
    print(">>> Đang phân tích kết quả từ file log...")
    df = parse_benchmark_results(LOG_FILE)
    if df.empty:
        print("[LỖI] Không Parse được dòng Data nào. Định dạng Table thay đổi chăng?")
    else:
        print(f">>> Tìm thấy {len(df)} datapoints. Tiến hành kết xuất Biểu đồ...")
        generate_plots(df, OUTPUT_DIR)
        print(f"✅ Hoàn tất! Các file phân tích đồ hoạ đã được tạo tại: {OUTPUT_DIR}")
