# Isolated CoreRouter HIL Testbed Design

## Intent

Rebuild the CoreRouter physical-in-the-loop testbed on the existing server so
the remaining HIL experiments can exercise Kubernetes/Tekton lifecycle,
Mininet traffic, BMv2 P4 forwarding, the SDN controller, and the CoreRouter API.
The user selected a dedicated VM as the isolation boundary. Existing benchmark
and active-chain jobs must continue without being stopped or modified.

## Current system concept

The implemented simulator selects a `(placement_node, routing_node)` pair.
The runtime admission boundary checks the modeled CPU, RAM, and per-list MSD
constraints and rejects requests that do not pass. Kubernetes/Tekton owns VNF
deployment and migration; the SDN controller changes forwarding rules; Mininet
and BMv2 provide the traffic/data-plane environment. A passing admission or
controller HTTP response alone is not evidence that the admitted SID list was
forwarded by the switches.

The current audited contract is deliberately narrower than a complete SFC
realization. The admitted SID list is not yet correlated with the controller's
steering payload. Deployed-TTL de-steering and confirmed P4 rule deletion
readback are also still open requirements. Actuation must therefore remain
fail-closed until an explicit topology/profile mapping and correlated readback
exist. Testbed availability must not be used to imply those code contracts are
already satisfied.

## Goals

- Keep all testbed kernel, network, and container operations inside one guest.
- Avoid creating or changing host bridges, routes, and firewall rules. The only
  allowed host listener is a verified free, loopback-only VM access forward.
- Run a single-node Kubernetes cluster with the repository's Tekton resources,
  VNF templates, backend, and SDN controller.
- Run the ten-node Mininet topology with one BMv2 switch per topology node,
  using the compiled MSD profiles and explicit switch/port mapping.
- Give every guest service, container, network, disk, and log an owned
  `core-router-hil` identity and deterministic cleanup path.
- Apply bounded CPU, memory, disk, and process limits so the guest cannot
  consume resources without a configured ceiling.
- Capture request-correlated API, Tekton, Kubernetes, P4 rule/readback, packet,
  counter, and timing evidence in a dedicated experiment directory.

## Non-goals and anti-goals

- Do not modify or restart host Docker, containerd, Kubernetes, network
  bridges, routes, iptables, or services owned by other projects/users.
- Do not claim zero host scheduling/I/O impact while the VM shares this server;
  the resource caps bound its maximum contribution but cannot eliminate
  contention under host saturation.
- Do not bind testbed services to existing host ports or expose them to the
  external network by default. Any access is through a separately verified,
  localhost-only forwarded port or VM SSH session.
- Do not claim ASIC behavior from BMv2 results.
- Do not enable unsafe steering, silently select a fallback path, release a
  deployed reservation without confirmed teardown, or present local admission
  success as packet-forwarding proof.
- Do not start long research runs during installation or smoke validation.

## Approaches considered

1. **Dedicated VM on this server — selected.** A guest kernel contains the
   Kubernetes cluster, Docker daemon, Mininet namespaces, BMv2 switches, API,
   and SDN controller. Guest-local host networking and privileged BMv2
   containers cannot change the server's host routes or bridges. Hard guest
   quotas limit resource use.
2. **Host namespaces/cgroups.** This consumes fewer resources but shares the
   host kernel and requires privileged network operations. The current Mininet
   scripts also issue host route/iptables changes and use fixed container
   names, so this path carries more collision risk and requires broader code
   surgery.
3. **Direct host deployment.** Rejected because it conflicts with the user's
   isolation requirement and the inspected scripts can mutate shared host
   networking.

## Selected architecture

```text
Server host
  bounded libvirt guest: core-router-hil
    guest-local Kubernetes + Tekton
    CoreRouter API + durable admission/migration state
    SDN controller
    Mininet topology + BMv2 switches + traffic/evidence capture
```

### Measured host envelope and proposed guest cap

Read-only capacity snapshot at 2026-11-17 15:01 +07:00:

- 96 online logical CPUs; load averages 11.38 / 11.63 / 12.27.
- 251 GiB total RAM, 134 GiB currently available, and no swap.
- 1.6 TiB free on the workspace filesystem.
- This is a point-in-time capacity observation, not a reservation or guarantee
  of future idle capacity. A host-visible process snapshot at 14:57 showed
  several other users' CPU/RAM-intensive jobs, this project's evaluation
  processes, one existing QEMU/KVM guest, and four unrelated Python workers
  using about one logical CPU and 13.4 GiB RSS each. Their VM
  ownership/configuration was not visible; do not reuse or change them.

An escalated read-only host check at 15:07 +07:00 showed 133 GiB available,
load averages 10.72 / 11.04 / 11.79, four unrelated Python workers near 100%
CPU and about 13.4 GiB RSS each, several project Python workers near 100% CPU,
and an existing QEMU process. Libvirt management was denied by polkit; the
current execution environment cannot access `/dev/kvm`. Therefore provisioning
is blocked until high-load runs finish and an administrator-provided
KVM/libvirt access path is available.

Use a capped guest: **12 vCPU, 20 GiB guest RAM, and a 120 GiB sparse disk**.
This allows ten guest vCPUs for the ten BMv2 switch processes, with two for
guest control-plane work. Put the VM in a low-priority host cgroup with
`CPUQuota=1200%`, `CPUWeight=10`, `MemoryHigh=22GiB`, `MemoryMax=24GiB`,
`IOWeight=10`, and 50 MiB/s read/write ceilings on the workspace backing
device. Keep 4 GiB between assigned guest RAM and the host cgroup maximum for
QEMU/device-emulation overhead. Record actual cgroup settings in the run
manifest. The cgroup RAM cap is under 10% of installed host RAM and its CPU cap
is at most 12 of 96 logical CPUs. These are hard upper bounds for the testbed,
not exclusive reservations. Latency results must include VM quota and host
load context.

