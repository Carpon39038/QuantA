from __future__ import annotations

from datetime import datetime, timedelta, timezone
import json
from pathlib import Path

from backend.app.app_wiring.settings import AppSettings
from backend.app.domains.market_data.sync import (
    latest_source_biz_date,
    list_source_biz_dates,
    load_latest_building_snapshot,
    resolve_source_backfill_window,
    resolve_source_backfill_window_to_start_date,
)
from backend.app.domains.tasking.bootstrap import ensure_runtime_directories
from backend.app.domains.tasking.service_runner import SUPPORTED_SERVICE_TASKS
from backend.app.shared.providers.duckdb import connect_duckdb


CN_TZ = timezone(timedelta(hours=8))
QUEUE_TASK_NAME = "service"


def enqueue_service_task(
    settings: AppSettings,
    *,
    task_name: str,
    snapshot_id: str | None = None,
    start_biz_date: str | None = None,
    end_biz_date: str | None = None,
    lookback_open_days: int | None = None,
    target_start_biz_date: str | None = None,
) -> dict[str, object]:
    if task_name not in SUPPORTED_SERVICE_TASKS:
        raise ValueError(f"Unsupported service task: {task_name}")

    ensure_runtime_directories(settings)

    requested_at = datetime.now(CN_TZ).isoformat(timespec="seconds")
    task_id = _generate_task_id(task_name)

    connection = connect_duckdb(settings.duckdb_path)
    try:
        published_snapshot = _resolve_service_snapshot(
            settings,
            connection,
            task_name=task_name,
            snapshot_id=snapshot_id,
        )
        (
            resolved_start_biz_date,
            resolved_end_biz_date,
            resolved_lookback_open_days,
            resolved_target_start_biz_date,
        ) = _resolve_service_date_range(
            settings,
            connection,
            task_name=task_name,
            start_biz_date=start_biz_date,
            end_biz_date=end_biz_date,
            lookback_open_days=lookback_open_days,
            target_start_biz_date=target_start_biz_date,
        )
        _replace_task_run_log(
            connection,
            task_id=task_id,
            task_name=task_name,
            biz_date=str(resolved_end_biz_date or published_snapshot["biz_date"]),
            snapshot_id=str(published_snapshot["snapshot_id"]),
            attempt_no=0,
            status="PENDING",
            started_at=requested_at,
            finished_at=requested_at,
            detail={
                "queue_source": "durable_file_queue",
                "requested_at": requested_at,
                "start_biz_date": resolved_start_biz_date,
                "end_biz_date": resolved_end_biz_date,
                "lookback_open_days": resolved_lookback_open_days,
                "target_start_biz_date": resolved_target_start_biz_date,
            },
        )
    finally:
        connection.close()

    queue_item = {
        "task_type": QUEUE_TASK_NAME,
        "task_id": task_id,
        "task_name": task_name,
        "requested_at": requested_at,
        "snapshot_id": str(published_snapshot["snapshot_id"]),
        "raw_snapshot_id": str(published_snapshot["raw_snapshot_id"]),
        "biz_date": str(published_snapshot["biz_date"]),
        "start_biz_date": resolved_start_biz_date,
        "end_biz_date": resolved_end_biz_date,
        "lookback_open_days": resolved_lookback_open_days,
        "target_start_biz_date": resolved_target_start_biz_date,
        "retry_count": 0,
        "max_retries": settings.task_max_retries,
        "next_attempt_at": requested_at,
        "last_error": None,
    }
    queue_path = write_service_queue_item(
        settings,
        task_id=task_id,
        queue_item=queue_item,
    )

    return {
        "task_id": task_id,
        "task_name": task_name,
        "status": "PENDING",
        "requested_at": requested_at,
        "snapshot_id": str(published_snapshot["snapshot_id"]),
        "raw_snapshot_id": str(published_snapshot["raw_snapshot_id"]),
        "retry_count": 0,
        "start_biz_date": resolved_start_biz_date,
        "end_biz_date": resolved_end_biz_date,
        "lookback_open_days": resolved_lookback_open_days,
        "target_start_biz_date": resolved_target_start_biz_date,
        "queue_path": str(queue_path),
    }


