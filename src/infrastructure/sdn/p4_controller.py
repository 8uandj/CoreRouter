import subprocess
import logging
from src.core.interfaces.controller import IController

logger = logging.getLogger("P4Controller")

class P4Controller(IController):
    def __init__(self, switch_container_name="p4switch", thrift_port=9090):
        self.container_name = switch_container_name
        self.thrift_port = thrift_port

    def inject_sfc_rule(self, target_mac: str, srv6_sid: str, egress_port: int) -> bool:
        p4_rule = f"table_add sfc_routing push_sfc_label {target_mac} => {srv6_sid} {egress_port}"
        
        docker_cmd = (
            f"echo '{p4_rule}' | "
            f"docker exec -i {self.container_name} simple_switch_CLI --thrift-port {self.thrift_port}"
        )

        try:
            result = subprocess.run(
                docker_cmd, 
                shell=True, 
                capture_output=True, 
                text=True
            )
            
            if "Entry has been added" in result.stdout:
                logger.info(f"Successfully injected rule for MAC {target_mac}")
                return True
            else:
                logger.error(f"P4 Switch Error: {result.stdout}")
                return False

        except Exception as e:
            logger.error(f"System error during rule injection: {e}")
            return False

    def get_topology(self) -> dict:
        # Mocking topology for now as no discovery logic was present in old code
        return {
            "nodes": [
                {"id": 0, "type": "edge", "msd_limit": 3},
                {"id": 1, "type": "core", "msd_limit": 6},
                {"id": 2, "type": "edge", "msd_limit": 3},
                {"id": 3, "type": "edge", "msd_limit": 3},
                {"id": 4, "type": "edge", "msd_limit": 3},
            ],
            "latencies": [
                [ 0,  2,  5,  8, 10],
                [ 2,  0,  2,  5,  8],
                [ 5,  2,  0,  2,  5],
                [ 8,  5,  2,  0,  2],
                [10,  8,  5,  2,  0],
            ]
        }
    
