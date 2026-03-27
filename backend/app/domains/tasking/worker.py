from __future__ import annotations

import argparse
from datetime import datetime, timedelta, timezone
import json

from backend.app.app_wiring.dev_bootstrap import bootstrap_dev_runtime
from backend.app.app_wiring.settings import AppSettings, load_settings
from backend.app.domains.backtest.bootstrap import (
    build_backtest_bundle,
    replace_backtest_materialization,
    upsert_backtest_request_row,
)
from backend.app.domains.backtest.queue import (
    move_backtest_queue_item,
    pending_backtest_queue_items,
)
from backend.app.domains.screener.bootstrap import ensure_screener_artifacts
from backend.app.domains.tasking.bootstrap import ensure_runtime_directories
from backend.app.domains.tasking.queue import (
    move_service_queue_item,
    pending_service_queue_items,
    replace_service_task_run_log,
)
from backend.app.shared.providers.duckdb import connect_duckdb


CN_TZ = timezone(timedelta(hours=8))


def process_backtest_queue(
    settings: AppSettings,
    *,
    limit: int | None = None,
) -> dict[str, object]:
    ensure_runtime_directories(settings)

    pending_items = pending_backtest_queue_items(settings, limit=limit)
    summary = {
        "processed": 0,
        "succeeded": 0,
        "failed": 0,
        "completed_ids": [],
        "failed_ids": [],
    }

    for pending_path, queue_item in pending_items:
        processing_path = move_backtest_queue_item(
            settings,
            path=pending_path,
            target_state="processing",
        )
        backtest_id = str(queue_item["backtest_id"])
        started_at = _now_isoformat()

        try:
            _process_one_backtest_request(settings, queue_item=queue_item, started_at=started_at)
        except Exception as exc:
            _mark_backtest_request_failed(
                settings,
                queue_item=queue_item,
                started_at=started_at,
                error_message=str(exc),
            )
            move_backtest_queue_item(settings, path=processing_path, target_state="failed")
            summary["processed"] += 1
            summary["failed"] += 1
            summary["failed_ids"].append(backtest_id)
            continue

        move_backtest_queue_item(settings, path=processing_path, target_state="completed")
        summary["processed"] += 1
        summary["succeeded"] += 1
        summary["completed_ids"].append(backtest_id)

    return summary


def process_service_queue(
    settings: AppSettings,
    *,
    limit: int | None = None,
) -> dict[str, object]:
    ensure_runtime_directories(settings)

    pending_items = pending_service_queue_items(settings, limit=limit)
    summary = {
        "processed": 0,
        "succeeded": 0,
        "failed": 0,
        "completed_ids": [],
        "failed_ids": [],
    }

    for pending_path, queue_item in pending_items:
        processing_path = move_service_queue_item(
            settings,
            path=pending_path,
            target_state="processing",
        )
        task_id = str(queue_item["task_id"])
        started_at = _now_isoformat()

        try:
            _process_one_service_request(settings, queue_item=queue_item, started_at=started_at)
        except Exception as exc:
            _mark_service_request_failed(
                settings,
                queue_item=queue_item,
                started_at=started_at,
                error_message=str(exc),
            )
            move_service_queue_item(settings, path=processing_path, target_state="failed")
            summary["processed"] += 1
            summary["failed"] += 1
            summary["failed_ids"].append(task_id)
            continue

        move_service_queue_item(settings, path=processing_path, target_state="completed")
        summary["processed"] += 1
        summary["succeeded"] += 1
        summary["completed_ids"].append(task_id)

    return summary


