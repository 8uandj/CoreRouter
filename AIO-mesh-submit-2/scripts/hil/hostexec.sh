#!/usr/bin/env bash
# Run a command as root in the host namespaces (privileged helper container + chroot).
exec docker run --rm --privileged --pid=host --network=host -v /:/host --entrypoint /usr/sbin/chroot p4lang/p4app:latest /host /bin/bash -c "$*"