Before VM creation and again before each experiment phase, require a stable
five-minute host preflight with `MemAvailable >= 96 GiB` and one-minute load
average below 24. The preflight must run with host-level process and cgroup
visibility; the current Codex sandbox exposes only its own process namespace,
so its `ps`/`ss` output cannot certify server-wide process or port availability.
If host-level visibility is unavailable, or any active high-load workload
owner/status is unknown, do not create/start the VM or begin a phase. The
14:57 process snapshot showed concurrent project evaluations and unrelated
compute workers, and current host process visibility is unavailable, so the
current recommendation is **wait for host-level confirmation that these runs
have finished, then recheck**, rather than start alongside unknown workloads.
If a gate fails, do not start the next workload. While a phase runs, sample
host/guest CPU and memory every 30 seconds. If `MemAvailable < 64 GiB` or load
average exceeds 48 for five
consecutive minutes, mark the current measurement as resource-contended and do
not begin the next phase until the host recovers. Do not automatically kill or
suspend a partially recorded experiment. Keep the VM at low CPU/I/O weight so
ordinary host work receives priority when resources are contested. The VM,
ports, containers, routes, and files can be isolated from other projects; a
shared host cannot promise zero CPU/I/O scheduling impact. Strict zero impact
requires an idle host window or an exclusively reserved machine.

Guest networking defaults to QEMU user-mode
networking, so the guest can make outbound connections without adding a host
bridge, route, or firewall rule. Any guest access is forwarded only to a
verified free port on host loopback. If QEMU user-mode networking or localhost
forwarding is unavailable, pause and request separate approval before an
administrator creates a dedicated NAT bridge/network on the host. Inside the
guest, internal service ports may use repository defaults.

Within the guest, deployment will use a dedicated cluster and Docker project
identity `core-router-hil`. Container names, volumes, labels, systemd units,
logs, and output directories receive the same prefix. The cluster's
`cluster-admin` Tekton binding is scoped to this disposable guest, not a shared
host cluster. Image versions, P4 compiler output hashes, Kubernetes/Tekton
versions, manifests, topology, port map, and run commands are pinned in the
guest manifest before experiments.

Run the SDN controller as a guest-local system service with access to the
guest Docker daemon, because its current BMv2 Thrift adapter shells out to
`docker exec`. Keep the CoreRouter API in a separate guest-local service and
do not mount the Docker socket into the API process. The API reaches the SDN
controller over the guest loopback interface and reaches Kubernetes through
the guest kubeconfig. Tekton tasks act only on the guest cluster.

The P4 topology profile is generated from the actual Mininet interface/port
map. Controller bootstrap must refuse unknown switches or incomplete mappings.
Before stronger HIL claims, steering must carry the admitted realization and
operation identity; teardown must remove rules and verify readback before the
reservation ledger releases resources. Until then, the HIL API's actuation path
stays closed and only non-actuating component tests may run.

## Build and validation phases

1. **Host access and capacity gate:** use an admin-provisioned VM/hypervisor
   access path; inspect current host capacity and resource owners; verify the
   proposed quota leaves headroom. No host workload is stopped.
2. **Guest base:** create/start the bounded VM, install pinned runtime
   dependencies, and record guest/host resource limits. Confirm host bridges,
   routes, and listeners are unchanged.
3. **Control plane:** deploy the single-node Kubernetes cluster, namespace,
   Tekton, RBAC, VNF manifests, backend, durable state volume, and SDN
   controller. Keep all API/controller binds guest-local.
4. **Data plane:** build/reuse the pinned P4 programs; start Mininet/BMv2 with
   unique guest-local names; record the observed switch IDs, interface/port
   mappings, and per-switch MSD profiles.
5. **Safe integration checks:** verify health, topology, workload deployment
   readiness, rule install/readback/delete, packet forwarding and counters with
   request-correlated records. Keep production orchestration actuation disabled
   until admitted-realization binding and teardown gates pass.
6. **Experiment handoff:** write a runbook for bounded API/concurrency, MSD
   over-depth, migration, teardown, and stability phases. Long runs require
   their own explicit phase command and write only under `results/hil/<run-id>`.

## Recovery and cleanup

Provide explicit `status`, `start`, `stop`, and `destroy` operations scoped to
the `core-router-hil` VM/resource identity. Stop/destroy must never use blanket
commands such as removing all Docker containers, networks, Kubernetes
namespaces, or host interfaces. Preserve logs and manifests outside ephemeral
guest storage before VM teardown. On interrupted teardown, retain the guest and
resource ledger for inspection rather than claiming cleanup succeeded.

## Constraints and unresolved input

- The current Codex execution account cannot access `/var/run/docker.sock`,
  has no usable Kubernetes context, cannot use `sudo` in this sandbox, and
  cannot connect to the libvirt user runtime. These are observed blockers to
  provisioning, not proof that the server lacks an administrator-managed VM.
- Host ports 8000–8002 are already occupied. Do not forward or bind those
  ports on the host.
- Current experiments and unrelated host users' workloads are running
  concurrently. The measured load is not an exclusive resource reservation;
  use the caps and preflight gates above and recheck live host state before
  provisioning and every experiment phase.
- An administrator-accessible VM/hypervisor path must be made available to
  the implementation session. Do not request or store an administrator
  password in repository files or chat.
- Exact dependency/image versions and guest network CIDRs are pinned only
  after a read-only check inside the provisioned guest; avoid collisions with
  the guest's existing interfaces and routes.
- VM networking must use QEMU user-mode networking unless the user separately
  approves a host-side libvirt bridge/NAT setup. This choice affects the VM
  manager and the available guest access/port-forwarding mechanism.
