from src.core.interfaces.orchestrator import IOrchestrator

class TopologyService:
    def __init__(self, orchestrator: IOrchestrator):
        self.orchestrator = orchestrator

    def get_topology(self):
        vfn_list = self.orchestrator.list_vnfs()
        nodes = []
        edges = []

        raw_nodes = []
        for vnf in vfn_list:
            name = vnf["id"]
            labels = vnf["labels"]
            
            raw_nodes.append({
                "id": name,
                "role": vnf["data"].get("role", "router"),
                "location": vnf["data"].get("location", "auto"),
                "ready": vnf["ready"],
                "desired": vnf["desired"],
                "status": vnf["data"].get("status", "Pending")
            })

        raw_nodes.sort(key=lambda x: x["id"])

        for n in raw_nodes:
            nodes.append({
                "id": n["id"],
                "type": "customNode",
                "data": {
                    "label": n["id"],
                    "role": n["role"],
                    "location": n["location"],
                    "status": n["status"],
                    "ready": f'{n["ready"]}/{n["desired"]}'
                },
                "position": {"x": 0, "y": 0},
                "draggable": True
            })

        fw_ids   = [n["id"] for n in nodes if n["data"]["role"] == "firewall"]
        idps_ids = [n["id"] for n in nodes if n["data"]["role"] == "idps"]

        for fw in fw_ids:
            for idps in idps_ids:
                edges.append({
                    "id": f"e-{fw}-{idps}", "source": fw, "target": idps,
                    "animated": True, "style": {"stroke": "#06b6d4", "strokeWidth": 2}
                })

        return {"nodes": nodes, "edges": edges}