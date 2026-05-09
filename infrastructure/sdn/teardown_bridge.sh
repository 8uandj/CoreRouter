#!/bin/bash
# teardown_bridge.sh — Dọn dẹp sau khi tắt Mininet
# Xóa: veth pairs, bridge ảo, và route Mininet
# Usage: sudo bash infrastructure/sdn/teardown_bridge.sh

set -e

echo "🧹 Teardown Mininet ↔ K8s bridge..."

echo "1. Xóa veth pairs..."
for veth in veth-h1-k8s veth-vnf1-k8s veth-vnf2-k8s; do
    ip link delete "$veth" 2>/dev/null && echo "   Deleted $veth" || true
done

echo "2. Xóa bridge br-k8s-mn (nếu có)..."
ip link delete br-k8s-mn 2>/dev/null && echo "   Deleted br-k8s-mn" || true

echo "3. Xóa route Mininet trên host..."
ip route del 10.0.0.0/24 2>/dev/null && echo "   Deleted route 10.0.0.0/24" || true

echo "4. Chạy mn -c để dọn OVS..."
mn -c 2>/dev/null || true

echo "✅ Teardown hoàn tất."
