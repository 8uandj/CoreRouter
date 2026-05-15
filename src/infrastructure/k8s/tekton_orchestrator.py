import uuid
import logging
import urllib3
from typing import Dict, Any, List, Optional
from kubernetes import client, config
from src.core.interfaces.orchestrator import IOrchestrator

urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

logger = logging.getLogger("TektonOrchestrator")

MIGRATE_PIPELINE_NAME = "vnf-migrate-single"
DEFAULT_NAMESPACE = "core-router"


class TektonOrchestrator(IOrchestrator):
    def __init__(self):
        self.custom_api = None
        self.apps_api = None
        self.core_api = None
        self._connect()

    def _connect(self):
        kubeconfig_paths = [
            "/var/snap/microk8s/current/credentials/client.config",  # MicroK8s — ưu tiên cao nhất
            None,  # Default ~/.kube/config — fallback
        ]
        
        connected = False
        for path in kubeconfig_paths:
            try:
                if path:
                    config.load_kube_config(config_file=path)
                else:
                    config.load_kube_config()
                
                conf = client.Configuration.get_default_copy()
                conf.verify_ssl = False
                client.Configuration.set_default(conf)
                
                self.custom_api = client.CustomObjectsApi()
                self.apps_api = client.AppsV1Api()
                self.core_api = client.CoreV1Api()
                connected = True
                break
            except Exception:
                pass

        if not connected:
            try:
                config.load_incluster_config()
                
                conf = client.Configuration.get_default_copy()
                conf.verify_ssl = False
                client.Configuration.set_default(conf)
                
                self.custom_api = client.CustomObjectsApi()
                self.apps_api = client.AppsV1Api()
                self.core_api = client.CoreV1Api()
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

    # --- Phase 2.2: Make-Before-Break single-VNF migration -------------------

    def trigger_migrate_single(
        self,
        old_deploy_name: str,
        new_deploy_name: str,
        file_name: str,
        target_location: str = "auto",
        namespace: str = DEFAULT_NAMESPACE,
        node_hostname: str = "",
    ) -> Dict[str, Any]:
        """MAKE-only step of Make-Before-Break.

        Creates a replacement Deployment + Service via the ``vnf-migrate-single``
        Tekton Pipeline. Does NOT steer traffic, does NOT delete the old VNF.
        Caller is responsible for invoking the SDN steer step and, only after
        steer is verified, calling :meth:`break_old_vnf`.
        """
        if not self.custom_api:
            return {"status": "error", "message": "K8s connection failed"}

        run_name = f"mig-{new_deploy_name[:24]}-{uuid.uuid4().hex[:6]}"
        pipeline_run = {
            "apiVersion": "tekton.dev/v1",
            "kind": "PipelineRun",
            "metadata": {"name": run_name},
            "spec": {
                "pipelineRef": {"name": MIGRATE_PIPELINE_NAME},
                "taskRunTemplate": {"serviceAccountName": "tekton-admin"},
                "params": [
                    {"name": "ns", "value": namespace},
                    {"name": "oldDeployName", "value": old_deploy_name},
                    {"name": "newDeployName", "value": new_deploy_name},
                    {"name": "fileName", "value": file_name},
                    {"name": "targetLocation", "value": target_location},
                    {"name": "labelSelector", "value": f"app={new_deploy_name}"},
                ],
                "workspaces": [
                    {
                        "name": "ws",
                        "volumeClaimTemplate": {
                            "spec": {
                                "accessModes": ["ReadWriteOnce"],
                                "resources": {"requests": {"storage": "50Mi"}},
                            }
                        },
                    }
                ],
            },
        }

        try:
            self.custom_api.create_namespaced_custom_object(
                group="tekton.dev", version="v1", namespace=namespace,
                plural="pipelineruns", body=pipeline_run,
            )
            return {
                "status": "success",
                "phase": "MAKE",
                "runName": run_name,
                "namespace": namespace,
                "oldDeployName": old_deploy_name,
                "newDeployName": new_deploy_name,
                "fileName": file_name,
                "targetLocation": target_location,
                "message": (
                    f"Migration MAKE pipeline started: {run_name}. "
                    "Old VNF kept; call break_old_vnf only after steer success."
                ),
            }
        except Exception as e:
            logger.error(f"Migrate Make Error: {e}")
            return {"status": "error", "message": str(e)}

    def get_pipelinerun_status(
        self,
        run_name: str,
        namespace: str = DEFAULT_NAMESPACE,
    ) -> Dict[str, Any]:
        """Return overall reason/conditions for a specific PipelineRun."""
        if not self.custom_api:
            return {"status": "error", "message": "K8s connection failed"}
        try:
            run = self.custom_api.get_namespaced_custom_object(
                group="tekton.dev", version="v1", namespace=namespace,
                plural="pipelineruns", name=run_name,
            )
        except Exception as e:
            logger.error(f"PipelineRun status error: {e}")
            return {"status": "error", "message": str(e), "runName": run_name}

        status_block = run.get("status", {}) or {}
        conditions = status_block.get("conditions") or [{}]
        cond = conditions[0]
        overall_reason = cond.get("reason", "Running")
        succeeded = cond.get("status") == "True" and overall_reason == "Succeeded"

        tasks = []
        for ref in status_block.get("childReferences", []) or []:
            tasks.append({
                "name": ref.get("pipelineTaskName", "Unknown"),
                "status": "Succeeded" if succeeded else overall_reason,
            })

        return {
            "status": "success",
            "runName": run_name,
            "namespace": namespace,
            "overallStatus": overall_reason,
            "succeeded": succeeded,
            "completionTime": status_block.get("completionTime"),
            "startTime": status_block.get("startTime"),
            "tasks": tasks,
        }

    def get_replacement_endpoint(
        self,
        deploy_name: str,
        namespace: str = DEFAULT_NAMESPACE,
        service_name: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Return readiness + Service NodePort/clusterIP for replacement VNF."""
        if not (self.apps_api and self.core_api):
            return {"status": "error", "message": "K8s connection failed"}

        ready = 0
        desired = 0
        try:
            dep = self.apps_api.read_namespaced_deployment(deploy_name, namespace)
            ready = int(dep.status.ready_replicas or 0)
            desired = int(dep.spec.replicas or 1)
        except Exception as e:
            return {"status": "error", "message": f"deployment not found: {e}"}

        svc_name = service_name or f"{deploy_name}-svc"
        ports: List[Dict[str, Any]] = []
        cluster_ip = None
        svc_type = None
        try:
            svc = self.core_api.read_namespaced_service(svc_name, namespace)
            cluster_ip = svc.spec.cluster_ip
            svc_type = svc.spec.type
            for p in svc.spec.ports or []:
                ports.append({
                    "name": p.name,
                    "port": p.port,
                    "targetPort": getattr(p, "target_port", None),
                    "nodePort": getattr(p, "node_port", None),
                    "protocol": p.protocol,
                })
        except Exception as e:
            logger.warning(f"Service lookup failed for {svc_name}: {e}")

        return {
            "status": "success",
            "deployName": deploy_name,
            "serviceName": svc_name,
            "namespace": namespace,
            "ready": ready,
            "desired": desired,
            "isReady": ready >= desired and ready > 0,
            "serviceType": svc_type,
            "clusterIP": cluster_ip,
            "ports": ports,
        }

    def break_old_vnf(
        self,
        old_deploy_name: str,
        namespace: str = DEFAULT_NAMESPACE,
    ) -> Dict[str, Any]:
        """Deferred BREAK step. MUST be called explicitly AFTER steer success."""
        if not self.apps_api:
            return {"status": "error", "message": "K8s connection failed"}
        try:
            self.apps_api.delete_namespaced_deployment(
                name=old_deploy_name, namespace=namespace,
                body=client.V1DeleteOptions(propagation_policy="Foreground"),
            )
        except client.exceptions.ApiException as e:
            if e.status == 404:
                return {
                    "status": "success",
                    "phase": "BREAK",
                    "message": f"Old VNF '{old_deploy_name}' already absent.",
                }
            logger.error(f"Break Old VNF Error: {e}")
            return {"status": "error", "message": str(e)}
        # Best-effort: also delete the matching Service if it exists.
        svc_name = f"{old_deploy_name}-svc"
        try:
            self.core_api.delete_namespaced_service(name=svc_name, namespace=namespace)
        except client.exceptions.ApiException as e:
            if e.status != 404:
                logger.warning(f"Service '{svc_name}' delete skipped: {e}")
        return {
            "status": "success",
            "phase": "BREAK",
            "oldDeployName": old_deploy_name,
            "namespace": namespace,
            "message": f"Old VNF '{old_deploy_name}' deleted.",
        }
