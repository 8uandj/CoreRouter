#!/usr/bin/env python3
"""Read-only host gate for the isolated CoreRouter HIL VM.

This command never creates files, changes host networking, starts services,
or modifies libvirt state. Run it as root on the server host, outside a
container/Codex sandbox. A successful result is required before provisioning.
"""

from __future__ import annotations

import argparse
import os
import pwd
import shutil
import subprocess
import sys
import time
from pathlib import Path


MIN_AVAILABLE_GIB = 96
MAX_LOAD_1M = 24.0
MAX_BUSY_PROCESS_CPU = 80.0
SAMPLE_SECONDS = 300
SAMPLE_INTERVAL_SECONDS = 30
VM_NAME = "core-router-hil"


class GateFailure(RuntimeError):
    pass


def gib(value: int) -> float:
    return value / (1024**3)


def read_mem_available_gib() -> float:
    for line in Path("/proc/meminfo").read_text().splitlines():
        if line.startswith("MemAvailable:"):
            return int(line.split()[1]) * 1024 / (1024**3)
    raise GateFailure("MemAvailable is absent from /proc/meminfo")


def load_averages() -> tuple[float, float, float]:
    values = Path("/proc/loadavg").read_text().split()[:3]
    return tuple(float(value) for value in values)  # type: ignore[return-value]


def command_output(command: list[str], timeout: int = 10) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        command,
        check=False,
        capture_output=True,
        text=True,
        timeout=timeout,
    )


def require_host_root() -> None:
    if os.geteuid() != 0:
        raise GateFailure("run as root on the server host; current UID is not 0")

    try:
        init_name = Path("/proc/1/comm").read_text().strip()
        same_pid_namespace = os.readlink("/proc/1/ns/pid") == os.readlink(
            "/proc/self/ns/pid"
        )
    except OSError as exc:
        raise GateFailure(f"cannot verify host process namespace: {exc}") from exc

    if init_name not in {"systemd", "init"} or not same_pid_namespace:
        raise GateFailure(
            "not running in the host PID namespace; container and sandbox views "
            "cannot certify other processes"
        )


def require_cgroup_v2() -> None:
    controllers_file = Path("/sys/fs/cgroup/cgroup.controllers")
    if not controllers_file.is_file():
        raise GateFailure("host cgroup v2 is unavailable")
    controllers = set(controllers_file.read_text().split())
    missing = {"cpu", "memory", "io"} - controllers
    if missing:
        raise GateFailure(f"host cgroup v2 lacks required controllers: {sorted(missing)}")


def require_kvm_and_libvirt() -> None:
    kvm = Path("/dev/kvm")
    if not kvm.exists() or not os.access(kvm, os.R_OK | os.W_OK):
        raise GateFailure("/dev/kvm is missing or not readable/writable")

    virsh = shutil.which("virsh")
    if not virsh:
        raise GateFailure("virsh is not installed")
    result = command_output([virsh, "-c", "qemu:///system", "list", "--all"])
    if result.returncode:
        detail = (result.stderr or result.stdout).strip()
        raise GateFailure(f"system libvirt is inaccessible: {detail}")
    if VM_NAME in result.stdout.split():
        raise GateFailure(f"VM name {VM_NAME!r} already exists; inspect it manually")


def require_disk_headroom(path: Path) -> None:
    existing = path
    while not existing.exists() and existing != existing.parent:
        existing = existing.parent
    available_gib = gib(shutil.disk_usage(existing).free)
    if available_gib < 150:
        raise GateFailure(
            f"only {available_gib:.1f} GiB free at {existing}; need 150 GiB "
            "for the sparse guest disk plus artifacts"
        )


