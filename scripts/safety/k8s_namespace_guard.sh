#!/usr/bin/env bash
# Set the current Kubernetes context namespace to core-router.

set -euo pipefail

NAMESPACE="${CORE_ROUTER_NAMESPACE:-core-router}"

info() { printf '[INFO] %s\n' "$*"; }
fail() { printf '[ERROR] %s\n' "$*" >&2; exit 1; }

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
    [[ -n "$kubectl_cmd" ]] || fail "No kubectl or microk8s command found."

    # shellcheck disable=SC2086
    $kubectl_cmd get namespace "$NAMESPACE" >/dev/null

    # This is intentionally the only mutating operation: it changes local kube context, not cluster resources.
    # shellcheck disable=SC2086
    $kubectl_cmd config set-context --current --namespace="$NAMESPACE" >/dev/null

    # shellcheck disable=SC2086
    info "Current context: $($kubectl_cmd config current-context)"
    # shellcheck disable=SC2086
    info "Current namespace: $($kubectl_cmd config view --minify --output 'jsonpath={..namespace}')"
}

main "$@"
