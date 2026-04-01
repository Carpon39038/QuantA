from __future__ import annotations

from datetime import datetime, timedelta, timezone
import json
from pathlib import Path

from backend.app.app_wiring.settings import AppSettings
from backend.app.domains.backtest.bootstrap import (
    INITIAL_CASH,
    delete_backtest_materialization,
    upsert_backtest_request_row,
)
from backend.app.domains.tasking.bootstrap import ensure_runtime_directories
from backend.app.shared.providers.duckdb import connect_duckdb


CN_TZ = timezone(timedelta(hours=8))
QUEUE_TASK_NAME = "backtest"
QUEUE_STRATEGY_VERSION = "m5-queue-001"


def enqueue_backtest_request(
    settings: AppSettings,
    *,
    snapshot_id: str | None = None,
    top_n: int | None = None,
) -> dict[str, object]:
    ensure_runtime_directories(settings)

    requested_at = datetime.now(CN_TZ).isoformat(timespec="seconds")
    backtest_id = _generate_backtest_id()
    resolved_top_n = _validate_top_n(top_n)

    connection = connect_duckdb(settings.duckdb_path)
    try:
        published_snapshot = _resolve_published_snapshot(connection, snapshot_id=snapshot_id)
        payload = {
            "top_n": resolved_top_n,
            "initial_cash": INITIAL_CASH,
            "holding_mode": "window_hold",
            "created_from": "manual_queue_request",
        }
        upsert_backtest_request_row(
            connection,
            backtest_id=backtest_id,
            requested_at=requested_at,
            snapshot_id=str(published_snapshot["snapshot_id"]),
            raw_snapshot_id=str(published_snapshot["raw_snapshot_id"]),
            strategy_version=QUEUE_STRATEGY_VERSION,
            signal_price_basis=str(published_snapshot["price_basis"]),
            payload_json=payload,
            status="PENDING",
            retry_count=0,
            last_error=None,
        )
    finally:
        connection.close()

    queue_item = {
        "task_type": QUEUE_TASK_NAME,
        "backtest_id": backtest_id,
        "requested_at": requested_at,
        "snapshot_id": str(published_snapshot["snapshot_id"]),
        "raw_snapshot_id": str(published_snapshot["raw_snapshot_id"]),
        "biz_date": str(published_snapshot["biz_date"]),
        "signal_price_basis": str(published_snapshot["price_basis"]),
        "strategy_version": QUEUE_STRATEGY_VERSION,
        "payload": payload,
        "retry_count": 0,
        "max_retries": settings.task_max_retries,
        "next_attempt_at": requested_at,
        "last_error": None,
    }
    queue_path = write_backtest_queue_item(
        settings,
        backtest_id=backtest_id,
        queue_item=queue_item,
    )

    return {
        "backtest_id": backtest_id,
        "status": "PENDING",
        "requested_at": requested_at,
        "snapshot_id": str(published_snapshot["snapshot_id"]),
        "raw_snapshot_id": str(published_snapshot["raw_snapshot_id"]),
        "signal_price_basis": str(published_snapshot["price_basis"]),
        "payload": payload,
        "retry_count": 0,
        "queue_path": str(queue_path),
    }


def pending_backtest_queue_items(
    settings: AppSettings,
    *,
    limit: int | None = None,
) -> list[tuple[Path, dict[str, object]]]:
    pending_dir = _queue_state_dir(settings, "pending")
    pending_dir.mkdir(parents=True, exist_ok=True)
    paths = sorted(pending_dir.glob("*.json"))
    if limit is not None:
        paths = paths[:limit]
    now_value = datetime.now(CN_TZ)
    items: list[tuple[Path, dict[str, object]]] = []
    for path in paths:
        payload = json.loads(path.read_text(encoding="utf-8"))
        next_attempt_at = payload.get("next_attempt_at")
        if isinstance(next_attempt_at, str) and datetime.fromisoformat(next_attempt_at) > now_value:
            continue
        items.append((path, payload))
        if limit is not None and len(items) >= limit:
            break
    return items


def move_backtest_queue_item(
    settings: AppSettings,
    *,
    path: Path,
    target_state: str,
) -> Path:
    target_dir = _queue_state_dir(settings, target_state)
    target_dir.mkdir(parents=True, exist_ok=True)
    target_path = target_dir / path.name
    path.replace(target_path)
    return target_path


def write_backtest_queue_item(
    settings: AppSettings,
    *,
    backtest_id: str,
    queue_item: dict[str, object],
) -> Path:
    pending_dir = _queue_state_dir(settings, "pending")
    pending_dir.mkdir(parents=True, exist_ok=True)
    queue_path = pending_dir / f"{backtest_id}.json"
    queue_path.write_text(
        json.dumps(queue_item, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    return queue_path


def rewrite_backtest_queue_item(
    settings: AppSettings,
    *,
    path: Path,
    queue_item: dict[str, object],
) -> Path:
    path.write_text(
        json.dumps(queue_item, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    return path


def delete_backtest_request_artifacts(
    settings: AppSettings,
    *,
    backtest_id: str,
) -> None:
    for state in ("pending", "processing", "completed", "failed"):
        queue_path = _queue_state_dir(settings, state) / f"{backtest_id}.json"
        queue_path.unlink(missing_ok=True)

    connection = connect_duckdb(settings.duckdb_path)
    try:
        delete_backtest_materialization(connection, backtest_id=backtest_id)
        connection.execute("DELETE FROM backtest_request WHERE backtest_id = ?", [backtest_id])
        connection.execute(
            "DELETE FROM task_run_log WHERE task_id = ?",
            [f"{backtest_id}:worker"],
        )
    finally:
        connection.close()


def _queue_state_dir(settings: AppSettings, state: str) -> Path:
    return settings.queue_dir / QUEUE_TASK_NAME / state


def _generate_backtest_id() -> str:
    timestamp = datetime.now(CN_TZ).strftime("%Y%m%dT%H%M%S%f")
    return f"backtest_request_{timestamp}"


def _validate_top_n(value: int | None) -> int:
    if value is None:
        return 2
    resolved = int(value)
    if resolved < 1 or resolved > 10:
        raise ValueError("top_n must be between 1 and 10")
    return resolved


def _resolve_published_snapshot(connection, *, snapshot_id: str | None) -> dict[str, object]:
    if snapshot_id is not None:
        row = connection.execute(
            """
            SELECT
              snapshot_id,
              raw_snapshot_id,
              biz_date,
              price_basis
            FROM artifact_publish
            WHERE snapshot_id = ?
              AND status = 'READY'
            LIMIT 1
            """,
            [snapshot_id],
        ).fetchone()
    else:
        row = connection.execute(
            """
            SELECT
              snapshot_id,
              raw_snapshot_id,
              biz_date,
              price_basis
            FROM artifact_publish
            WHERE status = 'READY'
            ORDER BY publish_seq DESC
            LIMIT 1
            """
        ).fetchone()

    if row is None:
        raise LookupError(f"Unknown READY snapshot: {snapshot_id or 'latest'}")

    resolved_snapshot_id, raw_snapshot_id, biz_date, price_basis = row
    return {
        "snapshot_id": str(resolved_snapshot_id),
        "raw_snapshot_id": str(raw_snapshot_id),
        "biz_date": str(biz_date),
        "price_basis": str(price_basis),
    }
