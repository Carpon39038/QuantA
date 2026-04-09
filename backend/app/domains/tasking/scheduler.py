from __future__ import annotations

import argparse
import json
import time

from backend.app.app_wiring.settings import AppSettings, load_settings
from backend.app.domains.market_data.repo import load_system_health
from backend.app.domains.market_data.sync import (
    latest_source_biz_date,
    load_latest_building_snapshot,
    resolve_source_backfill_window,
    resolve_source_backfill_window_to_start_date,
)
from backend.app.domains.tasking.bootstrap import ensure_runtime_directories
from backend.app.domains.tasking.queue import enqueue_service_task
from backend.app.domains.tasking.worker import (
    process_backtest_queue,
    process_service_queue,
)
from backend.app.shared.providers.duckdb import connect_duckdb


PIPELINE_TASK_ORDER = (
    "history_backfill",
    "daily_sync",
    "daily_screener",
    "daily_backtest",
)


def enqueue_next_pipeline_task(settings: AppSettings) -> dict[str, object]:
    ensure_runtime_directories(settings)
    if _has_open_service_queue_items(settings):
        return {"enqueued": None, "reason": "service_queue_busy"}

    building_snapshot = load_latest_building_snapshot(settings)
    if building_snapshot is not None:
        artifact_status = _load_artifact_status(settings, snapshot_id=str(building_snapshot["snapshot_id"]))
        if artifact_status.get("screener_run") != "READY":
            return {
                "enqueued": enqueue_service_task(
                    settings,
                    task_name="daily_screener",
                    snapshot_id=str(building_snapshot["snapshot_id"]),
                )
            }
        if artifact_status.get("backtest_run") != "READY":
            return {
                "enqueued": enqueue_service_task(
                    settings,
                    task_name="daily_backtest",
                    snapshot_id=str(building_snapshot["snapshot_id"]),
                )
            }
        return {"enqueued": None, "reason": "building_snapshot_waiting_publish"}

    source_biz_date = latest_source_biz_date(settings)
    latest_ready_snapshot = _load_latest_ready_snapshot_meta(settings)
    resolved_target_start_biz_date = _resolve_history_backfill_target_start_biz_date(
        settings,
        latest_ready_snapshot=latest_ready_snapshot,
    )
    if latest_ready_snapshot is not None and source_biz_date <= str(latest_ready_snapshot["biz_date"]):
        if _history_backfill_target_needs_extension(
            settings,
            latest_ready_snapshot=latest_ready_snapshot,
            source_biz_date=source_biz_date,
            resolved_target_start_biz_date=resolved_target_start_biz_date,
        ):
            return {
                "enqueued": enqueue_service_task(
                    settings,
                    task_name="history_backfill",
                    lookback_open_days=_history_backfill_target_open_days(
                        settings,
                        resolved_target_start_biz_date=resolved_target_start_biz_date,
                    ),
                    target_start_biz_date=resolved_target_start_biz_date,
                )
            }
        return {"enqueued": None, "reason": "source_not_newer"}

    if latest_ready_snapshot is not None:
        lookback_open_days = _history_backfill_target_open_days(
            settings,
            resolved_target_start_biz_date=resolved_target_start_biz_date,
        )
        if lookback_open_days is not None or resolved_target_start_biz_date is not None:
            return {
                "enqueued": enqueue_service_task(
                    settings,
                    task_name="history_backfill",
                    lookback_open_days=lookback_open_days,
                    target_start_biz_date=resolved_target_start_biz_date,
                )
            }
        return {"enqueued": enqueue_service_task(settings, task_name="history_backfill")}

    return {"enqueued": enqueue_service_task(settings, task_name="daily_sync")}


def run_scheduler_tick(
    settings: AppSettings,
    *,
    auto_pipeline: bool = True,
    service_limit: int | None = None,
    backtest_limit: int | None = None,
) -> dict[str, object]:
    ensure_runtime_directories(settings)
    pipeline_action = (
        enqueue_next_pipeline_task(settings) if auto_pipeline else {"enqueued": None, "reason": "auto_pipeline_disabled"}
    )
    service_summary = process_service_queue(settings, limit=service_limit)
    backtest_summary = process_backtest_queue(settings, limit=backtest_limit)
    return {
        "pipeline": pipeline_action,
        "service_worker": service_summary,
        "backtest_worker": backtest_summary,
        "settled": is_pipeline_settled(settings),
    }


