# Isolated HIL Deployment

## Current gate

The testbed must run inside a dedicated `core-router-hil` VM. Do not run
`setup_testbed.sh` on the shared server: it installs host packages and changes
host services/networking. No host service, Docker daemon, Kubernetes cluster,
bridge, route, or firewall rule may be changed for this deployment.

Run the read-only host gate from a root shell in the server's host PID
namespace:

```bash
sudo python3 scripts/hil/host_preflight.py
```

The command requires KVM and system libvirt access, cgroup v2 CPU/memory/I/O
controllers, at least 96 GiB available RAM, load below 24, at least 150 GiB
free on the VM disk filesystem, and five minutes without a process using 80%
or more of one CPU in the process snapshot. It prints `BLOCKED` and exits
nonzero on any failed check. The capacity checks repeat every 30 seconds for
five minutes before reporting `READY`.
It does not create files, start services, alter network state, or provision a
VM.

## Deployment phases

1. **Host and VM access:** run the preflight above. Resolve any reported busy
   processes by waiting for their owners to finish; do not stop or reprioritize
   them. Confirm the existing QEMU guest and libvirt owner with the server
   administrator. Only then provision the bounded VM: 12 vCPU, 20 GiB guest
   RAM, 24 GiB host cgroup maximum, and a 120 GiB sparse disk. Use QEMU
   user-mode networking with no host port forwards by default.
2. **Guest software:** install Docker, a single-node Kubernetes distribution,
   Tekton, Mininet, BMv2/P4 dependencies, and the CoreRouter services inside the
   guest. Keep the SDN controller's Docker socket guest-local; never mount it
   into the API. Pin image and package versions in the guest manifest before
   starting services. Do not run production steering while realization binding
   and confirmed P4 teardown remain unsupported.
3. **HIL validation:** start only guest-local resources with names prefixed
   `core-router-hil`. Record actual switch IDs, ports, MSD profiles, observed
   rules/readback, packet counters, and request-correlated timing. Stop before
   long experiment phases unless the host preflight passes again. Store HIL
   artifacts under `results/hil/<run-id>`.

## Present blocker

The latest host-level check found concurrent high-CPU project and unrelated
workloads, an existing QEMU guest with unknown owner/configuration, and
libvirt management denied because no polkit agent was available. The current
execution account also cannot access `/dev/kvm`. Do not start another VM until
the owners confirm the active workloads have finished and an administrator
provides a supported KVM/libvirt path. The preflight script is the required
recheck after that state changes.

The current runbook intentionally does not provide a host-side setup command:
the existing `setup_testbed.sh` is a host installer and is not safe for this
shared server. Guest provisioning must be supplied through the approved VM
management path, without modifying shared host services.
