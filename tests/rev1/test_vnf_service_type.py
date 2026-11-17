import unittest

from src.portal.backend.app.services.vnf_service_type import resolve_vnf_service


class VnfServiceTypeTests(unittest.TestCase):
    def test_voc_request_selects_vvoc_template_for_create_and_migration(self):
        self.assertEqual(resolve_vnf_service("voc"), ("voc", "vnf-voc.yaml"))

    def test_known_services_keep_their_manifest_mapping(self):
        self.assertEqual(resolve_vnf_service("attack"), ("firewall", "vnf-firewall.yaml"))
        self.assertEqual(resolve_vnf_service("Video"), ("router", "vnf-frr.yaml"))

    def test_unknown_service_uses_existing_router_fallback(self):
        self.assertEqual(resolve_vnf_service("Data"), ("router", "vnf-frr.yaml"))


if __name__ == "__main__":
    unittest.main()