def pending_service_queue_items(
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


def move_service_queue_item(
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


def write_service_queue_item(
    settings: AppSettings,
    *,
    task_id: str,
    queue_item: dict[str, object],
) -> Path:
    pending_dir = _queue_state_dir(settings, "pending")
    pending_dir.mkdir(parents=True, exist_ok=True)
    queue_path = pending_dir / f"{task_id}.json"
    queue_path.write_text(
        json.dumps(queue_item, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    return queue_path


def rewrite_service_queue_item(
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


def delete_service_task_artifacts(
    settings: AppSettings,
    *,
    task_id: str,
) -> None:
    for state in ("pending", "processing", "completed", "failed"):
        queue_path = _queue_state_dir(settings, state) / f"{task_id}.json"
        queue_path.unlink(missing_ok=True)

    connection = connect_duckdb(settings.duckdb_path)
    try:
        connection.execute("DELETE FROM task_run_log WHERE task_id = ?", [task_id])
    finally:
        connection.close()


def replace_service_task_run_log(
    settings: AppSettings,
    *,
    task_id: str,
    task_name: str,
    biz_date: str,
    snapshot_id: str,
    attempt_no: int,
    status: str,
    started_at: str,
    finished_at: str,
    detail: dict[str, object],
) -> None:
    connection = connect_duckdb(settings.duckdb_path)
    try:
        _replace_task_run_log(
            connection,
            task_id=task_id,
            task_name=task_name,
            biz_date=biz_date,
            snapshot_id=snapshot_id,
            attempt_no=attempt_no,
            status=status,
            started_at=started_at,
            finished_at=finished_at,
            detail=detail,
        )
    finally:
        connection.close()


def _replace_task_run_log(
    connection,
    *,
    task_id: str,
    task_name: str,
    biz_date: str,
    snapshot_id: str,
    attempt_no: int,
    status: str,
    started_at: str,
    finished_at: str,
    detail: dict[str, object],
) -> None:
    if status == "PENDING":
        error_code = "queued"
        error_message = None
    elif status in {"RUNNING", "SUCCESS"}:
        error_code = None
        error_message = None
    else:
        error_code = "worker_error"
        error_message = str(detail.get("error")) if detail.get("error") is not None else None

    connection.execute("DELETE FROM task_run_log WHERE task_id = ?", [task_id])
    connection.execute(
        """
        INSERT INTO task_run_log (
          task_id,
          task_name,
          biz_date,
          snapshot_id,
          attempt_no,
          status,
          error_code,
          error_message,
          started_at,
          finished_at,
          detail_json
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        [
            task_id,
            task_name,
            biz_date,
            snapshot_id,
            attempt_no,
            status,
            error_code,
            error_message,
            started_at,
            finished_at,
            json.dumps(detail, ensure_ascii=False),
        ],
    )


def _queue_state_dir(settings: AppSettings, state: str) -> Path:
    return settings.queue_dir / QUEUE_TASK_NAME / state


def _generate_task_id(task_name: str) -> str:
    timestamp = datetime.now(CN_TZ).strftime("%Y%m%dT%H%M%S%f")
    return f"task_request_{timestamp}_{task_name}"


def _resolve_published_snapshot(connection, *, snapshot_id: str | None) -> dict[str, object]:
    if snapshot_id is not None:
        row = connection.execute(
            """
            SELECT
              snapshot_id,
              raw_snapshot_id,
              biz_date
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
              biz_date
            FROM artifact_publish
            WHERE status = 'READY'
            ORDER BY publish_seq DESC
            LIMIT 1
            """
        ).fetchone()

    if row is None:
        raise LookupError(f"Unknown READY snapshot: {snapshot_id or 'latest'}")

    snapshot_value, raw_snapshot_id, biz_date = row
    return {
        "snapshot_id": str(snapshot_value),
        "raw_snapshot_id": str(raw_snapshot_id),
        "biz_date": str(biz_date),
    }


def _resolve_service_snapshot(
    settings: AppSettings,
    connection,
    *,
    task_name: str,
    snapshot_id: str | None,
) -> dict[str, object]:
    if task_name in {"daily_screener", "daily_backtest"}:
        if snapshot_id is None:
            building_snapshot = load_latest_building_snapshot(settings)
            if building_snapshot is not None:
                return {
                    "snapshot_id": str(building_snapshot["snapshot_id"]),
                    "raw_snapshot_id": str(building_snapshot["raw_snapshot_id"]),
                    "biz_date": str(building_snapshot["biz_date"]),
                }
        else:
            row = connection.execute(
                """
                SELECT snapshot_id, raw_snapshot_id, biz_date
                FROM artifact_publish
                WHERE snapshot_id = ?
                LIMIT 1
                """,
                [snapshot_id],
            ).fetchone()
            if row is None:
                raise LookupError(f"Unknown snapshot: {snapshot_id}")
            resolved_snapshot_id, raw_snapshot_id, biz_date = row
            return {
                "snapshot_id": str(resolved_snapshot_id),
                "raw_snapshot_id": str(raw_snapshot_id),
                "biz_date": str(biz_date),
            }

    return _resolve_published_snapshot(connection, snapshot_id=snapshot_id)


def _resolve_service_date_range(
    settings: AppSettings,
    connection,
    *,
    task_name: str,
    start_biz_date: str | None,
    end_biz_date: str | None,
    lookback_open_days: int | None,
    target_start_biz_date: str | None,
) -> tuple[str | None, str | None, int | None, str | None]:
    if task_name != "history_backfill":
        return None, None, None, None

    if bool(start_biz_date) != bool(end_biz_date):
        raise ValueError("history_backfill requires start_biz_date and end_biz_date together")
    if lookback_open_days is not None and target_start_biz_date is not None:
        raise ValueError(
            "history_backfill cannot combine lookback_open_days with target_start_biz_date"
        )
    if start_biz_date is not None and end_biz_date is not None:
        return start_biz_date, end_biz_date, lookback_open_days, target_start_biz_date

    resolved_lookback_open_days = (
        int(lookback_open_days) if lookback_open_days is not None else None
    )
    resolved_target_start_biz_date = (
        str(target_start_biz_date) if target_start_biz_date is not None else None
    )
    latest_ready_snapshot = _resolve_published_snapshot(connection, snapshot_id=None)
    latest_ready_biz_date = str(latest_ready_snapshot["biz_date"])
    source_biz_date = latest_source_biz_date(settings)
    if resolved_target_start_biz_date is not None:
        target_window = resolve_source_backfill_window_to_start_date(
            settings,
            target_start_biz_date=resolved_target_start_biz_date,
            end_biz_date=source_biz_date,
        )
        coverage = _load_snapshot_history_coverage(
            connection,
            snapshot_id=str(latest_ready_snapshot["snapshot_id"]),
        )
        if (
            source_biz_date <= latest_ready_biz_date
            and coverage["start_biz_date"] is not None
            and str(coverage["start_biz_date"]) <= str(target_window["start_biz_date"])
        ):
            raise ValueError("history_backfill already satisfies target_start_biz_date")
        return (
            str(target_window["start_biz_date"]),
            str(target_window["end_biz_date"]),
            None,
            resolved_target_start_biz_date,
        )
    if resolved_lookback_open_days is not None:
        if resolved_lookback_open_days <= 0:
            raise ValueError("history_backfill lookback_open_days must be positive")
        target_window = resolve_source_backfill_window(
            settings,
            lookback_open_days=resolved_lookback_open_days,
            end_biz_date=source_biz_date,
        )
        coverage = _load_snapshot_history_coverage(
            connection,
            snapshot_id=str(latest_ready_snapshot["snapshot_id"]),
        )
        if (
            source_biz_date <= latest_ready_biz_date
            and coverage["open_day_count"] >= resolved_lookback_open_days
            and coverage["start_biz_date"] is not None
            and str(coverage["start_biz_date"]) <= str(target_window["start_biz_date"])
        ):
            raise ValueError("history_backfill already satisfies lookback_open_days")
        return (
            str(target_window["start_biz_date"]),
            str(target_window["end_biz_date"]),
            resolved_lookback_open_days,
            None,
        )

    if source_biz_date <= latest_ready_biz_date:
        raise ValueError("history_backfill has no newer biz_date to ingest")

    candidate_dates = list_source_biz_dates(
        settings,
        start_biz_date=latest_ready_biz_date,
        end_biz_date=source_biz_date,
    )
    pending_dates = [biz_date for biz_date in candidate_dates if biz_date > latest_ready_biz_date]
    if not pending_dates:
        raise ValueError("history_backfill has no open biz dates beyond the latest READY snapshot")
    return pending_dates[0], pending_dates[-1], None, None


def _load_snapshot_history_coverage(
    connection,
    *,
    snapshot_id: str,
) -> dict[str, object]:
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
