import uuid
import logging
from typing import Dict, Any, List
from kubernetes import client, config
from src.core.interfaces.orchestrator import IOrchestrator

logger = logging.getLogger("TektonOrchestrator")

class TektonOrchestrator(IOrchestrator):
    def __init__(self):
        self.custom_api = None
        self.apps_api = None
        self._connect()

    def _connect(self):
        try:
            config.load_kube_config()
            self.custom_api = client.CustomObjectsApi()
            self.apps_api = client.AppsV1Api()
        except:
            try:
                config.load_incluster_config()
                self.custom_api = client.CustomObjectsApi()
                self.apps_api = client.AppsV1Api()
            except Exception as e:
                logger.error(f"Failed to connect to K8s: {e}")

    def trigger_deploy(self, name: str, vnf_type: str, profile: str, location: str = "auto") -> Dict[str, Any]:
        template_file = "vnf-frr.yaml"
        if vnf_type == "firewall": template_file = "vnf-firewall.yaml"
        elif vnf_type == "idps": template_file = "vnf-idps.yaml"

        run_name = f"deploy-{vnf_type}-{uuid.uuid4().hex[:6]}"
        
        # Manifests are now in infrastructure/k8s/manifests/ 
        # but Tekton params usually take names relative to workspace or persistent volumes.
        # Assuming the YAMLs are mounted/available to Tekton.
        
        pipeline_run = {
            "apiVersion": "tekton.dev/v1",
            "kind": "PipelineRun",
            "metadata": {"name": run_name},
            "spec": {
                "pipelineRef": {"name": "vnf-lcm-fast"}, 
                "taskRunTemplate": {"serviceAccountName": "tekton-admin"},
                "params": [
                    {"name": "ns", "value": "core-router"},
                    {"name": "deployName", "value": name},
                    {"name": "fileName", "value": template_file},
                    {"name": "labelSelector", "value": f"app={name}"},
                    {"name": "location", "value": location}
                ],
                "workspaces": [
                    {
                        "name": "ws",
                        "volumeClaimTemplate": {
                            "spec": {
                                "accessModes": ["ReadWriteOnce"],
                                "resources": {"requests": {"storage": "50Mi"}}
                            }
                        }
                    }
                ]
            }
        }

        try:
            if self.custom_api:
                self.custom_api.create_namespaced_custom_object(
                    group="tekton.dev", version="v1", namespace="core-router",
                    plural="pipelineruns", body=pipeline_run
                )
                return {
                    "status": "success", "runName": run_name,
                    "message": f"Successfully initialized {vnf_type.upper()} ({profile}) instance."
                }
        except Exception as e:
            logger.error(f"Deploy Error: {e}")
            return {"status": "error", "message": str(e)}
        return {"status": "error", "message": "K8s connection failed"}

    def trigger_terminate(self, vnf_name: str) -> Dict[str, Any]:
        run_name = f"terminate-{vnf_name[:20]}-{uuid.uuid4().hex[:6]}"
        pipeline_run = {
            "apiVersion": "tekton.dev/v1",
            "kind": "PipelineRun",
            "metadata": {"name": run_name},
            "spec": {
                "pipelineRef": {"name": "vnf-terminate"},
                "taskRunTemplate": {"serviceAccountName": "tekton-admin"},
                "params": [{"name": "deployName", "value": vnf_name}]
            }
        }
        try:
            if self.custom_api:
                self.custom_api.create_namespaced_custom_object(
                    group="tekton.dev", version="v1", namespace="core-router",
                    plural="pipelineruns", body=pipeline_run
                )
                return {"status": "success", "message": f"Termination pipeline started for '{vnf_name}'"}
        except Exception as e:
            logger.error(f"Terminate Error: {e}")
            return {"status": "error", "message": str(e)}
        return {"status": "error", "message": "K8s connection failed"}

    def get_status(self) -> Dict[str, Any]:
        if not self.custom_api: return {}
        try:
            runs = self.custom_api.list_namespaced_custom_object(
                group="tekton.dev", version="v1", namespace="core-router", plural="pipelineruns"
            )
            items = runs.get('items', [])
            if not items: 
                return {"name": "No Run Found", "tasks": [], "overallStatus": "None"}
            
            latest = sorted(items, key=lambda x: x['metadata']['creationTimestamp'], reverse=True)[0]
            conditions = latest.get('status', {}).get('conditions', [{}])
            overall_reason = conditions[0].get('reason', 'Running')
            
            tasks = []
            child_refs = latest.get('status', {}).get('childReferences', [])
            for ref in child_refs:
                tasks.append({
                    "name": ref.get('pipelineTaskName', 'Unknown Task'),
                    "status": "Succeeded" if overall_reason == "Succeeded" else "Running"
                })
                
            return {"name": latest['metadata']['name'], "overallStatus": overall_reason, "tasks": tasks}
        except Exception as e:
            return {"name": "Error", "tasks": [], "overallStatus": str(e)}

    def list_vnfs(self) -> List[Dict[str, Any]]:
        if not self.apps_api:
            return []
        try:
            deploys = self.apps_api.list_namespaced_deployment(namespace="core-router")
            vnfs = []
            for dep in deploys.items:
                labels = dep.metadata.labels or {}
                location = labels.get("core-router/location", "auto")
                vnfs.append({
                    "id": dep.metadata.name,
                    "labels": labels,
                    "ready": dep.status.ready_replicas or 0,
                    "desired": dep.spec.replicas or 1,
                    "data": {
                        "role": labels.get("core-router/role", "router"),
                        "location": location,
                        "status": "Running" if (dep.status.ready_replicas or 0) > 0 else "Pending"
                    }
                })
            return vnfs
        except Exception as e:
            logger.error(f"Error listing VNFs: {e}")
            return []
