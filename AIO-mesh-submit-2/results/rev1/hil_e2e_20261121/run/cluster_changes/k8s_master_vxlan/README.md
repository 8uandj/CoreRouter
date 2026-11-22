# k8s-master Calico VXLAN fix (authorised by user 2026-11-21)

Symptom: Pods on k8s-master unreachable from 3s-com (host and Mininet); 3s-com sends correct
VXLAN (UDP 4789, VNI 4096) to 10.10.7.10, nothing returns.

Diagnosis (privileged pod `hil-diag-k8s-master`, hostNetwork/hostPID, nsenter into host;
read-only first: diag_readonly_1.txt, diag_tcpdump_k8s_master.txt, diag_tcpdump_after_port.txt):
1. firewalld zone `public` (enp1s0) allowed 8472/udp (Flannel VXLAN) but not 4789/udp
   (Calico VXLAN in use) -> outer VXLAN rejected, "admin prohibited filter".
2. after (1), decapsulated packets on vxlan.calico were rejected on forward to cali*:
   vxlan.calico had no zone (the Flannel equivalents flannel.1/cni0 are in `trusted`).
Note: on k8s-master the outer source appears as 10.10.1.80, not 10.10.6.231 (NAT between
subnets); not changed.

Fix (runtime only, NOT --permanent; undone by `firewall-cmd --reload` or reboot): APPLIED.log
  firewall-cmd --zone=public  --add-port=4789/udp
  firewall-cmd --zone=trusted --add-interface=vxlan.calico
Rollback: ROLLBACK.sh. Before/after: firewalld_ports_*.txt, trusted_*.txt.
Verification: ping from 3s-com to 4 k8s-master Pods 3/3 each after fix (0/3 before).
Untouched: remaining rejects of UDP 7946 from 10.10.1.80 (unrelated gossip traffic).
Effect on campaign_corrected_model: requests probed before the fix time in APPLIED.log
recorded 0/20 for k8s-master Pods; they are kept as-is and re-probed separately.
