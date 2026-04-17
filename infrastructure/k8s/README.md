# 3S-COM K8s Infrastructure Layer

This directory contains the Kubernetes and Tekton manifests for the 3S-COM Orchestrator.

## Structure

```
infrastructure/k8s/
├── manifests/       # VNF Deployment & Config manifests
│   ├── vnf-frr.yaml
│   ├── vnf-firewall.yaml
│   ├── vnf-idps.yaml
│   └── config-frr.yaml
├── tekton/          # Tekton Pipelines and Tasks
│   ├── pipeline-vnf-wide.yaml
│   ├── tasks/
│   └── pipelinerun-vnf-wide.yaml
├── setup/           # Environment setup (RBAC, Namespace)
│   ├── ns-vnf.yaml
│   ├── tekton-admin.yaml
│   └── kustomization.yaml
└── README.md
```

## Quick Start
To prepare the environment:
```bash
kubectl apply -k infrastructure/k8s/setup/
```

To deploy a VNF manually via Tekton:
```bash
kubectl create -f infrastructure/k8s/tekton/pipelinerun-vnf-wide.yaml
```