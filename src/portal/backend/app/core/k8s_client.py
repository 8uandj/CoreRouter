from kubernetes import client, config
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("3S-COM-K8s")

class K8sClient:
    def __init__(self):
        self.core_api = None
        self.apps_api = None
        self.custom_api = None
        self.connect()

    def connect(self):
        kubeconfig_paths = [
            None, # Default ~/.kube/config
            "/var/snap/microk8s/current/credentials/client.config"
        ]
        
        connected = False
        for path in kubeconfig_paths:
            try:
                if path:
                    config.load_kube_config(config_file=path)
                else:
                    config.load_kube_config()
                self.core_api = client.CoreV1Api()
                self.apps_api = client.AppsV1Api()
                self.custom_api = client.CustomObjectsApi()
                logger.info(f"✅ Connected to K8s via {'default config' if not path else path}")
                connected = True
                break
            except Exception as e:
                logger.warning(f"⚠️ Failed to connect to K8s using {'default config' if not path else path}: {e}")

        if not connected:
            try:
                config.load_incluster_config()
                self.core_api = client.CoreV1Api()
                self.apps_api = client.AppsV1Api()
                self.custom_api = client.CustomObjectsApi()
                logger.info("✅ Connected via In-Cluster Config")
            except Exception as e:
                logger.error(f"❌ Failed to connect to K8s (In-Cluster): {e}")

# Tạo Singleton instance để dùng chung toàn app
k8s = K8sClient()