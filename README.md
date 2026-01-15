# Centralized Operations Platform for Next-Generation Core Networks

## Overview

The **Centralized Operations Platform** is a cloud-native orchestration and data analytics solution designed for **Virtual Network Functions (VNFs)** in next-generation core networks. This project functions as an automated data pipeline that manages the entire service lifecycle—from ingestion and deployment to real-time monitoring and AI-driven security response.

By integrating **SDN/NFV** principles with **Cloud-native CI/CD (Tekton)** and **Deep Learning**, the platform achieves high-performance orchestration with sub-30-second deployment times and identifies DDoS attacks with **96.8% accuracy**.

**Key Features include:**
- **Automated Lifecycle Management**: Full VNF lifecycle (Instantiation, Scaling, Termination) compliant with **ETSI NFV-MANO**.
- **Infrastructure as Code (IaC)**: Standardized 14-task deployment workflow using **Tekton**, ensuring consistent environment provisioning.
- **Real-time Stream Analytics**: Ingests and processes streaming network traffic to detect DDoS threats in under 2 seconds.
- **Dynamic Resource Optimization**: Uses real-time monitoring data to trigger automated "Scale-out" actions to maintain service availability.
- **Unified Observability**: Centralized dashboard for visualizing network topology and time-series resource metrics.

---

## Project Structure

The project directory consists of the following files and modules:

- **operations_backend/**: Core logic for interfacing with Kubernetes and Open Source MANO (OSM) APIs.
- **ai_security_service/**: Real-time detector using Deep Learning to evaluate traffic flow logs.
- **tekton_pipelines/**: YAML definitions for standardized deployment and scaling Tasks.
- **vnf_descriptors/**: TOSCA/YAML files defining VNF images and resource requirements.
- **traffic_simulator_GCP.py**: Script to generate normal and malicious traffic streams for pipeline testing.
- **run_ops_pipeline.sh**: Master automation script for managing the platform on GCP instances.
- **monitor_check.ipynb**: Jupyter notebook for post-hoc analysis of telemetry and security logs.
- **requirements.txt**: Python dependency list (PyTorch, Scikit-learn, Kubernetes-client, etc.).

---

# Prerequisites

This document describes all required components to run the **Centralized Operations Platform** locally or on Google Cloud Platform (GCP).

---

## Local Environment

### System Requirements

- **Operating System**: Linux (Ubuntu / Fedora recommended)
- **Python**: `3.10.0` or newer
- **kubectl**: Compatible with your Kubernetes version

---

### Kubernetes (MicroK8s)

Install MicroK8s:

```bash
sudo snap install microk8s --classic
microk8s enable dns storage dashboard #Enable required addons:
microk8s status --wait-ready #Verify installation:

```
Tekton Pipelines
Install the latest Tekton Pipelines release:

```bash
kubectl apply --filename https://storage.googleapis.com/tekton-releases/pipeline/latest/release.yaml
kubectl get pods -n tekton-pipelines #Verify Tekton installation:
```