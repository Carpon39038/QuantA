#!/usr/bin/env python3

from __future__ import annotations

import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile

import duckdb


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))


from backend.app.app_wiring.settings import load_settings
from backend.app.domains.market_data.repo import load_system_health
from backend.app.shared.telemetry.alerts import load_recent_alerts


def main() -> int:
    base_settings = load_settings()
    _validate_provider_env(base_settings.source_provider)

    runtime_owner = _build_runtime_owner()
    runtime_dir = runtime_owner["runtime_dir"]
    env = _build_canary_env(runtime_dir=runtime_dir, base_env=os.environ.copy())
    iterations = int(env.get("QUANTA_PIPELINE_CANARY_ITERATIONS", "8"))

    try:
        for command in _bootstrap_commands():
            _run_checked(command, env)

        scheduler_completed = _run_checked(
            [
                "python3",
                "-m",
                "backend.app.domains.tasking.scheduler",
                "--daemon",
                "--auto-pipeline",
                "--iterations",
                str(iterations),
                "--stream-ticks",
                "--stop-on-error",
            ],
            env,
        )
        scheduler_events = _json_events_from_stdout(scheduler_completed.stdout)

        previous_env = os.environ.copy()
        try:
            os.environ.update(env)
            settings = load_settings()
            health_payload = load_system_health(settings)
            alerts = load_recent_alerts(settings, limit=50)
        finally:
            os.environ.clear()
            os.environ.update(previous_env)

        summary = _load_canary_summary(
            runtime_dir=runtime_dir,
            source_provider=env["QUANTA_SOURCE_PROVIDER"],
            source_universe=env.get("QUANTA_SOURCE_UNIVERSE", ""),
            scheduler_events=scheduler_events,
            health_payload=health_payload,
            alerts=alerts,
            keep_runtime=runtime_owner["keep_runtime"],
        )
        _assert_canary_health(summary)
        print(json.dumps(summary, ensure_ascii=False, indent=2))
        return 0
    finally:
        cleanup = runtime_owner.get("cleanup")
        if callable(cleanup):
            cleanup()


def _validate_provider_env(source_provider: str) -> None:
    if source_provider == "fixture_json":
        return
    if source_provider == "tushare" and os.environ.get("QUANTA_TUSHARE_TOKEN"):
        return
    raise ValueError(
        "pipeline_daemon_canary requires QUANTA_TUSHARE_TOKEN when "
        f"QUANTA_SOURCE_PROVIDER={source_provider!r}"
    )


def _build_runtime_owner() -> dict[str, object]:
    requested_runtime_dir = os.environ.get("QUANTA_PIPELINE_CANARY_RUNTIME_DIR")
    if requested_runtime_dir:
        runtime_dir = Path(requested_runtime_dir).resolve()
        runtime_dir.mkdir(parents=True, exist_ok=True)
        return {
            "runtime_dir": runtime_dir,
            "keep_runtime": True,
            "cleanup": None,
        }

    if os.environ.get("QUANTA_PIPELINE_CANARY_KEEP_RUNTIME", "0") == "1":
        runtime_dir = Path(tempfile.mkdtemp(prefix="quanta-pipeline-canary-")).resolve()
        return {
            "runtime_dir": runtime_dir,
            "keep_runtime": True,
            "cleanup": None,
        }

    temp_dir = tempfile.TemporaryDirectory(prefix="quanta-pipeline-canary-")
    return {
        "runtime_dir": Path(temp_dir.name).resolve(),
        "keep_runtime": False,
        "cleanup": temp_dir.cleanup,
    }


def _build_canary_env(*, runtime_dir: Path, base_env: dict[str, str]) -> dict[str, str]:
    env = dict(base_env)
    source_provider = env.get("QUANTA_SOURCE_PROVIDER", "fixture_json")
    env.update(
        {
            "PYTHONUNBUFFERED": "1",
            "QUANTA_RUNTIME_DATA_DIR": str(runtime_dir),
            "QUANTA_DUCKDB_PATH": str(runtime_dir / "duckdb" / "quanta.duckdb"),
            "QUANTA_SCHEDULER_POLL_INTERVAL_SECONDS": env.get(
                "QUANTA_SCHEDULER_POLL_INTERVAL_SECONDS",
                "0",
            ),
            "QUANTA_TASK_RETRY_BACKOFF_SECONDS": env.get(
                "QUANTA_TASK_RETRY_BACKOFF_SECONDS",
                "0",
            ),
        }
    )
    env.setdefault("QUANTA_SOURCE_PROVIDER", source_provider)
    if source_provider == "tushare":
        env.setdefault("QUANTA_SOURCE_UNIVERSE", "core_research_12")
        env.setdefault("QUANTA_SOURCE_VALIDATION_PROVIDERS", "none")
        env.setdefault("QUANTA_DISCLOSURE_PROVIDER", "none")
    return env