def run_daily_pipeline(
    settings: AppSettings,
    *,
    max_ticks: int = 6,
) -> dict[str, object]:
    tick_summaries: list[dict[str, object]] = []
    for _ in range(max_ticks):
        tick_summary = run_scheduler_tick(
            settings,
            auto_pipeline=True,
            service_limit=1,
            backtest_limit=1,
        )
        tick_summaries.append(tick_summary)
        if is_pipeline_settled(settings):
            break

    return {
        "tick_count": len(tick_summaries),
        "ticks": tick_summaries,
        "settled": is_pipeline_settled(settings),
    }


def run_scheduler_loop(
    settings: AppSettings,
    *,
    auto_pipeline: bool,
    iterations: int | None,
) -> dict[str, object]:
    summaries: list[dict[str, object]] = []
    loop_count = 0
    while iterations is None or loop_count < iterations:
        tick_summary = run_scheduler_tick(settings, auto_pipeline=auto_pipeline)
        summaries.append(tick_summary)
        loop_count += 1
        if iterations is None:
            time.sleep(settings.scheduler_poll_interval_seconds)
        elif loop_count < iterations:
            time.sleep(settings.scheduler_poll_interval_seconds)

    return {
        "iterations": loop_count,
        "ticks": summaries,
    }


def is_pipeline_settled(settings: AppSettings) -> bool:
    if _has_open_service_queue_items(settings):
        return False
    if load_latest_building_snapshot(settings) is not None:
        return False

    latest_ready_snapshot = _load_latest_ready_snapshot_meta(settings)
    if latest_ready_snapshot is None:
        return False
    source_biz_date = latest_source_biz_date(settings)
    if source_biz_date > str(latest_ready_snapshot["biz_date"]):
        return False
    resolved_target_start_biz_date = _resolve_history_backfill_target_start_biz_date(
        settings,
        latest_ready_snapshot=latest_ready_snapshot,
    )
    if _history_backfill_target_needs_extension(
        settings,
        latest_ready_snapshot=latest_ready_snapshot,
        source_biz_date=source_biz_date,
        resolved_target_start_biz_date=resolved_target_start_biz_date,
    ):
        return False
    return True


def _has_open_service_queue_items(settings: AppSettings) -> bool:
    for state in ("pending", "processing"):
        queue_dir = settings.queue_dir / "service" / state
        if queue_dir.exists() and any(queue_dir.glob("*.json")):
            return True
    return False


def _load_latest_ready_snapshot_meta(settings: AppSettings) -> dict[str, object] | None:
    connection = connect_duckdb(settings.duckdb_path, read_only=True)
    try:
        row = connection.execute(
            """
            SELECT snapshot_id, biz_date, raw_snapshot_id
            FROM artifact_publish
            WHERE status = 'READY'
            ORDER BY publish_seq DESC
            LIMIT 1
            """
        ).fetchone()
        if row is None:
            return None
        snapshot_id, biz_date, raw_snapshot_id = row
        return {
            "snapshot_id": str(snapshot_id),
            "biz_date": str(biz_date),
            "raw_snapshot_id": str(raw_snapshot_id),
        }
    finally:
        connection.close()


def _load_artifact_status(settings: AppSettings, *, snapshot_id: str) -> dict[str, object]:
    connection = connect_duckdb(settings.duckdb_path, read_only=True)
    try:
        row = connection.execute(
            """
            SELECT artifact_status_json
            FROM artifact_publish
            WHERE snapshot_id = ?
            LIMIT 1
            """,
            [snapshot_id],
        ).fetchone()
        if row is None:
            raise LookupError(f"Unknown snapshot_id: {snapshot_id}")
        return dict(json.loads(row[0]))
    finally:
        connection.close()


