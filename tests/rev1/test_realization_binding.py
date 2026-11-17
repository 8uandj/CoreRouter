import unittest

from src.portal.backend.app.services.realization import (
    AdmittedRealization,
    validate_realization_payload,
)


def realization(**changes):
    values = {
        "request_id": "request-1",
        "operation_id": "operation-1",
        "topology_hash": "a" * 64,
        "profile_id": "p4-path-candidate-v1",
        "sid_stack": ("fc00:9::1", "fc00:6::1", "fc00:1::1"),
        "forwarding_sid": "fc00:9::1",
        "switch_path": (1, 6, 9),
        "p4_topology_hash": "b" * 64,
    }
    values.update(changes)
    return AdmittedRealization(**values)


def controller_payload(admitted):
    return {
        "request_id": admitted.request_id,
        "operation_id": admitted.operation_id,
        "topology_hash": admitted.topology_hash,
        "profile_id": admitted.profile_id,
        "p4_topology_hash": admitted.p4_topology_hash,
        "switch_path": list(admitted.switch_path),
        "sid_stack": list(admitted.sid_stack),
    }


class RealizationBindingTests(unittest.TestCase):
    def test_controller_payload_must_match_admitted_identity_and_full_path(self):
        admitted = realization()
        self.assertIsNone(validate_realization_payload(admitted, controller_payload(admitted)))

    def test_controller_payload_mismatch_is_rejected(self):
        admitted = realization()
        changes = [
            {"operation_id": "other-operation"},
            {"topology_hash": "c" * 64},
            {"profile_id": "other-profile"},
            {"p4_topology_hash": "d" * 64},
            {"switch_path": [1, 6, 8]},
            {"sid_stack": ["fc00:8::1"]},
        ]
        for change in changes:
            with self.subTest(change=change):
                payload = controller_payload(admitted)
                payload.update(change)
                with self.assertRaisesRegex(ValueError, "admitted realization"):
                    validate_realization_payload(admitted, payload)

    def test_unresolved_forwarding_realization_is_rejected(self):
        admitted = realization(forwarding_sid=None)
        with self.assertRaisesRegex(ValueError, "no supported forwarding realization"):
            validate_realization_payload(admitted, {})

    def test_supported_p4_path_requires_matching_terminal_and_topology_hash(self):
        with self.assertRaisesRegex(ValueError, "forwarding path is inconsistent"):
            realization(forwarding_sid="fc00:6::1")
        with self.assertRaisesRegex(ValueError, "live P4 topology hash"):
            realization(p4_topology_hash=None)


if __name__ == "__main__":
    unittest.main()