def _bootstrap_commands() -> list[list[str]]:
    return [
        ["python3", "-m", "backend.app.domains.tasking.bootstrap"],
        ["python3", "-m", "backend.app.domains.market_data.bootstrap"],
        ["python3", "-m", "backend.app.domains.analysis.bootstrap"],
        ["python3", "-m", "backend.app.domains.screener.bootstrap"],
        ["python3", "-m", "backend.app.domains.backtest.bootstrap"],
    ]


def _run_checked(command: list[str], env: dict[str, str]) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        command,
        cwd=ROOT,
        env=env,
        check=True,
        capture_output=True,
        text=True,
    )


def _json_events_from_stdout(stdout: str) -> list[dict[str, object]]:
    events = []
    for line in stdout.splitlines():
        if not line.startswith("{"):
            continue
        event = json.loads(line)
        if event.get("event") == "scheduler_loop_finished":
            event = {
                "event": "scheduler_loop_finished",
                "iterations": event.get("iterations"),
            }
        events.append(event)
    return events


def _load_canary_summary(
    *,
    runtime_dir: Path,
    source_provider: str,
    source_universe: str,
    scheduler_events: list[dict[str, object]],
    health_payload: dict[str, object],
    alerts: list[dict[str, object]],
    keep_runtime: bool,
) -> dict[str, object]:
    duckdb_path = runtime_dir / "duckdb" / "quanta.duckdb"
    connection = duckdb.connect(str(duckdb_path), read_only=True)
    try:
        latest_snapshot = connection.execute(
            """
            SELECT snapshot_id, raw_snapshot_id, biz_date, status
            FROM artifact_publish
            ORDER BY publish_seq DESC
            LIMIT 1
            """
        ).fetchone()
        task_rows = connection.execute(
            """
            SELECT task_id, task_name, biz_date, snapshot_id, status, error_message
            FROM task_run_log
            ORDER BY started_at DESC, task_id DESC
            LIMIT 20
            """
        ).fetchall()
    finally:
        connection.close()

    tick_events = [
        event for event in scheduler_events if event.get("event") == "scheduler_tick"
    ]
    return {
        "ok": True,
        "source_provider": source_provider,
        "source_universe": source_universe,
        "runtime_dir": str(runtime_dir) if keep_runtime else None,
        "scheduler_tick_count": len(tick_events),
        "scheduler_service_processed_count": sum(
            int(event.get("service_worker", {}).get("processed", 0))
            for event in tick_events
            if isinstance(event.get("service_worker"), dict)
        ),
        "scheduler_backtest_processed_count": sum(
            int(event.get("backtest_worker", {}).get("processed", 0))
            for event in tick_events
            if isinstance(event.get("backtest_worker"), dict)
        ),
        "scheduler_events": scheduler_events,
        "latest_snapshot": {
            "snapshot_id": str(latest_snapshot[0]),
            "raw_snapshot_id": str(latest_snapshot[1]),
            "biz_date": str(latest_snapshot[2]),
            "status": str(latest_snapshot[3]),
        } if latest_snapshot is not None else None,
        "health": health_payload,
        "alerts": alerts,
        "task_runs": [
            {
                "task_id": str(task_id),
                "task_name": str(task_name),
                "biz_date": str(biz_date),
                "snapshot_id": str(snapshot_id),
                "status": str(status),
                "error_message": str(error_message) if error_message is not None else None,
            }
            for task_id, task_name, biz_date, snapshot_id, status, error_message in task_rows
        ],
    }


def _assert_canary_health(summary: dict[str, object]) -> None:
    latest_snapshot = summary["latest_snapshot"]
    if not isinstance(latest_snapshot, dict) or latest_snapshot.get("status") != "READY":
        raise AssertionError("pipeline canary did not produce a READY latest snapshot")

    health = summary["health"]
    if not isinstance(health, dict) or health.get("status") != "ok":
        raise AssertionError("pipeline canary health payload is not ok")

    scheduler_events = summary["scheduler_events"]
    if not isinstance(scheduler_events, list) or not scheduler_events:
        raise AssertionError("pipeline canary produced no scheduler stream events")

    task_runs = summary["task_runs"]
    if not isinstance(task_runs, list) or not task_runs:
        raise AssertionError("pipeline canary produced no task_run_log rows")
    if any(
        isinstance(item, dict) and item.get("status") not in {"SUCCESS", "PENDING"}
        for item in task_runs
    ):
        raise AssertionError("pipeline canary has non-success task_run_log rows")

    alerts = summary["alerts"]
    if any(isinstance(item, dict) and item.get("severity") == "error" for item in alerts):
        raise AssertionError("pipeline canary emitted error alerts")


if __name__ == "__main__":
    raise SystemExit(main())
