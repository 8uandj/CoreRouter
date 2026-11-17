import pytest

from src.portal.backend.app.services.realization import (
    AdmittedRealization,
    validate_realization_payload,
)


def realization(**changes):
    values = {
        "request_id": "request-1",
        "operation_id": "operation-1",
        "topology_hash": "a" * 64,
        "profile_id": "profile-1",
        "sid_stack": ("2001:db8::1", "2001:db8::2"),
        "forwarding_sid": "2001:db8::2",
    }
    values.update(changes)
    return AdmittedRealization(**values)


def test_controller_payload_must_match_admitted_identity_and_sid_stack():
    admitted = realization()
    payload = {
        "request_id": admitted.request_id,
        "operation_id": admitted.operation_id,
        "topology_hash": admitted.topology_hash,
        "profile_id": admitted.profile_id,
        "new_rules": [
            {"type": "srv6_sid", "sid": "2001:db8::1"},
            {"type": "srv6_sid", "sid": "2001:db8::2"},
        ],
    }

    assert validate_realization_payload(admitted, payload) is None


@pytest.mark.parametrize(
    "change,payload_change",
    [
        ({}, {"operation_id": "other-operation"}),
        ({}, {"topology_hash": "b" * 64}),
        ({}, {"profile_id": "other-profile"}),
        ({}, {"new_rules": [{"type": "srv6_sid", "sid": "2001:db8::9"}]}),
    ],
)
def test_controller_payload_mismatch_is_rejected(change, payload_change):
    admitted = realization(**change)
    payload = {
        "request_id": admitted.request_id,
        "operation_id": admitted.operation_id,
        "topology_hash": admitted.topology_hash,
        "profile_id": admitted.profile_id,
        "new_rules": [{"type": "srv6_sid", "sid": admitted.forwarding_sid}],
    }
    payload.update(payload_change)

    with pytest.raises(ValueError, match="admitted realization"):
        validate_realization_payload(admitted, payload)


def test_unresolved_forwarding_realization_is_rejected():
    admitted = realization(forwarding_sid=None)
    with pytest.raises(ValueError, match="no supported forwarding realization"):
        validate_realization_payload(admitted, {})
