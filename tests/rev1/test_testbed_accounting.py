import unittest
import tempfile
from pathlib import Path

from src.analytics.benchmark.benchmark_testbed.metrics import summarize_records
from src.analytics.benchmark.benchmark_testbed.models import RequestRecord
from src.analytics.benchmark.benchmark_testbed.run_concurrency import build_request_trace, summarize
from src.analytics.benchmark.benchmark_testbed.config import BenchmarkConfig
from src.analytics.benchmark.benchmark_testbed.runner import ScenarioRunner
from src.analytics.benchmark.benchmark_testbed.models import RequestSpec, ScenarioDefinition


def record(step, hour, admitted, deployed, latency):
    return RequestRecord(
        algorithm="hybrid_runtime",
        scenario="extended",
        step=step,
        accepted=admitted,
        status_code=200 if admitted else 409,
        decision_latency_ms=latency,
        service_latency_ms=0.0,
        service_type="Data",
        cpu_req=5.0,
        ram_req=2.0,
        msd_req=2,
        source_node=0,
        destination_node=1,
        alert_flag=False,
        admitted=admitted,
        safe_admitted=admitted,
        deployed=deployed,
        actuation_requested=deployed,
        deployment_status="ready" if deployed else "not_requested",
        elapsed_s=hour * 3600.0 + step,
        hour_index=hour,
        timestamp_utc="2026-11-16T00:00:00+00:00",
    )


class TestbedAccountingTests(unittest.TestCase):
    def test_hourly_summaries_separate_admission_deployment_and_latency(self):
        rows = [record(0, 0, True, True, 10.0), record(1, 0, False, False, 20.0), record(2, 1, True, False, 30.0)]
        summary = summarize_records(
            algorithm="hybrid_runtime",
            scenario="extended",
            title="extended",
            records=rows,
            msd_drop_delta=0,
            final_active_vnfs=1,
            wall_clock_s=3601.0,
        )
        self.assertEqual(summary.admitted, 2)
        self.assertEqual(summary.deployed, 1)
        self.assertEqual(summary.completed_ops_per_s, 3 / 3601.0)
        self.assertEqual(len(summary.hourly_summaries), 2)
        self.assertEqual(summary.hourly_summaries[0]["generated_requests"], 2)
        self.assertEqual(summary.hourly_summaries[0]["deployed"], 1)
        self.assertEqual(summary.hourly_summaries[1]["decision_p99_ms"], 30.0)

    def test_concurrency_trace_and_summary_are_reproducible_and_use_wall_time(self):
        trace_a = build_request_trace(10, 7)
        trace_b = build_request_trace(10, 7)
        self.assertEqual([item.to_payload() for item in trace_a], [item.to_payload() for item in trace_b])
        rows = [
            {"admitted": True, "http_latency_ms": 10.0, "client_dispatch_overhead_ms": 1.0},
            {"admitted": False, "http_latency_ms": 30.0, "client_dispatch_overhead_ms": 2.0},
        ]
        summary = summarize(rows, concurrency=2, wall_s=4.0)
        self.assertEqual(summary["completed_ops_per_s"], 0.5)
        self.assertEqual(summary["http_latency_p50_ms"], 10.0)
        self.assertEqual(summary["rejected"], 1)

    def test_live_runner_writes_request_timestamps_and_hourly_file(self):
        class FakeClient:
            def reset(self): return 200, {}, 0.0
            def set_alert(self, alert): return 200, {}, 0.0
            def msd_drops(self): return 200, {'s1': 0}, 0.0
            def orchestrate(self, payload):
                return 409, {"detail": {"reason_key": "msd_violation", "message": "rejected"}}, 2.0
            def state(self): return 200, {"data": {"active_vnfs": []}}, 0.0

        scenario = ScenarioDefinition(
            "runner_smoke", "runner smoke", "fixed requests", 2,
            lambda step, total, rng: RequestSpec("Data", 5, 2, 2),
        )
        with tempfile.TemporaryDirectory() as directory:
            records, summary = ScenarioRunner(
                BenchmarkConfig(steps=2, output_dir=Path(directory)), FakeClient()
            ).run(scenario, Path(directory))
            self.assertEqual(len(records), 2)
            self.assertTrue(all(row.timestamp_utc and row.elapsed_s >= 0 for row in records))
            self.assertEqual(summary.admitted, 0)
            self.assertTrue((Path(directory) / "runner_smoke_hourly_summary.csv").exists())


if __name__ == "__main__":
    unittest.main()


def test_latest_pipeline_success_cannot_count_as_completed_migration():
    row = record(0, 0, True, True, 10)
    row.latest_pipeline_status = 'Succeeded'
    summary = summarize_records(algorithm='hybrid_runtime', scenario='extended', title='test',
        records=[row], msd_drop_delta=0, final_active_vnfs=1, wall_clock_s=1)
    assert summary.successful_migration_pipelines == 0


def test_new_deployment_is_not_a_migration_trigger_and_completed_migration_is_counted():
    deployment = record(0, 0, True, True, 10)
    deployment.migration_status = 'deploying'
    migration = record(1, 0, True, True, 10)
    migration.migration_status = 'triggered'
    migration.migration_completed = True
    migration.migration_operation_id = 'operation'
    summary = summarize_records(algorithm='hybrid_runtime', scenario='extended', title='test',
        records=[deployment, migration], msd_drop_delta=0, final_active_vnfs=1, wall_clock_s=1)
    assert summary.migration_triggers == 1
    assert summary.completed_migrations == 1
