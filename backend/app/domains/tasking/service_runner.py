from __future__ import annotations

import json

from backend.app.domains.backtest.bootstrap import materialize_backtest_snapshot
from backend.app.domains.market_data.sync import (
    finalize_snapshot_publish,
    load_latest_building_snapshot,
    sync_market_data,
)
from backend.app.shared.providers.duckdb import connect_duckdb
from backend.app.app_wiring.settings import AppSettings
from backend.app.domains.screener.bootstrap import (
    materialize_screener_snapshot,
)
from backend.app.domains.tasking.bootstrap import ensure_runtime_directories


SUPPORTED_SERVICE_TASKS = {
    "daily_sync",
    "daily_screener",
    "daily_backtest",
}


def run_service_task(
    settings: AppSettings,
    *,
    task_name: str,
    snapshot_id: str | None = None,
) -> dict[str, object]:
    if task_name == "daily_sync":
        return run_daily_sync(settings)
    if task_name == "daily_screener":
        return run_daily_screener(settings, snapshot_id=snapshot_id)
    if task_name == "daily_backtest":
        return run_daily_backtest(settings, snapshot_id=snapshot_id)
    raise ValueError(f"Unsupported service task: {task_name}")


def run_daily_sync(settings: AppSettings) -> dict[str, object]:
    sync_summary = sync_market_data(settings)
    return {
        "runtime": ensure_runtime_directories(settings),
        "snapshot_id": str(sync_summary["snapshot_id"]),
        "raw_snapshot_id": str(sync_summary["raw_snapshot_id"]),
        "biz_date": str(sync_summary["biz_date"]),
        "sync": sync_summary,
    }


def run_daily_screener(
    settings: AppSettings,
    *,
    snapshot_id: str | None = None,
) -> dict[str, object]:
    target_snapshot = _resolve_pipeline_snapshot(settings, snapshot_id=snapshot_id)
    connection = connect_duckdb(settings.duckdb_path)
    try:
        screener_summary = materialize_screener_snapshot(
            connection,
            snapshot_id=str(target_snapshot["snapshot_id"]),
            raw_snapshot_id=str(target_snapshot["raw_snapshot_id"]),
            biz_date=str(target_snapshot["biz_date"]),
            price_basis=str(target_snapshot["price_basis"]),
            published_at=str(target_snapshot["published_at"]),
        )
        _update_snapshot_artifact_state(
            connection,
            snapshot_id=str(target_snapshot["snapshot_id"]),
            updates={
                "screener_run": "READY",
                "screener_result": "READY",
            },
        )
    finally:
        connection.close()

    return {
        "runtime": ensure_runtime_directories(settings),
        "snapshot_id": str(target_snapshot["snapshot_id"]),
        "raw_snapshot_id": str(target_snapshot["raw_snapshot_id"]),
        "screener": screener_summary,
    }


def run_daily_backtest(
    settings: AppSettings,
    *,
    snapshot_id: str | None = None,
) -> dict[str, object]:
    target_snapshot = _resolve_pipeline_snapshot(settings, snapshot_id=snapshot_id)
    connection = connect_duckdb(settings.duckdb_path)
    try:
        backtest_summary = materialize_backtest_snapshot(
            connection,
            snapshot_id=str(target_snapshot["snapshot_id"]),
            raw_snapshot_id=str(target_snapshot["raw_snapshot_id"]),
            biz_date=str(target_snapshot["biz_date"]),
            price_basis=str(target_snapshot["price_basis"]),
            requested_at=str(target_snapshot["published_at"]),
            created_from="daily_pipeline_service",
        )
        if backtest_summary is None:
            raise RuntimeError(
                f"Backtest materialization failed for snapshot_id={target_snapshot['snapshot_id']}"
            )
        _update_snapshot_artifact_state(
            connection,
            snapshot_id=str(target_snapshot["snapshot_id"]),
            updates={
                "backtest_request": "READY",
                "backtest_run": "READY",
                "backtest_trade": "READY",
                "backtest_equity_curve": "READY",
            },
        )
    finally:
        connection.close()

    finalize_snapshot_publish(settings, snapshot_id=str(target_snapshot["snapshot_id"]))
    return {
        "runtime": ensure_runtime_directories(settings),
        "snapshot_id": str(target_snapshot["snapshot_id"]),
        "raw_snapshot_id": str(target_snapshot["raw_snapshot_id"]),
        "backtest": backtest_summary,
        "status": "READY",
    }


def _resolve_pipeline_snapshot(
    settings: AppSettings,
    *,
    snapshot_id: str | None,
) -> dict[str, object]:
    if snapshot_id is not None:
        connection = connect_duckdb(settings.duckdb_path, read_only=True)
        try:
            row = connection.execute(
                """
                SELECT snapshot_id, raw_snapshot_id, biz_date, price_basis, published_at
                FROM artifact_publish
                WHERE snapshot_id = ?
                LIMIT 1
                """,
                [snapshot_id],
            ).fetchone()
            if row is None:
                raise LookupError(f"Unknown snapshot_id: {snapshot_id}")
            resolved_snapshot_id, raw_snapshot_id, biz_date, price_basis, published_at = row
            return {
                "snapshot_id": str(resolved_snapshot_id),
                "raw_snapshot_id": str(raw_snapshot_id),
                "biz_date": str(biz_date),
                "price_basis": str(price_basis),
                "published_at": str(published_at),
            }
        finally:
            connection.close()

    building_snapshot = load_latest_building_snapshot(settings)
    if building_snapshot is not None:
        return building_snapshot

    raise LookupError("No BUILDING snapshot available for pipeline task")


def _update_snapshot_artifact_state(
    connection,
    *,
    snapshot_id: str,
    updates: dict[str, str],
) -> None:
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
    artifact_status = dict(json.loads(row[0]))
    artifact_status.update(updates)
    connection.execute(
        """
        UPDATE artifact_publish
        SET artifact_status_json = ?
        WHERE snapshot_id = ?
        """,
        [json.dumps(artifact_status, ensure_ascii=False), snapshot_id],
    )
