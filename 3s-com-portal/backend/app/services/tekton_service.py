import uuid
from app.core.k8s_client import k8s, logger
from app.models.schemas import DeployRequest

def trigger_deploy(request: DeployRequest):
    template_file = "vnf-frr.yaml"
    if request.type == "firewall": template_file = "vnf-firewall.yaml"
    elif request.type == "idps": template_file = "vnf-idps.yaml"

    run_name = f"deploy-{request.type}-{uuid.uuid4().hex[:6]}"
    
    pipeline_run = {
        "apiVersion": "tekton.dev/v1",
        "kind": "PipelineRun",
        "metadata": {"name": run_name},
        "spec": {
            "pipelineRef": {"name": "vnf-lcm-wide"}, 
            "taskRunTemplate": {"serviceAccountName": "tekton-admin"}, # Quan trọng
            "params": [
                {"name": "ns", "value": "vnf"},
                {"name": "deployName", "value": request.name},
                {"name": "fileName", "value": template_file},
                {"name": "labelSelector", "value": f"app={request.name}"}
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
        k8s.custom_api.create_namespaced_custom_object(
            group="tekton.dev", version="v1", namespace="tekton-pipelines",
            plural="pipelineruns", body=pipeline_run
        )
        logger.info(f"✅ Deployed: {run_name}")
        return {
            "status": "success", "runName": run_name,
            "message": f"Successfully initialized {request.type.upper()} ({request.profile}) instance."
        }
    except Exception as e:
        logger.error(f"Deploy Error: {e}")
        return {"status": "error", "message": str(e)}

def get_pipeline_status():
    if not k8s.custom_api: return {}
    try:
        runs = k8s.custom_api.list_namespaced_custom_object(
            group="tekton.dev", version="v1", namespace="tekton-pipelines", plural="pipelineruns"
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