def process_cpu_snapshot() -> dict[int, tuple[str, str, int, float]]:
    """Return PID -> (user, command, CPU ticks, RSS GiB) for visible host PIDs."""
    snapshot = {}
    for proc in Path("/proc").iterdir():
        if not proc.name.isdigit():
            continue
        try:
            stat = (proc / "stat").read_text()
            fields = stat[stat.rfind(")") + 2 :].split()
            cpu_ticks = int(fields[11]) + int(fields[12])
            status = (proc / "status").read_text().splitlines()
            uid = int(next(line.split()[1] for line in status if line.startswith("Uid:")))
            rss_kib = int(next(line.split()[1] for line in status if line.startswith("VmRSS:")))
            command = (proc / "comm").read_text().strip()
            snapshot[int(proc.name)] = (
                pwd.getpwuid(uid).pw_name,
                command,
                cpu_ticks,
                rss_kib * 1024 / (1024**3),
            )
        except (OSError, StopIteration, ValueError, KeyError):
            # Processes can exit between directory enumeration and proc reads.
            continue
    return snapshot


def busy_processes(
    previous: dict[int, tuple[str, str, int, float]],
    current: dict[int, tuple[str, str, int, float]],
    elapsed_seconds: float,
) -> list[tuple[str, int, str, float, float]]:
    ticks_per_second = os.sysconf("SC_CLK_TCK")
    busy = []
    for pid, (user, command, cpu_ticks, rss_gib) in current.items():
        prior = previous.get(pid)
        if prior is None:
            continue
        cpu_percent = (cpu_ticks - prior[2]) * 100 / (ticks_per_second * elapsed_seconds)
        if cpu_percent >= MAX_BUSY_PROCESS_CPU:
            busy.append((user, pid, command, cpu_percent, rss_gib))
    return busy


def check_capacity(label: str, disk_path: Path) -> dict[int, tuple[str, str, int, float]]:
    available_gib = read_mem_available_gib()
    load_1m, load_5m, load_15m = load_averages()
    print(
        f"{label}: MemAvailable={available_gib:.1f} GiB, "
        f"load={load_1m:.2f}/{load_5m:.2f}/{load_15m:.2f}"
    )
    if available_gib < MIN_AVAILABLE_GIB:
        raise GateFailure(
            f"MemAvailable {available_gib:.1f} GiB is below {MIN_AVAILABLE_GIB} GiB"
        )
    if load_1m >= MAX_LOAD_1M:
        raise GateFailure(f"one-minute load {load_1m:.2f} is not below {MAX_LOAD_1M}")

    require_disk_headroom(disk_path)
    return process_cpu_snapshot()


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--disk-path",
        type=Path,
        default=Path("/dis/users/dcs/CoreRouter/results/hil"),
        help="filesystem where the VM disk and HIL artifacts will be stored",
    )
    args = parser.parse_args()

    try:
        require_host_root()
        require_cgroup_v2()
        require_kvm_and_libvirt()
        previous = check_capacity("initial", args.disk_path)

        samples = SAMPLE_SECONDS // SAMPLE_INTERVAL_SECONDS
        print(
            f"Capacity gate: sampling for {SAMPLE_SECONDS}s "
            f"({samples} intervals of {SAMPLE_INTERVAL_SECONDS}s)."
        )
        for index in range(samples):
            time.sleep(SAMPLE_INTERVAL_SECONDS)
            current = check_capacity(f"sample {index + 1}/{samples}", args.disk_path)
            busy = busy_processes(previous, current, SAMPLE_INTERVAL_SECONDS)
            if busy:
                print("High-CPU host processes (must finish before provisioning):")
                for user, pid, command, cpu, rss_gib in busy:
                    print(
                        f"  user={user} pid={pid} command={command} "
                        f"cpu={cpu:.1f}% rss={rss_gib:.1f}GiB"
                    )
                raise GateFailure(
                    "a host process used at least 80% of one CPU in the last interval"
                )
            previous = current

    except (GateFailure, OSError, subprocess.TimeoutExpired) as exc:
        print(f"BLOCKED: {exc}", file=sys.stderr)
        return 2

    print("READY: host preflight passed. Provision only the isolated VM profile.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
