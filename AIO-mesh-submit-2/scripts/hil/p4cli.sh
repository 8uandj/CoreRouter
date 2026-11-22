#!/usr/bin/env bash
# Run simple_switch_CLI commands against live switch sN (thrift 19090+N). Usage: p4cli.sh s9 'table_dump routing_v6'
N=${1#s}; shift
printf '%s\n' "$@" | docker run --rm -i --network=host --entrypoint simple_switch_CLI p4lang/p4app:latest --thrift-port $((19090+N)) 2>&1
