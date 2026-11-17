import tempfile
from pathlib import Path

from src.portal.backend.app.services.migration_journal import MigrationJournal
from src.portal.backend.app.services.realization import AdmittedRealization


def supported_realization():
    return AdmittedRealization(
        'request', 'operation', 'a' * 64, 'p4-path-candidate-v1',
        ('fc00:2::1', 'fc00:1::1'), 'fc00:2::1', (1, 2), 'b' * 64)


def test_records_survive_reopening_and_are_returned_as_copies():
    with tempfile.TemporaryDirectory() as directory:
        path = Path(directory) / 'migration.sqlite3'
        journal = MigrationJournal(path)
        journal.record('new', {'status': 'running', 'old_vnf': 'old'})
        journal.record('new', {'status': 'warning', 'data': {
            'recovery_state': 'STEERING_UNCERTAIN', 'steer_operation_id': 'operation'}})
        restored = MigrationJournal(path)
        row = restored.get('new')
        assert row['data']['steer_operation_id'] == 'operation'
        row['data']['steer_operation_id'] = 'changed'
        assert restored.get('new')['data']['steer_operation_id'] == 'operation'
        assert restored.get('missing') is None


def test_journal_failure_prevents_infrastructure_mutation():
    import asyncio
    from unittest.mock import Mock
    import pytest
    from src.portal.backend.app.services.orchestration_service import OrchestrationService
    journal = Mock()
    journal.start.side_effect = OSError('disk unavailable')
    orchestrator = Mock()
    service = OrchestrationService(orchestrator, None, '',
                                   state_manager=Mock(), migration_journal=journal)
    with pytest.raises(OSError, match='disk unavailable'):
        asyncio.run(service.make_before_break_sequence('old', 'new', 'vnf.yaml', 'hanoi-1', None,
                                                       admitted_realization=supported_realization()))
    orchestrator.trigger_migrate_single.assert_not_called()


def test_duplicate_replacement_does_not_repeat_infrastructure_mutation():
    import asyncio
    from unittest.mock import Mock, AsyncMock
    from src.portal.backend.app.services.orchestration_service import OrchestrationService
    journal = MigrationJournal()
    orchestrator = Mock()
    service = OrchestrationService(orchestrator, None, '', state_manager=Mock(), migration_journal=journal)
    service._execute_make_before_break = AsyncMock(return_value={
        'status': 'warning', 'data': {'recovery_state': 'STEERING_UNCERTAIN'}})
    original = asyncio.run(service.make_before_break_sequence('old', 'new', 'vnf.yaml', 'hanoi-1', None,
        admitted_realization=supported_realization()))
    second = asyncio.run(service.make_before_break_sequence('old', 'new', 'vnf.yaml', 'hanoi-1', None,
        admitted_realization=supported_realization()))
    assert service._execute_make_before_break.await_count == 1
    assert second['message'] == 'MIGRATION_ALREADY_EXISTS'
    assert journal.get('new') == original


def test_separate_workers_cannot_claim_same_replacement_twice():
    from concurrent.futures import ThreadPoolExecutor
    from threading import Barrier
    with tempfile.TemporaryDirectory() as directory:
        path = Path(directory) / 'migration.sqlite3'
        journals = [MigrationJournal(path), MigrationJournal(path)]
        barrier = Barrier(2)
        def start(journal):
            barrier.wait(timeout=2)
            return journal.start('new', {'status': 'running'})
        with ThreadPoolExecutor(max_workers=2) as pool:
            outcomes = list(pool.map(start, journals))
        assert sorted(outcomes) == [False, True]
        assert MigrationJournal(path).get('new') == {'status': 'running'}
