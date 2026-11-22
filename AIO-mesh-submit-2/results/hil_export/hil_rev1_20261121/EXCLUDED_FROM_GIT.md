# Files kept on the testbed host but not committed

- `02_forwarding_overmsd/original/rebuild_20261117T123405Z/phase9_pre_restart/jobs.json`:
  cluster-wide Kubernetes Job dump that includes credentials of unrelated namespaces
  (`onap`, `fleet-local`, e.g. a Rancher `CATTLE_TOKEN`). It is listed in `SHA256SUMS`, so
  `sha256sum -c SHA256SUMS` reports it missing in a git clone; use `--ignore-missing`.
  No HIL table or claim depends on this file.
