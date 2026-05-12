#!/usr/bin/env bash
# Read-only preflight checks before running CoreRouter on a server shared with ONAP.

set -euo pipefail

CORE_ROUTER_ROOT="${CORE_ROUTER_ROOT:-/home/CoreRouter}"
ONAP_ROOT="${ONAP_ROOT:-/home/dis}"
NAMESPACE="${CORE_ROUTER_NAMESPACE:-core-router}"
MIN_FREE_GB="${CORE_ROUTER_MIN_FREE_GB:-10}"

info() { printf '[INFO] %s\n' "$*"; }
warn() { printf '[WARN] %s\n' "$*" >&2; }
fail() { printf '[ERROR] %s\n' "$*" >&2; exit 1; }

section() {
    printf '\n== %s ==\n' "$*"
}

select_kubectl() {
    if command -v microk8s >/dev/null 2>&1; then
        printf 'microk8s kubectl'
    elif command -v kubectl >/dev/null 2>&1; then
        printf 'kubectl'
    else
        printf ''
    fi
}

run_optional() {
    local label="$1"
    shift

    section "$label"
    if ! "$@"; then
        warn "$label failed or is unavailable; continuing because this is a read-only preflight."
    fi
}

require_repo_root() {
    local current_root

    current_root="$(pwd -P)"
    [[ "$current_root" == "$CORE_ROUTER_ROOT" ]] || \
        fail "Run this from $CORE_ROUTER_ROOT (current: $current_root). Set CORE_ROUTER_ROOT only for non-production testing."

    [[ -f "$CORE_ROUTER_ROOT/run_backend_docker.sh" ]] || \
        fail "CoreRouter marker missing: $CORE_ROUTER_ROOT/run_backend_docker.sh"
    [[ -d "$CORE_ROUTER_ROOT/infrastructure" ]] || \
        fail "CoreRouter marker missing: $CORE_ROUTER_ROOT/infrastructure"
}

check_disk() {
    local available_gb

    df -h "$CORE_ROUTER_ROOT" /
    available_gb="$(df -BG "$CORE_ROUTER_ROOT" | awk 'NR==2 {gsub(/G/, "", $4); print $4}')"
    if [[ -n "$available_gb" && "$available_gb" -lt "$MIN_FREE_GB" ]]; then
        warn "Free disk under ${MIN_FREE_GB}GB at $CORE_ROUTER_ROOT: ${available_gb}GB. Avoid builds/pulls until disk is cleaned deliberately."
    fi
}

check_k8s() {
    local kubectl_cmd="$1"

    if [[ -z "$kubectl_cmd" ]]; then
        warn "No kubectl or microk8s command found."
        return 0
    fi

    # shellcheck disable=SC2086
    $kubectl_cmd get nodes -o wide
    # shellcheck disable=SC2086
    $kubectl_cmd get ns
    # shellcheck disable=SC2086
    $kubectl_cmd get pods -A | awk -v ns="$NAMESPACE" '
        NR == 1 || $1 == ns || tolower($0) ~ /onap|oom|crash|error|pending/
    '
}

check_docker() {
    if ! command -v docker >/dev/null 2>&1; then
        warn "Docker command not found."
        return 0
    fi

    docker ps -a --format 'table {{.Names}}\t{{.Status}}\t{{.Image}}' | \
        awk 'NR == 1 || tolower($0) ~ /onap|core-router|3s-com/'
}

warn_onap_failures() {
    local kubectl_cmd="$1"
    local found=0

    if [[ -n "$kubectl_cmd" ]]; then
        # shellcheck disable=SC2086
        if $kubectl_cmd get pods -A 2>/dev/null | awk 'tolower($0) ~ /onap/ && tolower($0) ~ /oom|crash|error|pending|failed/ {found=1} END {exit !found}'; then
            warn "ONAP-related Kubernetes pods appear unhealthy before CoreRouter starts."
            found=1
        fi
    fi

    if command -v docker >/dev/null 2>&1; then
        if docker ps -a --format '{{.Names}} {{.Status}} {{.Image}}' 2>/dev/null | \
            awk 'tolower($0) ~ /onap/ && tolower($0) ~ /exited|dead|restarting|unhealthy/ {found=1} END {exit !found}'; then
            warn "ONAP-related Docker containers appear unhealthy before CoreRouter starts."
            found=1
        fi
    fi

    if [[ "$found" -eq 0 ]]; then
        info "No obvious ONAP failures detected by read-only checks."
    fi
}

main() {
    local kubectl_cmd

    require_repo_root
    kubectl_cmd="$(select_kubectl)"

    section "CoreRouter safety preflight"
    info "CoreRouter root: $CORE_ROUTER_ROOT"
    info "ONAP root: $ONAP_ROOT"
    info "CoreRouter namespace: $NAMESPACE"

    [[ -d "$ONAP_ROOT" ]] || warn "ONAP root does not exist or is not mounted: $ONAP_ROOT"

    run_optional "Disk" check_disk
    run_optional "Memory" free -h
    run_optional "Docker containers matching ONAP/CoreRouter" check_docker
    run_optional "Kubernetes nodes/namespaces/pods" check_k8s "$kubectl_cmd"
    run_optional "ONAP failure scan" warn_onap_failures "$kubectl_cmd"

    section "Preflight complete"
    info "No changes were made by this script."
}

main "$@"
