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
        try:
            config.load_kube_config()
            self.core_api = client.CoreV1Api()
            self.apps_api = client.AppsV1Api()
            self.custom_api = client.CustomObjectsApi()
            logger.info("✅ Connected to Kubernetes Cluster")
        except Exception as e:
            logger.error(f"❌ Failed to connect to K8s: {e}")
            try:
                config.load_incluster_config()
                self.core_api = client.CoreV1Api()
                self.apps_api = client.AppsV1Api()
                self.custom_api = client.CustomObjectsApi()
                logger.info("✅ Connected via In-Cluster Config")
            except:
                pass
        except Exception as e:
            logger.error(f"❌ Failed to connect to K8s: {e}")
            # Thử load in-cluster config nếu chạy trong pod (cho tương lai)
            try:
                config.load_incluster_config()
                self.core_api = client.CoreV1Api()
                self.custom_api = client.CustomObjectsApi()
                logger.info("✅ Connected via In-Cluster Config")
            except:
                pass

# Tạo Singleton instance để dùng chung toàn app
k8s = K8sClient()