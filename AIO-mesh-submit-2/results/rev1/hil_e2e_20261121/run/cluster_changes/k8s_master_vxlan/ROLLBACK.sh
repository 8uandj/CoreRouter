#!/bin/sh
# Undo the HIL VXLAN fix on k8s-master (runtime-only change; also undone by `firewall-cmd --reload` or reboot).
kubectl -n core-router exec hil-diag-k8s-master -- nsenter -t 1 -m -u -n -i -p -- firewall-cmd --zone=public --remove-port=4789/udp
# If the diag pod is gone, run on k8s-master as root: firewall-cmd --zone=public --remove-port=4789/udp
kubectl -n core-router exec hil-diag-k8s-master -- nsenter -t 1 -m -u -n -i -p -- firewall-cmd --zone=trusted --remove-interface=vxlan.calico
# without the diag pod, on k8s-master as root: firewall-cmd --zone=trusted --remove-interface=vxlan.calico
