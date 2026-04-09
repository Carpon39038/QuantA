#!/usr/bin/env python3

from __future__ import annotations

import json
import os
from pathlib import Path
import socket
import subprocess
import sys
import time
import urllib.request

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from backend.app.app_wiring.settings import load_settings
from backend.app.domains.backtest.queue import delete_backtest_request_artifacts
from backend.app.domains.market_data.sync import delete_snapshot_artifacts
from backend.app.domains.tasking.bootstrap import ensure_runtime_directories
from backend.app.domains.tasking.queue import delete_service_task_artifacts
from backend.app.shared.providers.duckdb import connect_duckdb
from backend.app.shared.telemetry.alerts import load_recent_alerts


def find_free_port() -> int:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
        sock.bind(("127.0.0.1", 0))
        return int(sock.getsockname()[1])


def fetch_json(url: str) -> dict[str, object]:
    with urllib.request.urlopen(url, timeout=5) as response:
        return json.loads(response.read().decode("utf-8"))


def fetch_text(url: str) -> str:
    with urllib.request.urlopen(url, timeout=5) as response:
        return response.read().decode("utf-8")


def post_json(url: str, payload: dict[str, object] | None = None) -> dict[str, object]:
    data = json.dumps(payload or {}).encode("utf-8")
    request = urllib.request.Request(
        url,
        data=data,
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    with urllib.request.urlopen(request, timeout=10) as response:
        return json.loads(response.read().decode("utf-8"))


def wait_for(check_name: str, url: str, timeout_seconds: float = 12.0) -> None:
    deadline = time.time() + timeout_seconds
    last_error: Exception | None = None

    while time.time() < deadline:
        try:
            urllib.request.urlopen(url, timeout=1).read()
            return
        except Exception as exc:
            last_error = exc
            time.sleep(0.2)

    raise RuntimeError(f"{check_name} did not become ready: {last_error}")


def start_process(
    name: str,
    command: list[str],
    env: dict[str, str],
    log_path: Path,
) -> subprocess.Popen[bytes]:
    log_file = log_path.open("wb")
    process = subprocess.Popen(
        command,
        cwd=ROOT,
        env=env,
        stdout=log_file,
        stderr=subprocess.STDOUT,
    )
    process.log_file = log_file  # type: ignore[attr-defined]
    print(f"[app-smoke] started {name}: {' '.join(command)}")
    print(f"[app-smoke] log: {log_path}")
    return process


def stop_process(process: subprocess.Popen[bytes]) -> None:
    if process.poll() is None:
        process.terminate()
        try:
            process.wait(timeout=5)
        except subprocess.TimeoutExpired:
            process.kill()
            process.wait(timeout=5)
    log_file = getattr(process, "log_file", None)
    if log_file is not None:
        log_file.close()


def run_checked_command(command: list[str], env: dict[str, str]) -> subprocess.CompletedProcess[str]:
    print(f"[app-smoke] run: {' '.join(command)}")
    return subprocess.run(
        command,
        cwd=ROOT,
        env=env,
        check=True,
        capture_output=True,
        text=True,
    )


def fetch_task_log(settings, *, task_id: str) -> dict[str, object]:
    connection = connect_duckdb(settings.duckdb_path, read_only=True)
    try:
        row = connection.execute(
            """
            SELECT
              task_id,
              task_name,
              biz_date,
              snapshot_id,
              attempt_no,
              status,
              detail_json
            FROM task_run_log
            WHERE task_id = ?
            LIMIT 1
            """,
            [task_id],
        ).fetchone()
        if row is None:
            raise LookupError(f"Unknown task_id: {task_id}")
        task_id_value, task_name, biz_date, snapshot_id, attempt_no, status, detail_json = row
        return {
            "task_id": str(task_id_value),
            "task_name": str(task_name),
            "biz_date": str(biz_date),
            "snapshot_id": str(snapshot_id),
            "attempt_no": int(attempt_no),
            "status": str(status),
            "detail": json.loads(detail_json) if detail_json else {},
        }
    finally:
        connection.close()


def main() -> int:
    settings = load_settings()
    ensure_runtime_directories(settings)
    baseline_alert_count = len(load_recent_alerts(settings, limit=200))

    backend_port = find_free_port()
    frontend_port = find_free_port()
    backend_origin = f"http://127.0.0.1:{backend_port}"
    frontend_origin = f"http://127.0.0.1:{frontend_port}"

    env = os.environ.copy()
    env.update(
        {
            "PYTHONUNBUFFERED": "1",
            "QUANTA_BACKEND_HOST": "127.0.0.1",
            "QUANTA_BACKEND_PORT": str(backend_port),
            "QUANTA_FRONTEND_HOST": "127.0.0.1",
            "QUANTA_FRONTEND_PORT": str(frontend_port),
        }
    )

    backend_log = settings.logs_dir / "app-smoke-backend.log"
    frontend_log = settings.logs_dir / "app-smoke-frontend.log"

    backend = start_process(
        "backend",
        ["pnpm", "run", "backend:dev"],
        env,
        backend_log,
    )
    frontend = None
    queued_backtest_id: str | None = None
    queued_service_task_ids: list[str] = []
    pipeline_snapshot_id: str | None = None
    pipeline_raw_snapshot_id: str | None = None

    try:
        wait_for("backend health", f"{backend_origin}/health")

        frontend = start_process(
            "frontend",
            ["pnpm", "run", "frontend:dev"],
            env,
            frontend_log,
        )
        wait_for("frontend health", f"{frontend_origin}/health")

        backend_payload = fetch_json(f"{backend_origin}/api/v1/snapshot/latest")
        frontend_proxy_payload = fetch_json(f"{frontend_origin}/api/v1/snapshot/latest")
        stock_snapshot_payload = fetch_json(
            f"{backend_origin}/api/v1/stocks/300750.SZ/snapshot"
        )
        latest_raw_kline_payload = fetch_json(
            f"{backend_origin}/api/v1/stocks/300750.SZ/kline?dataset=daily_bar"
            "&raw_snapshot_id=raw_snapshot_2026-03-27_close_001"
        )
        previous_raw_kline_payload = fetch_json(
            f"{backend_origin}/api/v1/stocks/300750.SZ/kline?dataset=daily_bar"
            "&raw_snapshot_id=raw_snapshot_2026-03-26_close_001"
        )
        frontend_price_kline_payload = fetch_json(
            f"{frontend_origin}/api/v1/stocks/300750.SZ/kline?dataset=price_series"
        )
        indicator_payload = fetch_json(
            f"{backend_origin}/api/v1/stocks/300750.SZ/indicators"
        )
        capital_flow_payload = fetch_json(
            f"{frontend_origin}/api/v1/stocks/300750.SZ/capital-flow"
        )
        fundamentals_payload = fetch_json(
            f"{backend_origin}/api/v1/stocks/300750.SZ/fundamentals"
        )
        disclosures_payload = fetch_json(
            f"{backend_origin}/api/v1/stocks/300750.SZ/disclosures"
        )
        corporate_actions_payload = fetch_json(
            f"{backend_origin}/api/v1/stocks/300750.SZ/corporate-actions"
        )
        screener_latest_payload = fetch_json(f"{backend_origin}/api/v1/screener/runs/latest")
        screener_results_payload = fetch_json(
            f"{backend_origin}/api/v1/screener/runs/{screener_latest_payload['run_id']}/results"
        )
        backtest_latest_payload = fetch_json(f"{backend_origin}/api/v1/backtests/runs/latest")
        backtest_trades_payload = fetch_json(
            f"{backend_origin}/api/v1/backtests/runs/{backtest_latest_payload['backtest_id']}/trades"
        )
        backtest_curve_payload = fetch_json(
            f"{frontend_origin}/api/v1/backtests/runs/{backtest_latest_payload['backtest_id']}/equity-curve"
        )
        task_runs_payload = fetch_json(f"{backend_origin}/api/v1/tasks/runs")
        system_health_payload = fetch_json(f"{frontend_origin}/api/v1/system/health")
        alerts_payload = fetch_json(f"{backend_origin}/api/v1/system/alerts")
        daily_sync_post_payload = post_json(f"{backend_origin}/api/v1/tasks/daily-sync/run")
        queued_service_task_ids.append(str(daily_sync_post_payload["task"]["task_id"]))
        queued_task_runs_payload = fetch_json(f"{backend_origin}/api/v1/tasks/runs")
        queued_tasks_by_id = {
            str(item["task_id"]): item for item in queued_task_runs_payload["items"]
        }
        sync_worker_run = run_checked_command(
            ["python3", "-m", "backend.app.domains.tasking.worker", "--once", "--task", "service", "--limit", "1"],
            env,
        )
        sync_task_payload = fetch_task_log(
            settings,
            task_id=str(daily_sync_post_payload["task"]["task_id"]),
        )
        pipeline_snapshot_id = str(sync_task_payload["detail"]["execution_summary"]["snapshot_id"])
        pipeline_raw_snapshot_id = str(
            sync_task_payload["detail"]["execution_summary"]["raw_snapshot_id"]
        )

        daily_screener_post_payload = post_json(
            f"{backend_origin}/api/v1/tasks/daily-screener/run",
            {"snapshot_id": pipeline_snapshot_id},
        )
        queued_service_task_ids.append(str(daily_screener_post_payload["task"]["task_id"]))
        screener_worker_run = run_checked_command(
            ["python3", "-m", "backend.app.domains.tasking.worker", "--once", "--task", "service", "--limit", "1"],
            env,
        )

        daily_backtest_post_payload = post_json(
            f"{backend_origin}/api/v1/tasks/daily-backtest/run",
            {"snapshot_id": pipeline_snapshot_id},
        )
        queued_service_task_ids.append(str(daily_backtest_post_payload["task"]["task_id"]))
        backtest_service_worker_run = run_checked_command(
            ["python3", "-m", "backend.app.domains.tasking.worker", "--once", "--task", "service", "--limit", "1"],
            env,
        )
        history_backfill_post_payload = post_json(
            f"{backend_origin}/api/v1/tasks/history-backfill/run",
            {
                "start_biz_date": "2026-03-31",
                "end_biz_date": "2026-03-31",
            },
        )
        queued_service_task_ids.append(str(history_backfill_post_payload["task"]["task_id"]))
        history_backfill_worker_run = run_checked_command(
            ["python3", "-m", "backend.app.domains.tasking.worker", "--once", "--task", "service", "--limit", "1"],
            env,
        )
        processed_task_runs_payload = fetch_json(f"{backend_origin}/api/v1/tasks/runs")
        refreshed_snapshot_payload = fetch_json(f"{backend_origin}/api/v1/snapshot/latest")
        refreshed_screener_payload = fetch_json(f"{backend_origin}/api/v1/screener/runs/latest")
        refreshed_service_backtest_payload = fetch_json(f"{backend_origin}/api/v1/backtests/runs/latest")
        backtest_post_payload = post_json(
            f"{backend_origin}/api/v1/backtests/runs",
            {"top_n": 3},
        )
        queued_backtest_id = str(backtest_post_payload["backtest"]["backtest_id"])
        queued_backtest_payload = fetch_json(
            f"{backend_origin}/api/v1/backtests/runs/{queued_backtest_id}"
        )
        worker_run = run_checked_command(
            ["python3", "-m", "backend.app.domains.tasking.worker", "--once", "--task", "backtest"],
            env,
        )
        processed_backtest_payload = fetch_json(
            f"{backend_origin}/api/v1/backtests/runs/{backtest_post_payload['backtest']['backtest_id']}"
        )
        frontend_html = fetch_text(f"{frontend_origin}/")
        frontend_js = fetch_text(f"{frontend_origin}/main.js")

        assert backend_payload["status"] == "READY"
        assert backend_payload["snapshot_id"] == frontend_proxy_payload["snapshot_id"]
        assert backend_payload["market_overview"]["trade_date"] == "2026-03-27"
        assert backend_payload["runtime"]["duckdb_path"].endswith("quanta.duckdb")
        assert backend_payload["runtime"]["source_provider"] == "fixture_json"
        assert backend_payload["runtime"]["source_universe"] == "core_operating_40"
        assert backend_payload["runtime"]["source_symbol_count"] == 40
        assert backend_payload["task_status"]["data_update"] == "SUCCESS"
        assert backend_payload["shadow_validation"]["status"] in {"SKIPPED", "UNKNOWN"}
        assert backend_payload["screener"]["strategy_name"] == "三策略候选池"
        assert len(backend_payload["screener"]["top_candidates"]) >= 3
        assert backend_payload["screener"]["top_candidates"][0]["strategy_name"] in {
            "趋势突破",
            "放量启动",
            "资金共振",
        }
        assert (
            backend_payload["screener"]["top_candidates"][0]["trend_score"] is not None
        )
        assert (
            backend_payload["screener"]["top_candidates"][0]["capital_score"] is not None
        )
        assert stock_snapshot_payload["available_series"]["daily_bar"]["row_count"] == 3
        assert stock_snapshot_payload["available_series"]["fundamental_feature"]["row_count"] == 0
        assert stock_snapshot_payload["latest_daily_bar"]["trade_date"] == "2026-03-27"
        assert abs(stock_snapshot_payload["latest_price_bar"]["close"] - 266.4) < 1e-6
        assert len(latest_raw_kline_payload["items"]) == 3
        assert abs(latest_raw_kline_payload["items"][1]["close_raw"] - 258.1) < 1e-6
        assert (
            latest_raw_kline_payload["items"][1]["effective_raw_snapshot_id"]
            == "raw_snapshot_2026-03-27_close_001"
        )
        assert len(previous_raw_kline_payload["items"]) == 2
        assert abs(previous_raw_kline_payload["items"][-1]["close_raw"] - 257.4) < 1e-6
        assert len(frontend_price_kline_payload["items"]) == 3
        assert abs(frontend_price_kline_payload["items"][1]["close"] - 260.1) < 1e-6
        assert (
            frontend_price_kline_payload["items"][1]["effective_snapshot_id"]
            == "snapshot_2026-03-27_ready_001"
        )
        assert indicator_payload["range"]["row_count"] == 3
        assert indicator_payload["latest_indicator"]["effective_snapshot_id"] == "snapshot_2026-03-27_ready_001"
        assert len(indicator_payload["latest_patterns"]) >= 2
        assert any(
            item["signal_code"] == "breakout_up" for item in indicator_payload["latest_patterns"]
        )
        assert any(
            item["signal_code"] == "volume_expansion"
            for item in indicator_payload["latest_patterns"]
        )
        assert capital_flow_payload["range"]["row_count"] == 3
        assert capital_flow_payload["latest_capital_feature"]["effective_snapshot_id"] == "snapshot_2026-03-27_ready_001"
        assert capital_flow_payload["latest_capital_feature"]["has_dragon_tiger"] is True
        assert fundamentals_payload["range"]["row_count"] == 0
        assert fundamentals_payload["latest_fundamental_feature"] is None
        assert stock_snapshot_payload["available_series"]["official_disclosure"]["row_count"] >= 2
        assert stock_snapshot_payload["available_series"]["corporate_action"]["row_count"] >= 1
        assert disclosures_payload["range"]["row_count"] >= 2
        assert disclosures_payload["latest_disclosure"] is not None
        assert "公告" in disclosures_payload["latest_disclosure"]["title"]
        assert disclosures_payload["items"][-1]["detail_url"].startswith(
            "https://www.cninfo.com.cn/new/disclosure/detail"
        )
        assert corporate_actions_payload["range"]["row_count"] >= 1
        assert corporate_actions_payload["latest_corporate_action"] is not None
        assert corporate_actions_payload["items"][-1]["action_summary"]
        assert screener_latest_payload["run_id"].startswith("screener_run_")
        assert screener_latest_payload["result_count"] == len(screener_latest_payload["results"])
        assert screener_latest_payload["result_count"] >= 3
        assert screener_latest_payload["results"][0]["rank_no"] == 1
        assert screener_results_payload["run_id"] == screener_latest_payload["run_id"]
        assert len(screener_results_payload["results"]) == len(
            screener_latest_payload["results"]
        )
        assert backtest_latest_payload["backtest_id"].startswith("backtest_run_")
        assert backtest_latest_payload["request"]["payload"]["top_n"] == 2
        assert len(backtest_latest_payload["trades"]) == 4
        assert len(backtest_latest_payload["equity_curve"]) == 3
        assert backtest_trades_payload["backtest_id"] == backtest_latest_payload["backtest_id"]
        assert len(backtest_trades_payload["trades"]) == len(backtest_latest_payload["trades"])
        assert backtest_curve_payload["backtest_id"] == backtest_latest_payload["backtest_id"]
        assert len(backtest_curve_payload["equity_curve"]) == len(
            backtest_latest_payload["equity_curve"]
        )
        assert (
            backtest_latest_payload["equity_curve"][-1]["equity"]
            > backtest_latest_payload["equity_curve"][0]["equity"]
        )
        assert task_runs_payload["snapshot_id"] == backend_payload["snapshot_id"]
        assert len(task_runs_payload["items"]) >= 4
        assert any(item["task_name"] == "backtest" for item in task_runs_payload["items"])
        assert system_health_payload["status"] == "ok"
        assert system_health_payload["snapshot_id"] == backend_payload["snapshot_id"]
        assert system_health_payload["task_count"] == len(task_runs_payload["items"])
        assert system_health_payload["table_counts"]["backtest_trade"] >= 4
        assert system_health_payload["alert_count"] == baseline_alert_count
        assert system_health_payload["alert_summary"]["window_count"] == baseline_alert_count
        assert system_health_payload["history_coverage"]["open_day_count"] >= 1
        assert system_health_payload["shadow_validation"]["status"] in {
            "SKIPPED",
            "UNKNOWN",
        }
        assert len(alerts_payload["items"]) == min(baseline_alert_count, 20)
        assert alerts_payload["summary"]["window_count"] == baseline_alert_count
        assert daily_sync_post_payload["status"] == "accepted"
        assert daily_sync_post_payload["task"]["task_name"] == "daily_sync"
        assert daily_sync_post_payload["task"]["status"] == "PENDING"
        assert queued_tasks_by_id[str(daily_sync_post_payload["task"]["task_id"])]["status"] == "PENDING"
        assert "processed: 1" in sync_worker_run.stdout
        assert sync_task_payload["status"] == "SUCCESS"
        assert pipeline_snapshot_id is not None
        assert pipeline_raw_snapshot_id is not None
        assert daily_screener_post_payload["status"] == "accepted"
        assert daily_screener_post_payload["task"]["task_name"] == "daily_screener"
        assert daily_screener_post_payload["task"]["status"] == "PENDING"
        assert "processed: 1" in screener_worker_run.stdout
        assert daily_backtest_post_payload["status"] == "accepted"
        assert daily_backtest_post_payload["task"]["task_name"] == "daily_backtest"
        assert daily_backtest_post_payload["task"]["status"] == "PENDING"
        assert "processed: 1" in backtest_service_worker_run.stdout
        assert history_backfill_post_payload["status"] == "accepted"
        assert history_backfill_post_payload["task"]["task_name"] == "history_backfill"
        assert history_backfill_post_payload["task"]["status"] == "PENDING"
        assert "processed: 1" in history_backfill_worker_run.stdout
        processed_tasks_by_id = {
            str(item["task_id"]): item for item in processed_task_runs_payload["items"]
        }
        for task_id in queued_service_task_ids:
            assert processed_tasks_by_id[task_id]["status"] == "SUCCESS"
            assert (
                processed_tasks_by_id[task_id]["detail"]["queue_source"]
                == "durable_file_queue"
            )
        history_backfill_task = processed_tasks_by_id[
            str(history_backfill_post_payload["task"]["task_id"])
        ]
        assert history_backfill_task["detail"]["execution_summary"]["backfill"]["snapshot_count"] == 0
        assert (
            history_backfill_task["detail"]["execution_summary"]["backfill"]["skipped_existing_biz_dates"]
            == ["2026-03-31"]
        )
        assert refreshed_snapshot_payload["snapshot_id"] == pipeline_snapshot_id
        assert refreshed_snapshot_payload["market_overview"]["trade_date"] == "2026-03-31"
        assert refreshed_snapshot_payload["shadow_validation"]["status"] == "SKIPPED"
        assert refreshed_screener_payload["snapshot_id"] == pipeline_snapshot_id
        assert refreshed_screener_payload["run_id"] != screener_latest_payload["run_id"]
        assert refreshed_service_backtest_payload["snapshot_id"] == pipeline_snapshot_id
        assert refreshed_service_backtest_payload["backtest_id"] != backtest_latest_payload["backtest_id"]
        assert backtest_post_payload["status"] == "accepted"
        assert backtest_post_payload["backtest"]["status"] == "PENDING"
        assert backtest_post_payload["backtest"]["payload"]["top_n"] == 3
        assert queued_backtest_payload["status"] == "PENDING"
        assert queued_backtest_payload["trades"] == []
        assert "processed: 1" in worker_run.stdout
        assert (
            processed_backtest_payload["backtest_id"]
            == queued_backtest_id
        )
        assert processed_backtest_payload["status"] == "SUCCESS"
        assert len(processed_backtest_payload["trades"]) >= 4
        assert len(processed_backtest_payload["equity_curve"]) >= 3
        assert "QuantA" in frontend_html
        assert "fetchLatestSnapshot" in frontend_js
        assert "观察名单" in frontend_html
        assert "个股详情" in frontend_html
        assert "价格轨迹" in frontend_html
        assert "财务侧" in frontend_html
        assert "官方披露" in frontend_html

        print("[app-smoke] backend and frontend are healthy")
        print(
            "[app-smoke] proxy snapshot id:",
            frontend_proxy_payload["snapshot_id"],
        )
        print("[app-smoke] frontend shell loaded")
        return 0
    finally:
        if frontend is not None:
            stop_process(frontend)
        stop_process(backend)
        if queued_backtest_id:
            delete_backtest_request_artifacts(settings, backtest_id=queued_backtest_id)
        if pipeline_snapshot_id and pipeline_raw_snapshot_id:
            delete_snapshot_artifacts(
                settings,
                snapshot_id=pipeline_snapshot_id,
                raw_snapshot_id=pipeline_raw_snapshot_id,
            )
        for task_id in queued_service_task_ids:
            delete_service_task_artifacts(settings, task_id=task_id)


if __name__ == "__main__":
    raise SystemExit(main())
