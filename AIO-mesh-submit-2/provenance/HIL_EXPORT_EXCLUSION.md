# Files omitted from the submission bundle

- `02_forwarding_overmsd/original/rebuild_20261117T123405Z/phase9_pre_restart/jobs.json`:
  cluster-wide Kubernetes Job dump that includes credentials of unrelated namespaces
  (`onap`, `fleet-local`, e.g. a Rancher `CATTLE_TOKEN`). It has been removed from the bundled export and its bundled `SHA256SUMS`.
  No HIL table or claim depends on this file.
