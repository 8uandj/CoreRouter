# CoreRouter Safety Scripts

These scripts are for operating CoreRouter on a server shared with ONAP.

Default paths:

- CoreRouter: `/home/CoreRouter`
- ONAP: `/home/dis`
- Kubernetes namespace: `core-router`

Use `CORE_ROUTER_ROOT`, `ONAP_ROOT`, or `CORE_ROUTER_NAMESPACE` only for testing or if the production paths change deliberately.

## Commands

```bash
bash scripts/safety/preflight_core_router.sh
bash scripts/safety/check_onap_safety.sh
bash scripts/safety/k8s_namespace_guard.sh
bash scripts/safety/run_corerouter_safe.sh status
bash scripts/safety/run_corerouter_safe.sh backend-run
```

## Safety Rules

- Do not run broad destructive commands unless the owner explicitly approves the exact impact:
  - `kubectl delete -A`
  - `docker system prune -a`
  - `microk8s reset`
  - `kubeadm reset`
  - `fuser -k`
- Do not edit or remove files under `/home/dis` from CoreRouter scripts.
- Do not apply manifests to ONAP namespaces from CoreRouter workflows.
- Keep CoreRouter manifests scoped to the `core-router` namespace.
- Use taint `dedicated=core-router:NoSchedule` only on nodes dedicated to CoreRouter.
- Do not taint, drain, cordon, or reboot nodes that are serving ONAP without a separate ONAP maintenance plan.

## Notes

The checks are intentionally read-only except `k8s_namespace_guard.sh`, which only sets the local Kubernetes context namespace to `core-router`. It does not change cluster resources.
