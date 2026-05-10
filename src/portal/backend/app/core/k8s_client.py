from kubernetes import client, config
import time
import logging
import urllib3

urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("3S-COM-K8s")

class K8sClient:
    def __init__(self):
        self.core_api = None
        self.apps_api = None
        self.custom_api = None
        self.connect()

    def connect(self):
        # MicroK8s kubeconfig được ưu tiên trước — tránh load nhầm cluster khác
        kubeconfig_paths = [
            "/var/snap/microk8s/current/credentials/client.config",  # MicroK8s
            None,  # Default ~/.kube/config — fallback
        ]

        connected = False
        for path in kubeconfig_paths:
            try:
                if path:
                    config.load_kube_config(config_file=path)
                else:
                    config.load_kube_config()
                # Tắt verify SSL cho self-signed cert của MicroK8s
                conf = client.Configuration.get_default_copy()
                conf.verify_ssl = False
                client.Configuration.set_default(conf)
                self.core_api = client.CoreV1Api()
                self.apps_api = client.AppsV1Api()
                self.custom_api = client.CustomObjectsApi()
                logger.info(f"✅ Connected to K8s via {'default config' if not path else path}")
                connected = True
                break
            except Exception as e:
                logger.warning(f"⚠️ Failed to connect via {'default' if not path else path}: {e}")

        if not connected:
            try:
                config.load_incluster_config()
                self.core_api = client.CoreV1Api()
                self.apps_api = client.AppsV1Api()
                self.custom_api = client.CustomObjectsApi()
                logger.info("✅ Connected via In-Cluster Config")
            except Exception as e:
                logger.error(f"❌ Failed to connect to K8s (In-Cluster): {e}")

    def wait_for_pod_ready(
        self,
        deploy_name: str,
        namespace: str = "core-router",
        timeout: int = 120,
        poll_interval: int = 3,
    ) -> bool:
        """
        Poll K8s Deployment cho đến khi readyReplicas >= 1.

        KIẾN TRÚC: Đây là điểm duy nhất được phép poll trạng thái Pod.
        SDN Controller (controller.py) KHÔNG được gọi kubectl.
        Backend gọi hàm này → xác nhận Ready → mới gọi POST /steer.

        Returns:
            True  nếu Pod Ready trong timeout
            False nếu timeout hoặc lỗi K8s API
        """
        if not self.apps_api:
            logger.error("[K8sClient] apps_api not initialized — cannot wait for pod")
            return False

        logger.info(f"[K8sClient] Waiting for {deploy_name} Ready (timeout={timeout}s)...")
        deadline = time.time() + timeout

        while time.time() < deadline:
            try:
                dep = self.apps_api.read_namespaced_deployment(deploy_name, namespace)
                ready = dep.status.ready_replicas or 0
                desired = dep.spec.replicas or 1
                if ready >= desired:
                    logger.info(f"[K8sClient] ✅ {deploy_name} Ready ({ready}/{desired})")
                    return True
                logger.debug(f"[K8sClient] {deploy_name}: {ready}/{desired} ready — waiting...")
            except Exception as e:
                logger.warning(f"[K8sClient] Poll error: {e}")
            time.sleep(poll_interval)

        logger.error(f"[K8sClient] ❌ Timeout: {deploy_name} not Ready after {timeout}s")
        return False


# Singleton instance dùng chung toàn app
k8s = K8sClient()