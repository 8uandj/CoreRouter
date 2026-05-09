#!/bin/bash
# deploy_helper.sh — Trigger Tekton pipeline triển khai 1 VNF (Phase 2)
#
# Usage:
#   ./deploy_helper.sh <type> <deploy-name> <location>
#   ./deploy_helper.sh frr  vnf-frr-001   hanoi-1
#   ./deploy_helper.sh voc  vnf-voc-hn1   hanoi-1
#
# Available types: frr, firewall, nat, voc, idps, lb
#   (phải khớp với key trong ConfigMap vnf-inputs)

set -euo pipefail

TYPE="${1:-}"
NAME="${2:-}"
LOC="${3:-}"

if [ -z "$TYPE" ] || [ -z "$NAME" ] || [ -z "$LOC" ]; then
    echo "Usage:   ./deploy_helper.sh <vnf-type> <deploy-name> <location>"
    echo "Example: ./deploy_helper.sh frr vnf-frr-001 hanoi-1"
    echo ""
    echo "Available types: frr, firewall, nat, voc, idps, lb"
    echo "  (Phải tồn tại key 'vnf-<type>.yaml' trong ConfigMap vnf-inputs)"
    exit 1
fi

FILE_NAME="vnf-${TYPE}.yaml"
NAMESPACE="core-router"

echo "🚀 Deploying ${NAME} (type=${TYPE}, location=${LOC})..."
echo "   Template: ${FILE_NAME} from ConfigMap vnf-inputs"
echo ""

cat <<EOF | sudo microk8s kubectl create -f -
apiVersion: tekton.dev/v1
kind: PipelineRun
metadata:
  generateName: deploy-${TYPE}-
  namespace: ${NAMESPACE}
spec:
  pipelineRef: { name: vnf-lcm-fast }
  taskRunTemplate: { serviceAccountName: tekton-admin }
  workspaces:
  - name: ws
    volumeClaimTemplate:
      spec:
        accessModes: [ReadWriteOnce]
        resources: { requests: { storage: 50Mi } }
  params:
  - { name: ns,            value: "${NAMESPACE}" }
  - { name: deployName,    value: "${NAME}" }
  - { name: fileName,      value: "${FILE_NAME}" }
  - { name: labelSelector, value: "app=${NAME}" }
  - { name: location,      value: "${LOC}" }
EOF

echo ""
echo "✅ PipelineRun created! Monitor with:"
echo "   sudo microk8s kubectl get pods -n ${NAMESPACE} -w"
echo "   sudo microk8s kubectl get pipelinerun -n ${NAMESPACE}"
