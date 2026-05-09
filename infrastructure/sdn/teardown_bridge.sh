#!/bin/bash
# teardown_bridge.sh — Dọn dẹp sau khi tắt Mininet
# Xóa: veth pairs, bridge ảo, return routes, và FORWARD rules
# Usage: sudo bash infrastructure/sdn/teardown_bridge.sh

set -e

echo "🧹 Teardown Mininet ↔ K8s bridge (Transparent Routing mode)..."

echo "1. Xóa veth pairs..."
for veth in veth-h1-k8s veth-vnf1-k8s veth-vnf2-k8s; do
    ip link delete "$veth" 2>/dev/null && echo "   Deleted $veth" || true
done

echo "2. Xóa bridge br-k8s-mn (nếu có — chỉ Calico mode)..."
ip link delete br-k8s-mn 2>/dev/null && echo "   Deleted br-k8s-mn" || true

echo "3. Xóa per-host return routes (Transparent Routing)..."
# Các host routes /32 do _setup_transparent_routing() tạo ra
for route in 10.0.0.1/32 10.0.0.11/32 10.0.0.12/32; do
    ip route del "$route" 2>/dev/null && echo "   Deleted route $route" || true
done
# Route /24 cũ (nếu còn)
ip route del 10.0.0.0/24 2>/dev/null && echo "   Deleted route 10.0.0.0/24" || true

echo "4. Xóa FORWARD rules cho bridge (nếu còn từ lần chạy trước)..."
# Chỉ xóa rule liên quan đến bridge — KHÔNG flush toàn bộ FORWARD chain
for bridge in br-k8s-mn cni0; do
    iptables -D FORWARD -i "$bridge" -j ACCEPT 2>/dev/null || true
    iptables -D FORWARD -o "$bridge" -j ACCEPT 2>/dev/null || true
done

echo "5. Chạy mn -c để dọn OVS state..."
mn -c 2>/dev/null || true

echo "✅ Teardown hoàn tất. Không còn MASQUERADE residue."
