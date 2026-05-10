#!/bin/bash

# Usage: ./deploy_helper.sh <TYPE> <DEPLOY_NAME> <LOCATION>
# Example: ./deploy_helper.sh frr vnf-frr-001 hanoi-1

TYPE=$1
NAME=$2
LOC=$3

if [ -z "$TYPE" ] || [ -z "$NAME" ] || [ -z "$LOC" ]; then
    echo "Usage: ./deploy_helper.sh <vnf-type> <deploy-name> <location>"
    echo "Example: ./deploy_helper.sh frr vnf-frr-001 hanoi-1"
    echo "Available types: frr, firewall, nat, voc, idps, lb"
    exit 1
fi

FILE_NAME="vnf-${TYPE}.yaml"

echo "🚀 Kích hoạt Tekton deploy ${NAME} (loại ${TYPE}) tại ${LOC}..."

cat <<EOF | sudo microk8s kubectl create -f -
apiVersion: tekton.dev/v1
kind: PipelineRun
metadata: { generateName: deploy-${TYPE}-, namespace: core-router }
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
  - { name: ns, value: core-router }
  - { name: deployName, value: ${NAME} }
  - { name: fileName,   value: ${FILE_NAME} }
  - { name: labelSelector, value: app=${NAME} }
  - { name: location,   value: ${LOC} }
EOF

echo "✅ Đã gửi lệnh cho Tekton! Gõ 'sudo microk8s kubectl get pods -n core-router -w' để xem kết quả."
