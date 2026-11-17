# Server configuration inspection

Read-only inspection was requested by the user to locate HIL configuration on
this server. No testbed was started, modified or exercised.

Observed host: `hanoi`. Docker, kubectl, ip and ss commands are installed.
Docker socket access was denied both normally and through the available
noninteractive sudo check (`sudo` requires a password). No credentials were
requested or read. Kubectl has no usable current configuration and targets
localhost:8080, where the connection was refused. Standard MicroK8s and
Kubernetes installation/config locations and the current user's `.kube`
directory were absent at inspection. The listeners inspected did not include
the repository controller's default 8765 endpoint or the expected switch Thrift
ports. This establishes the limits of the current account's observations; it
does not prove that no isolated VM/container testbed exists.

Repository source does contain configuration candidates:

- `infrastructure/sdn/topo_vietnam.py`: ten Vietnam nodes with switch names
  s1–s10 and MSD profiles 10/10/5/5/4/8/4/5/10/5; uses an OVS topology.
- `infrastructure/sdn/topo_p4.py`: switch manager, generated Thrift map,
  controller startup at port 8765 and local SIDs `fc00:<i>::1`.
- `infrastructure/sdn/p4_switch.py`: switch process/interface setup.
- `infrastructure/k8s/tekton/` and manifests: lifecycle/pipeline configuration.

These files are intended configuration, not evidence that their switch ports,
interfaces or Kubernetes nodes are currently instantiated. Realization and
teardown code must consume a validated explicit profile rather than assume the
old endpoint SID and fixed `s1`/port-1 route match the actual deployment.

Current user scope: finish code and tests; the user will run the experimental
phases. Live provisioning, training, research benchmarks and HIL execution are
outside this continuation's execution scope.
