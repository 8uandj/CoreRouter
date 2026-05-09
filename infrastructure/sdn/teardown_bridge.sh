#!/bin/bash
# Teardown: don veth pairs va routes khi Mininet dung

KIND_CONTAINER="nfv-mini-control-plane"

echo "1. Xoa veth pairs..."
ip link delete veth-h1-kind   2>/dev/null || true
ip link delete veth-vnf1-kind 2>/dev/null || true
ip link delete veth-vnf2-kind 2>/dev/null || true

echo "2. Xoa route trong Kind container..."
docker exec $KIND_CONTAINER ip route del 10.0.0.0/24 2>/dev/null || true

echo "Hoan tat."