def _process_one_backtest_request(
    settings: AppSettings,
    *,
    queue_item: dict[str, object],
    started_at: str,
) -> None:
    backtest_id = str(queue_item["backtest_id"])
    snapshot_id = str(queue_item["snapshot_id"])
    raw_snapshot_id = str(queue_item["raw_snapshot_id"])
    biz_date = str(queue_item["biz_date"])
    signal_price_basis = str(queue_item["signal_price_basis"])
    strategy_version = str(queue_item["strategy_version"])
    requested_at = str(queue_item["requested_at"])
    payload = queue_item.get("payload")
    payload_dict = payload if isinstance(payload, dict) else {}
    top_n = int(payload_dict.get("top_n", 2))

    connection = connect_duckdb(settings.duckdb_path)
    try:
        retry_count = _fetch_backtest_retry_count(connection, backtest_id=backtest_id)
        upsert_backtest_request_row(
            connection,
            backtest_id=backtest_id,
            requested_at=requested_at,
            snapshot_id=snapshot_id,
            raw_snapshot_id=raw_snapshot_id,
            strategy_version=strategy_version,
            signal_price_basis=signal_price_basis,
            payload_json=payload_dict,
            status="RUNNING",
            retry_count=retry_count + 1,
            last_error=None,
        )

        bundle = build_backtest_bundle(
            connection,
            backtest_id=backtest_id,
            snapshot_id=snapshot_id,
            raw_snapshot_id=raw_snapshot_id,
            biz_date=biz_date,
            price_basis=signal_price_basis,
            requested_at=requested_at,
            top_n=top_n,
            strategy_version=strategy_version,
            created_from=str(payload_dict.get("created_from", "manual_queue_request")),
        )
        if bundle is None:
            raise RuntimeError(f"Backtest request {backtest_id} could not build a replay bundle")

        replace_backtest_materialization(connection, bundle=bundle)
        upsert_backtest_request_row(
            connection,
            backtest_id=backtest_id,
            requested_at=requested_at,
            snapshot_id=snapshot_id,
            raw_snapshot_id=raw_snapshot_id,
            strategy_version=strategy_version,
            signal_price_basis=signal_price_basis,
            payload_json=payload_dict,
            status="SUCCESS",
            retry_count=retry_count + 1,
            last_error=None,
        )
        _replace_task_run_log(
            connection,
            task_id=f"{backtest_id}:worker",
            task_name="backtest_worker",
            biz_date=biz_date,
            snapshot_id=snapshot_id,
            attempt_no=retry_count + 1,
            status="SUCCESS",
            started_at=started_at,
            finished_at=_now_isoformat(),
            detail={
                "backtest_id": backtest_id,
                "top_n": top_n,
                "queue_source": "durable_file_queue",
            },
        )
    finally:
        connection.close()


def _process_one_service_request(
    settings: AppSettings,
    *,
    queue_item: dict[str, object],
    started_at: str,
) -> None:
    task_id = str(queue_item["task_id"])
    task_name = str(queue_item["task_name"])
    snapshot_id = str(queue_item["snapshot_id"])
    biz_date = str(queue_item["biz_date"])
    requested_at = str(queue_item["requested_at"])

    replace_service_task_run_log(
        settings,
        task_id=task_id,
        task_name=task_name,
        biz_date=biz_date,
        snapshot_id=snapshot_id,
        attempt_no=1,
        status="RUNNING",
        started_at=started_at,
        finished_at=started_at,
        detail={
            "queue_source": "durable_file_queue",
            "requested_at": requested_at,
        },
    )

    if task_name == "daily_sync":
        execution_summary = bootstrap_dev_runtime(settings)
    elif task_name == "daily_screener":
        execution_summary = ensure_screener_artifacts(settings)
    else:
        raise ValueError(f"Unsupported service task: {task_name}")

    replace_service_task_run_log(
        settings,
        task_id=task_id,
        task_name=task_name,
        biz_date=biz_date,
        snapshot_id=snapshot_id,
        attempt_no=1,
        status="SUCCESS",
        started_at=started_at,
        finished_at=_now_isoformat(),
        detail={
            "queue_source": "durable_file_queue",
            "requested_at": requested_at,
            "execution_summary": execution_summary,
        },
    )


