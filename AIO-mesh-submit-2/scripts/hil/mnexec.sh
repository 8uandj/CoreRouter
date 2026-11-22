#!/usr/bin/env bash
# Run a command inside Mininet host hN's network namespace (root via privileged helper container).
# Usage: mnexec.sh h9 'ip route; ping -c1 10.1.189.159'
set -euo pipefail
H="$1"; shift
PID=$(ps -eo pid,cmd | awk -v h="mininet:$H" '$NF==h {print $1}' | head -1)
[ -n "$PID" ] || { echo "no PID for $H" >&2; exit 2; }
exec docker run --rm --privileged --pid=host --network=host -v /:/host --entrypoint /usr/bin/nsenter \
  p4lang/p4app:latest -t "$PID" -n -- chroot /host /bin/bash -c "$*"
