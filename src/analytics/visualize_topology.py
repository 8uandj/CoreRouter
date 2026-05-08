import matplotlib.pyplot as plt
import networkx as nx
import numpy as np
import os
import sys

# Thêm project root vào path để import được module
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '../..')))

from src.orchestration.jo_vdpr.topology import DC_NODES, LATENCY_MATRIX, NAMES, LATS, LONS, ROLES, MSD_LIMITS

def visualize_backbone():
    # Giả lập dữ liệu CPU từ Table 4.1 của luận văn
    CPU_CAPS = {
        "Hanoi": 200, "HaiPhong": 150, "NinhBinh": 80, "Vinh": 80,
        "Hue": 60, "DaNang": 150, "QuyNhon": 60, "NhaTrang": 80,
        "HoChiMinh": 200, "CanTho": 80
    }

    G = nx.Graph()
    
    # Thiết lập màu sắc và kích thước cho các node
    node_colors = []
    node_sizes = []
    pos = {}
    
    # ── Node Definitions ──────────────────────────────────────────
    for i, (name, lat, lon, role, msd, proc) in enumerate(DC_NODES):
        G.add_node(name, cpu=CPU_CAPS[name], msd=msd, role=role)
        pos[name] = (lon, lat)
        
        if role == "core":
            node_colors.append('#ff4757') # Vibrant Red/Coral for Core
            node_sizes.append(1800)
        else:
            node_colors.append('#2f3542') # Sleek Dark Blue/Black for Edge
            node_sizes.append(900)

    # ── Backbone Edge Logic (Realistic S-Chain) ───────────────────
    # Thay vì vẽ tất cả, chúng ta chỉ vẽ "xương sống" nối từ Bắc vào Nam
    backbone_links = [
        ("Hanoi", "HaiPhong"), ("Hanoi", "NinhBinh"),
        ("NinhBinh", "Vinh"), ("Vinh", "Hue"),
        ("Hue", "DaNang"), ("DaNang", "QuyNhon"),
        ("QuyNhon", "NhaTrang"), ("NhaTrang", "HoChiMinh"),
        ("HoChiMinh", "CanTho"),
        # Core to Core High-speed connections
        ("Hanoi", "DaNang"), ("DaNang", "HoChiMinh")
    ]
    for u, v in backbone_links:
        G.add_edge(u, v, weight=LATENCY_MATRIX[NAMES.index(u)][NAMES.index(v)])

    # ── Rendering ──────────────────────────────────────────────────
    plt.figure(figsize=(12, 20))
    plt.gca().set_facecolor('#f8fafc') # Light slate background
    
    # Draw Backbone Edges
    nx.draw_networkx_edges(G, pos, width=3, edge_color='#94a3b8', alpha=0.4, style='--')
    
    # Draw Nodes
    nx.draw_networkx_nodes(G, pos, node_size=node_sizes, node_color=node_colors, 
                           edgecolors='white', linewidths=3, alpha=1.0)

    # ── Label Logic (Offset to avoid overlapping) ────────────────
    for name, (lon, lat) in pos.items():
        role = G.nodes[name]['role']
        cpu = CPU_CAPS[name]
        msd = int(MSD_LIMITS[NAMES.index(name)])
        
        # Tên Thành phố (Dưới node)
        plt.text(lon, lat - 0.22, name, fontsize=14, fontweight='black', 
                 color='#2d3436', horizontalalignment='center', verticalalignment='top')
        
        # Thông số tài nguyên (Bên phải node)
        info_str = f"CPU: {cpu}\nMSD: {msd}"
        bbox_color = '#fff' if role == 'core' else '#f1f2f6'
        plt.text(lon + 0.18, lat, info_str, fontsize=11, 
                 color='#636e72', fontweight='bold', verticalalignment='center',
                 bbox=dict(facecolor=bbox_color, alpha=0.85, edgecolor='#dfe6e9', boxstyle='round,pad=0.3'))

    # Title & Metadata
    plt.title("JO-VPPM: Vietnam Backbone Simulation Topology\n(Geographic Hierarchy S-Curve)", 
              fontsize=22, fontweight='black', pad=30, color='#2d3436')
    
    # Grid & Spacing
    plt.grid(True, linestyle=':', alpha=0.4, color='#b2bec3')
    plt.axis('on') # Show coordinates for geographic context
    plt.xlabel("Longitude (E)", fontsize=14, color='#636e72')
    plt.ylabel("Latitude (N)", fontsize=14, color='#636e72')

    # Legend
    core_proxy = plt.Line2D([0], [0], marker='o', color='w', label='Core Datacenter Hub',
                            markerfacecolor='#ff4757', markersize=15)
    edge_proxy = plt.Line2D([0], [0], marker='o', color='w', label='Edge Computing Node',
                            markerfacecolor='#2f3542', markersize=10)
    plt.legend(handles=[core_proxy, edge_proxy], loc='upper right', fontsize=12, frameon=True, shadow=True)

    # Cấu hình trục
    plt.title("10-Node Vietnam Backbone Simulation Topology\n(Geographical Distribution & Resource Hierarchy)", fontsize=14, fontweight='bold', pad=20)
    plt.xlabel("Longitude", fontsize=12)
    plt.ylabel("Latitude", fontsize=12)
    plt.grid(True, linestyle='--', alpha=0.3)
    
    # Legend
    core_patch = plt.Line2D([0], [0], marker='o', color='w', label='Core DC Hub (High MSD)', markerfacecolor='#ef4444', markersize=12)
    edge_patch = plt.Line2D([0], [0], marker='o', color='w', label='Edge DC Node (Low MSD)', markerfacecolor='#3b82f6', markersize=8)
    plt.legend(handles=[core_patch, edge_patch], loc='upper left', frameon=True, fontsize=10)

    # Lưu hình ảnh
    output_path = os.path.join(os.path.dirname(__file__), '../../results/figures/vietnam_backbone_topology.png')
    os.makedirs(os.path.dirname(output_path), exist_ok=True)
    plt.savefig(output_path, dpi=300, bbox_inches='tight')
    plt.close()
    
    print(f"✅ Đã xuất ảnh topology tại: {output_path}")

if __name__ == "__main__":
    visualize_backbone()
