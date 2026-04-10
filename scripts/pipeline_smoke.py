#!/usr/bin/env python3

from __future__ import annotations

import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))


from backend.app.app_wiring.settings import load_settings
from backend.app.domains.tasking.queue import move_service_queue_item
from backend.app.shared.providers.duckdb import connect_duckdb


def run_checked(command: list[str], env: dict[str, str]) -> str:
    print(f"[pipeline-smoke] run: {' '.join(command)}")
    completed = subprocess.run(
        command,
        cwd=ROOT,
        env=env,
        check=True,
        capture_output=True,
        text=True,
    )
    return completed.stdout


def build_env(runtime_dir: Path, *, fail_first_n: int = 0) -> dict[str, str]:
    env = os.environ.copy()
    env.update(
        {
            "PYTHONUNBUFFERED": "1",
            "QUANTA_RUNTIME_DATA_DIR": str(runtime_dir),
            "QUANTA_DUCKDB_PATH": str(runtime_dir / "duckdb" / "quanta.duckdb"),
            "QUANTA_SOURCE_PROVIDER": "fixture_json",
            "QUANTA_SOURCE_FIXTURE_DIR": str(
                ROOT / "backend/app/fixtures/source_snapshots"
            ),
            "QUANTA_TASK_RETRY_BACKOFF_SECONDS": "0",
            "QUANTA_TASK_MAX_RETRIES": "2",
            "QUANTA_SOURCE_FAIL_FIRST_N": str(fail_first_n),
        }
    )
    return env


def bootstrap_runtime(env: dict[str, str]) -> None:
    run_checked(["python3", "-m", "backend.app.domains.tasking.bootstrap"], env)
    run_checked(["python3", "-m", "backend.app.domains.market_data.bootstrap"], env)
    run_checked(["python3", "-m", "backend.app.domains.analysis.bootstrap"], env)
    run_checked(["python3", "-m", "backend.app.domains.screener.bootstrap"], env)
    run_checked(["python3", "-m", "backend.app.domains.backtest.bootstrap"], env)


def verify_scheduler_success_case() -> None:
    with tempfile.TemporaryDirectory(prefix="quanta-pipeline-success-") as temp_dir:
        runtime_dir = Path(temp_dir)
        env = build_env(runtime_dir)
        bootstrap_runtime(env)

        scheduler_output = run_checked(
            ["python3", "-m", "backend.app.domains.tasking.scheduler", "--max-ticks", "6"],
            env,
        )
        scheduler_summary = json.loads(scheduler_output)
        assert scheduler_summary["settled"] is True

        os.environ.update(
            {
                "QUANTA_RUNTIME_DATA_DIR": str(runtime_dir),
                "QUANTA_DUCKDB_PATH": str(runtime_dir / "duckdb" / "quanta.duckdb"),
            }
        )
        settings = load_settings()
        connection = connect_duckdb(settings.duckdb_path, read_only=True)
        try:
            latest_snapshot = connection.execute(
                """
                SELECT snapshot_id, raw_snapshot_id, biz_date, status
                FROM artifact_publish
                ORDER BY publish_seq DESC
                LIMIT 1
                """
            ).fetchone()
            assert latest_snapshot is not None
            assert str(latest_snapshot[2]) == "2026-03-31"
            assert str(latest_snapshot[3]) == "READY"
        finally:
            connection.close()


def verify_retry_case() -> None:
    with tempfile.TemporaryDirectory(prefix="quanta-pipeline-retry-") as temp_dir:
        runtime_dir = Path(temp_dir)
        env = build_env(runtime_dir, fail_first_n=1)
        bootstrap_runtime(env)

        scheduler_output = run_checked(
            ["python3", "-m", "backend.app.domains.tasking.scheduler", "--max-ticks", "8"],
            env,
        )
        scheduler_summary = json.loads(scheduler_output)
        assert scheduler_summary["settled"] is True
        assert any(
            tick["service_worker"]["retried"] >= 1 for tick in scheduler_summary["ticks"]
        )

        alerts_path = runtime_dir / "logs" / "alerts.jsonl"
        if alerts_path.exists():
            alerts_content = alerts_path.read_text(encoding="utf-8").strip()
            assert alerts_content == ""


