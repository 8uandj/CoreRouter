#!/usr/bin/env bash
# Remove the two NAT rules added for the HIL e2e run (tagged corerouter-hil-e2e).
H=/home/CoreRouter/results/hil/e2e_tools/hostexec.sh
$H 'for s in 10.0.0.0/24 10.1.240.0/24; do iptables -t nat -D POSTROUTING -s $s -o vxlan.calico -m comment --comment corerouter-hil-e2e -j MASQUERADE; done'