def _mark_backtest_request_failed(
    settings: AppSettings,
    *,
    queue_item: dict[str, object],
    started_at: str,
    error_message: str,
) -> None:
    backtest_id = str(queue_item["backtest_id"])
    snapshot_id = str(queue_item["snapshot_id"])
    raw_snapshot_id = str(queue_item["raw_snapshot_id"])
    signal_price_basis = str(queue_item["signal_price_basis"])
    strategy_version = str(queue_item["strategy_version"])
    requested_at = str(queue_item["requested_at"])
    biz_date = str(queue_item["biz_date"])
    payload = queue_item.get("payload")
    payload_dict = payload if isinstance(payload, dict) else {}

    connection = connect_duckdb(settings.duckdb_path)
    try:
        retry_count = _fetch_backtest_retry_count(connection, backtest_id=backtest_id)
        upsert_backtest_request_row(
            connection,
            backtest_id=backtest_id,
            requested_at=requested_at,
            snapshot_id=snapshot_id,
            raw_snapshot_id=raw_snapshot_id,
            strategy_version=strategy_version,
            signal_price_basis=signal_price_basis,
            payload_json=payload_dict,
            status="FAILED",
            retry_count=retry_count + 1,
            last_error=error_message,
        )
        _replace_task_run_log(
            connection,
            task_id=f"{backtest_id}:worker",
            task_name="backtest_worker",
            biz_date=biz_date,
            snapshot_id=snapshot_id,
            attempt_no=retry_count + 1,
            status="FAILED",
            started_at=started_at,
            finished_at=_now_isoformat(),
            detail={
                "backtest_id": backtest_id,
                "error": error_message,
                "queue_source": "durable_file_queue",
            },
        )
    finally:
        connection.close()


def _mark_service_request_failed(
    settings: AppSettings,
    *,
    queue_item: dict[str, object],
    started_at: str,
    error_message: str,
) -> None:
    task_id = str(queue_item["task_id"])
    task_name = str(queue_item["task_name"])
    snapshot_id = str(queue_item["snapshot_id"])
    biz_date = str(queue_item["biz_date"])
    requested_at = str(queue_item["requested_at"])

    replace_service_task_run_log(
        settings,
        task_id=task_id,
        task_name=task_name,
        biz_date=biz_date,
        snapshot_id=snapshot_id,
        attempt_no=1,
        status="FAILED",
        started_at=started_at,
        finished_at=_now_isoformat(),
        detail={
            "queue_source": "durable_file_queue",
            "requested_at": requested_at,
            "error": error_message,
        },
    )


def _fetch_backtest_retry_count(connection, *, backtest_id: str) -> int:
    row = connection.execute(
        """
        SELECT retry_count
        FROM backtest_request
        WHERE backtest_id = ?
        LIMIT 1
        """,
        [backtest_id],
    ).fetchone()
    return int(row[0]) if row is not None else 0


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
            None if status == "SUCCESS" else "worker_error",
            None if status == "SUCCESS" else str(detail.get("error")),
            started_at,
            finished_at,
            json.dumps(detail, ensure_ascii=False),
        ],
    )


def _now_isoformat() -> str:
    return datetime.now(CN_TZ).isoformat(timespec="seconds")


def _print_summary(summary: dict[str, object]) -> None:
    print("QuantA task worker run:")
    print(f"- processed: {summary['processed']}")
    print(f"- succeeded: {summary['succeeded']}")
    print(f"- failed: {summary['failed']}")
    print(
        "- completed_ids:",
        ", ".join(summary["completed_ids"]) if summary["completed_ids"] else "none",
    )
    print(
        "- failed_ids:",
        ", ".join(summary["failed_ids"]) if summary["failed_ids"] else "none",
    )


def main() -> int:
    parser = argparse.ArgumentParser(description="Process QuantA durable queue items.")
    parser.add_argument(
        "--task",
        choices=["backtest", "service"],
        default="backtest",
        help="Queue task type to process.",
    )
    parser.add_argument(
        "--once",
        action="store_true",
        help="Process current pending items once and exit.",
    )
    parser.add_argument(
        "--limit",
        type=int,
        default=None,
        help="Limit the number of items processed in this run.",
    )
    args = parser.parse_args()

    settings = load_settings()
    if args.task == "service":
        summary = process_service_queue(settings, limit=args.limit)
    elif args.task == "backtest":
        summary = process_backtest_queue(settings, limit=args.limit)
    else:
        raise ValueError(f"Unsupported task type: {args.task}")

    _print_summary(summary)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
