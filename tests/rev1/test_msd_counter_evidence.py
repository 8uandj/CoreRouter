from unittest.mock import Mock
import pytest
from infrastructure.sdn.controller import ThriftController
from src.analytics.benchmark.benchmark_testbed.metrics import total_msd_drops
from src.analytics.benchmark.benchmark_testbed.config import BenchmarkConfig
from src.analytics.benchmark.benchmark_testbed.runner import ScenarioRunner


@pytest.mark.parametrize('reply', [(1, 'unreachable'), (0, 'invalid counter'), (0, 'error packets: 0')])
def test_missing_switch_counter_is_not_zero_drops(reply):
    controller = ThriftController.__new__(ThriftController)
    controller._cli = Mock(return_value=reply)
    assert controller.read_counter('msd_violation_counter') is None


@pytest.mark.parametrize('snapshot', [{}, {'s1': None}, {'s1': -1}, {'s1': 'error'}, {'s1': True}])
def test_missing_or_malformed_counter_snapshot_cannot_make_zero_violation_evidence(snapshot):
    with pytest.raises(ValueError):
        total_msd_drops(snapshot)


def test_http_failure_does_not_make_zero_violation_evidence():
    client = Mock()
    client.msd_drops.return_value = (503, {}, 0)
    with pytest.raises(RuntimeError):
        ScenarioRunner(BenchmarkConfig(), client)._read_msd_drop_total()


def test_valid_zero_and_positive_counter_values_are_preserved():
    assert total_msd_drops({'s1': 0, 's2': 4}) == 4


@pytest.mark.parametrize('output', ['counter[0]= packets: 0, bytes: 0',
                                    'counter[0]= (bytes=128, packets=4)'])
def test_valid_switch_counter_output_is_measured(output):
    controller = ThriftController.__new__(ThriftController)
    controller._cli = Mock(return_value=(0, output))
    expected = 4 if 'packets=4' in output else 0
    assert controller.read_counter('counter') == expected


def test_final_counter_failure_preserves_raw_requests(tmp_path):
    from src.analytics.benchmark.benchmark_testbed.models import RequestSpec, ScenarioDefinition
    client = Mock()
    client.reset.return_value = (200, {}, 0)
    client.msd_drops.side_effect = [(200, {'s1': 0}, 0), (503, {}, 0)]
    client.orchestrate.return_value = (409, {'detail': {'reason_key': 'no_safe_action'}}, 1)
    scenario = ScenarioDefinition('counter_failure', 'test', 'test', 1,
        lambda step, count, rng: RequestSpec('Data', 1, 1, 2))
    with pytest.raises(RuntimeError, match='counter endpoint unavailable'):
        ScenarioRunner(BenchmarkConfig(steps=1), client).run(scenario, tmp_path)
    assert (tmp_path / 'counter_failure_records.csv').read_text().count('\n') == 2


@pytest.mark.parametrize('before,after', [({'s1': 5, 's2': 0}, {'s1': 0, 's2': 10}),
                                          ({'s1': 0, 's2': 0}, {'s1': 0})])
def test_counter_reset_or_switch_disappearance_cannot_be_hidden_by_aggregate(tmp_path, before, after):
    from src.analytics.benchmark.benchmark_testbed.models import RequestSpec, ScenarioDefinition
    client = Mock()
    client.reset.return_value = (200, {}, 0)
    client.msd_drops.side_effect = [(200, before, 0), (200, after, 0)]
    client.orchestrate.return_value = (409, {'detail': {'reason_key': 'no_safe_action'}}, 1)
    client.state.return_value = (200, {'data': {'active_vnfs': []}}, 0)
    scenario = ScenarioDefinition('counter_reset', 'test', 'test', 1,
        lambda step, count, rng: RequestSpec('Data', 1, 1, 2))
    with pytest.raises(RuntimeError, match='counter'):
        ScenarioRunner(BenchmarkConfig(steps=1), client).run(scenario, tmp_path)
    assert (tmp_path / 'counter_reset_records.csv').is_file()
