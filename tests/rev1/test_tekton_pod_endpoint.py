import unittest
from types import SimpleNamespace
from unittest.mock import Mock

from src.infrastructure.k8s.tekton_orchestrator import TektonOrchestrator


def ready_pod(pod_ip="10.1.189.200"):
    return SimpleNamespace(
        metadata=SimpleNamespace(name="vnf-voc-smoke-pod"),
        status=SimpleNamespace(
            phase="Running", pod_ip=pod_ip,
            conditions=[SimpleNamespace(type="Ready", status="True")],
        ),
        spec=SimpleNamespace(node_name="worker2"),
    )


class TektonPodEndpointTests(unittest.TestCase):
    def setUp(self):
        self.orchestrator = TektonOrchestrator.__new__(TektonOrchestrator)
        self.orchestrator.apps_api = Mock()
        self.orchestrator.core_api = Mock()
        self.orchestrator.apps_api.read_namespaced_deployment.return_value = SimpleNamespace(
            status=SimpleNamespace(ready_replicas=1),
            spec=SimpleNamespace(replicas=1),
        )
        self.orchestrator.core_api.read_namespaced_service.return_value = SimpleNamespace(
            spec=SimpleNamespace(cluster_ip="10.152.183.210", type="NodePort", ports=[]),
        )

    def test_ready_endpoint_includes_the_actual_ready_pod_ip_and_node(self):
        self.orchestrator.core_api.list_namespaced_pod.return_value = SimpleNamespace(
            items=[ready_pod()])

        result = self.orchestrator.get_replacement_endpoint("vnf-voc-smoke")

        self.assertTrue(result["isReady"])
        self.assertEqual(result["podIP"], "10.1.189.200")
        self.assertEqual(result["podName"], "vnf-voc-smoke-pod")
        self.assertEqual(result["nodeName"], "worker2")
        self.orchestrator.core_api.list_namespaced_pod.assert_called_once_with(
            "core-router", label_selector="app=vnf-voc-smoke")

    def test_deployment_ready_without_ready_pod_ip_is_not_forwardable(self):
        self.orchestrator.core_api.list_namespaced_pod.return_value = SimpleNamespace(
            items=[ready_pod(pod_ip=None)])

        result = self.orchestrator.get_replacement_endpoint("vnf-voc-smoke")

        self.assertFalse(result["isReady"])
        self.assertIsNone(result["podIP"])


if __name__ == "__main__":
    unittest.main()
