#!/usr/bin/env bash
# Read-only ONAP health snapshot for a server shared with CoreRouter.

set -euo pipefail

ONAP_ROOT="${ONAP_ROOT:-/home/dis}"

info() { printf '[INFO] %s\n' "$*"; }
warn() { printf '[WARN] %s\n' "$*" >&2; }

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

main() {
    local kubectl_cmd

    kubectl_cmd="$(select_kubectl)"

    section "ONAP filesystem"
    if [[ -d "$ONAP_ROOT" ]]; then
        info "ONAP root exists: $ONAP_ROOT"
    else
        warn "ONAP root not found: $ONAP_ROOT"
    fi

    section "Kubernetes ONAP/error snapshot"
    if [[ -n "$kubectl_cmd" ]]; then
        # shellcheck disable=SC2086
        $kubectl_cmd get ns || warn "Unable to list namespaces."
        printf '\n'
        # shellcheck disable=SC2086
        $kubectl_cmd get pods -A | awk '
            NR == 1 || tolower($0) ~ /onap|oom|crash|error|pending|failed/
        ' || warn "Unable to list pods."
    else
        warn "No kubectl or microk8s command found."
    fi

    section "Docker ONAP/error snapshot"
    if command -v docker >/dev/null 2>&1; then
        if ! docker ps -a --format 'table {{.Names}}\t{{.Status}}\t{{.Image}}' | \
            awk 'NR == 1 || tolower($0) ~ /onap|oom|crash|error|pending|failed|unhealthy|restarting|exited/'; then
            warn "Unable to list Docker containers."
        fi
    else
        warn "Docker command not found."
    fi

    section "Check complete"
    info "No changes were made by this script."
}

main "$@"