def _history_backfill_target_needs_extension(
    settings: AppSettings,
    *,
    latest_ready_snapshot: dict[str, object],
    source_biz_date: str,
    resolved_target_start_biz_date: str | None = None,
) -> bool:
    target_open_days = settings.history_backfill_target_open_days
    configured_target_start_biz_date = settings.history_backfill_target_start_biz_date
    auto_target_mode = (
        configured_target_start_biz_date is not None
        and configured_target_start_biz_date.lower() == "auto"
    )
    if target_open_days <= 0 and configured_target_start_biz_date is None:
        return False

    coverage = _load_snapshot_history_coverage(
        settings,
        snapshot_id=str(latest_ready_snapshot["snapshot_id"]),
    )
    coverage_start = str(coverage["start_biz_date"]) if coverage["start_biz_date"] is not None else None
    effective_target_start_biz_date = resolved_target_start_biz_date
    if (
        effective_target_start_biz_date is None
        and configured_target_start_biz_date is not None
        and not auto_target_mode
    ):
        effective_target_start_biz_date = configured_target_start_biz_date
    if effective_target_start_biz_date is not None:
        target_window = resolve_source_backfill_window_to_start_date(
            settings,
            target_start_biz_date=effective_target_start_biz_date,
            end_biz_date=source_biz_date,
        )
        return coverage_start is None or coverage_start > str(target_window["start_biz_date"])

    if target_open_days > 0:
        target_window = resolve_source_backfill_window(
            settings,
            lookback_open_days=target_open_days,
            end_biz_date=source_biz_date,
        )
        return (
            coverage["open_day_count"] < target_open_days
            or coverage_start is None
            or coverage_start > str(target_window["start_biz_date"])
        )
    return False


def _history_backfill_target_open_days(
    settings: AppSettings,
    *,
    resolved_target_start_biz_date: str | None = None,
) -> int | None:
    configured_target_start_biz_date = settings.history_backfill_target_start_biz_date
    if (
        configured_target_start_biz_date is not None
        and (
            configured_target_start_biz_date.lower() != "auto"
            or resolved_target_start_biz_date is not None
        )
    ):
        return None
    return (
        settings.history_backfill_target_open_days
        if settings.history_backfill_target_open_days > 0
        else None
    )


def _resolve_history_backfill_target_start_biz_date(
    settings: AppSettings,
    *,
    latest_ready_snapshot: dict[str, object] | None,
) -> str | None:
    configured_target_start_biz_date = settings.history_backfill_target_start_biz_date
    if configured_target_start_biz_date is None:
        return None
    if configured_target_start_biz_date.lower() != "auto":
        return configured_target_start_biz_date
    if latest_ready_snapshot is None:
        return None
    try:
        health_payload = load_system_health(settings)
    except LookupError:
        return None
    history_coverage = health_payload.get("history_coverage", {})
    recommended_target_start_biz_date = history_coverage.get(
        "recommended_target_start_biz_date"
    )
    if recommended_target_start_biz_date in (None, ""):
        return None
    return str(recommended_target_start_biz_date)


def _load_snapshot_history_coverage(
    settings: AppSettings,
    *,
    snapshot_id: str,
) -> dict[str, object]:
    connection = connect_duckdb(settings.duckdb_path, read_only=True)
    try:
        row = connection.execute(
            """
            SELECT
              MIN(trade_date),
              MAX(trade_date),
              COUNT(DISTINCT trade_date)
            FROM price_series_daily
            WHERE snapshot_id = ?
              AND price_basis = 'raw'
            """,
            [snapshot_id],
        ).fetchone()
        min_trade_date, max_trade_date, open_day_count = row
        return {
            "start_biz_date": str(min_trade_date) if min_trade_date is not None else None,
            "end_biz_date": str(max_trade_date) if max_trade_date is not None else None,
            "open_day_count": int(open_day_count or 0),
        }
    finally:
        connection.close()


def main() -> int:
    parser = argparse.ArgumentParser(description="Run the QuantA scheduler tick/loop for daily orchestration.")
    parser.add_argument(
        "--enqueue-only",
        action="store_true",
        help="Only enqueue the next pipeline task if one is available.",
    )
    parser.add_argument(
        "--daemon",
        action="store_true",
        help="Run the scheduler as a resident polling loop.",
    )
    parser.add_argument(
        "--auto-pipeline",
        action="store_true",
        help="When used with --daemon, keep auto-driving the daily pipeline.",
    )
    parser.add_argument(
        "--iterations",
        type=int,
        default=None,
        help="Optional loop iteration limit for --daemon.",
    )
    parser.add_argument(
        "--max-ticks",
        type=int,
        default=6,
        help="Maximum ticks to use for the non-daemon daily pipeline run.",
    )
    args = parser.parse_args()

    settings = load_settings()
    if args.enqueue_only:
        summary = enqueue_next_pipeline_task(settings)
    elif args.daemon:
        summary = run_scheduler_loop(
            settings,
            auto_pipeline=args.auto_pipeline,
            iterations=args.iterations,
        )
    else:
        summary = run_daily_pipeline(settings, max_ticks=args.max_ticks)

    print(json.dumps(summary, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
