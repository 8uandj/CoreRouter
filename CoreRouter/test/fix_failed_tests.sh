#!/bin/bash
# fix_failed_tests.sh — Fix 3 lỗi từ test_phases.sh (v2)
# Usage: sudo bash test/fix_failed_tests.sh

KC="sudo microk8s kubectl"
PASS=0; FAIL=0

ok()   { echo "  ✅ $1"; PASS=$((PASS+1)); }
fail() { echo "  ❌ $1"; FAIL=$((FAIL+1)); }

echo ""
echo "╔══════════════════════════════════════════════════════╗"
echo "║  Fix 3 test failures — 3S-COM Testbed               ║"
echo "╚══════════════════════════════════════════════════════╝"

# ──────────────────────────────────────────────────────────────
# FIX 1: TC-1.5 — Push images lên localhost:32000 registry service
# Dùng Docker daemon (reliable hơn microk8s ctr)
# ──────────────────────────────────────────────────────────────
echo ""
echo "▶ FIX 1/3: Push images lên localhost:32000 via Docker..."

# Đảm bảo Docker cho phép localhost:32000 (insecure registry)
DAEMON_JSON="/etc/docker/daemon.json"
if ! grep -q "localhost:32000" "$DAEMON_JSON" 2>/dev/null; then
    echo '{"insecure-registries": ["localhost:32000"]}' | sudo tee "$DAEMON_JSON" > /dev/null
    sudo systemctl reload docker || sudo systemctl restart docker
    sleep 2
    echo "  ✅ Added localhost:32000 to insecure-registries"
else
    echo "  ✅ localhost:32000 already in insecure-registries"
fi

push_image() {
    local src_img="$1"
    local dst_tag="$2"
    echo "  Pushing $dst_tag ..."
    docker tag "$src_img" "$dst_tag" 2>/dev/null || true
    if docker push "$dst_tag" 2>/dev/null; then
        ok "Pushed: $dst_tag"
    else
        fail "Push FAILED: $dst_tag — check: systemctl status docker"
    fi
}

push_image "alpine:latest"           "localhost:32000/alpine:latest"
push_image "python:3.11-alpine"      "localhost:32000/python:3.11-alpine"
push_image "nginx:1.27-alpine"       "localhost:32000/nginx:1.27-alpine"
push_image "quay.io/frrouting/frr:9.1.1" "localhost:32000/frr:9.1.1"
push_image "bitnami/kubectl:latest"  "localhost:32000/kubectl:1.30"

echo ""
echo "  Verify qua Registry API:"
declare -A VERIFY_MAP=(
    ["alpine:latest"]="alpine"
    ["python:3.11-alpine"]="python"
    ["nginx:1.27-alpine"]="nginx"
    ["frr:9.1.1"]="frr"
    ["kubectl:1.30"]="kubectl"
)
for img in "alpine:latest" "python:3.11-alpine" "nginx:1.27-alpine" "frr:9.1.1" "kubectl:1.30"; do
    repo="${VERIFY_MAP[$img]}"
    resp=$(curl -s --max-time 3 "http://localhost:32000/v2/${repo}/tags/list" 2>/dev/null || echo "")
    if echo "$resp" | grep -q '"tags"'; then
        ok "Registry has: localhost:32000/$img"
    else
        fail "Registry MISSING: localhost:32000/$img — resp: ${resp:0:60}"
    fi
done

# ──────────────────────────────────────────────────────────────
# FIX 2: TC-2.4 — Re-apply K8s resources để cập nhật Task images
# ──────────────────────────────────────────────────────────────
echo ""
echo "▶ FIX 2/3: Re-apply K8s resources lên cluster..."
if $KC apply -k infrastructure/k8s/ 2>&1 | tail -5; then
    # Kiểm tra task images sau khi apply
    sleep 2
    EXTERNAL=$($KC get tasks -n core-router -o yaml 2>/dev/null \
        | grep "image:" \
        | grep -v "localhost:32000" \
        | grep -v "#" || echo "")
    if [ -z "$EXTERNAL" ]; then
        ok "Tất cả Tekton Tasks đã dùng localhost:32000"
    else
        fail "Vẫn còn task dùng image ngoài: $EXTERNAL"
    fi
else
    fail "kubectl apply -k FAILED"
fi

# ──────────────────────────────────────────────────────────────
# FIX 3: TC-3.4 — Xoá MASQUERADE rule sót từ lần chạy cũ
# ──────────────────────────────────────────────────────────────
echo ""
echo "▶ FIX 3/3: Xoá MASQUERADE rule sót..."

# Xoá tất cả bản trùng (có thể có nhiều)
while sudo iptables -t nat -D POSTROUTING \
        -s 10.0.0.0/24 ! -d 10.0.0.0/24 -j MASQUERADE 2>/dev/null; do
    echo "  Deleted 1 MASQUERADE rule"
done

REMAIN=$(sudo iptables -t nat -L POSTROUTING -n 2>/dev/null \
    | grep "10.0.0.0/24.*MASQUERADE" || echo "")
if [ -z "$REMAIN" ]; then
    ok "MASQUERADE sạch — SFC Transparency: ON"
else
    fail "MASQUERADE vẫn còn: $REMAIN"
fi

# ──────────────────────────────────────────────────────────────
echo ""
echo "╔══════════════════════════════════════════════════════╗"
printf  "║  Kết quả: ✅ PASS=%d  ❌ FAIL=%d                       ║\n" $PASS $FAIL
echo "║  Chạy lại để verify:                                ║"
echo "║    sudo bash test/test_phases.sh all                ║"
echo "╚══════════════════════════════════════════════════════╝"
echo ""
exit $FAIL