def verify_resident_scheduler_stream_case() -> None:
    with tempfile.TemporaryDirectory(prefix="quanta-pipeline-resident-") as temp_dir:
        runtime_dir = Path(temp_dir)
        env = build_env(runtime_dir)
        env["QUANTA_SCHEDULER_POLL_INTERVAL_SECONDS"] = "0"
        bootstrap_runtime(env)

        scheduler_output = run_checked(
            [
                "python3",
                "-m",
                "backend.app.domains.tasking.scheduler",
                "--daemon",
                "--auto-pipeline",
                "--iterations",
                "3",
                "--stream-ticks",
                "--stream-log-path",
                str(runtime_dir / "logs" / "pipeline-daemon.jsonl"),
                "--stop-on-error",
            ],
            env,
        )
        stream_events = [
            json.loads(line)
            for line in scheduler_output.splitlines()
            if line.startswith("{")
        ]
        tick_started_events = [
            event for event in stream_events if event["event"] == "scheduler_tick_started"
        ]
        tick_events = [
            event for event in stream_events if event["event"] == "scheduler_tick"
        ]
        assert [event["event"] for event in tick_events] == [
            "scheduler_tick",
            "scheduler_tick",
            "scheduler_tick",
        ]
        assert [event["tick_no"] for event in tick_started_events] == [1, 2, 3]
        assert stream_events[-1]["event"] == "scheduler_loop_finished"
        assert stream_events[-1]["iterations"] == 3
        assert any(
            event["service_worker"]["processed"] >= 1
            for event in tick_events
        )
        log_events = [
            json.loads(line)
            for line in (runtime_dir / "logs" / "pipeline-daemon.jsonl").read_text(
                encoding="utf-8"
            ).splitlines()
        ]
        assert log_events == stream_events


def verify_orphaned_processing_recovery_case() -> None:
    with tempfile.TemporaryDirectory(prefix="quanta-pipeline-recover-") as temp_dir:
        runtime_dir = Path(temp_dir)
        env = build_env(runtime_dir)
        env["QUANTA_SCHEDULER_POLL_INTERVAL_SECONDS"] = "0"
        bootstrap_runtime(env)

        previous_env = os.environ.copy()
        try:
            os.environ.update(
                {
                    "QUANTA_RUNTIME_DATA_DIR": str(runtime_dir),
                    "QUANTA_DUCKDB_PATH": str(runtime_dir / "duckdb" / "quanta.duckdb"),
                }
            )
            settings = load_settings()
            enqueue_summary = json.loads(
                run_checked(
                    [
                        "python3",
                        "-m",
                        "backend.app.domains.tasking.scheduler",
                        "--enqueue-only",
                    ],
                    env,
                )
            )
            enqueued_payload = enqueue_summary["enqueued"]
            move_service_queue_item(
                settings,
                path=Path(str(enqueued_payload["queue_path"])),
                target_state="processing",
            )
        finally:
            os.environ.clear()
            os.environ.update(previous_env)

        scheduler_output = run_checked(
            [
                "python3",
                "-m",
                "backend.app.domains.tasking.scheduler",
                "--daemon",
                "--auto-pipeline",
                "--iterations",
                "1",
                "--stream-ticks",
                "--stop-on-error",
            ],
            env,
        )
        stream_events = [
            json.loads(line)
            for line in scheduler_output.splitlines()
            if line.startswith("{")
        ]
        tick_event = next(event for event in stream_events if event["event"] == "scheduler_tick")
        assert tick_event["pipeline"]["reason"] == "service_queue_busy"
        assert tick_event["service_worker"]["processed"] == 1
        assert str(enqueued_payload["task_id"]) in tick_event["service_worker"]["completed_ids"]

        alerts_path = runtime_dir / "logs" / "alerts.jsonl"
        alerts = [
            json.loads(line)
            for line in alerts_path.read_text(encoding="utf-8").splitlines()
            if line.strip()
        ]
        assert any(
            alert["alert_type"] == "service_queue_processing_recovered"
            for alert in alerts
        )


def main() -> int:
    verify_scheduler_success_case()
    verify_retry_case()
    verify_resident_scheduler_stream_case()
    verify_orphaned_processing_recovery_case()
    print("[pipeline-smoke] scheduler and retry paths are healthy")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
