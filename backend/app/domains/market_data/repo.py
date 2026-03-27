from __future__ import annotations

from datetime import datetime, timedelta, timezone
import json
from typing import Any

from backend.app.app_wiring.settings import AppSettings
from backend.app.domains.market_data.bootstrap import ensure_dev_duckdb
from backend.app.shared.providers.duckdb import connect_duckdb


def _decode_json_text(raw_value: str | None, fallback: Any) -> Any:
    if not raw_value:
        return fallback
    return json.loads(raw_value)


CN_TZ = timezone(timedelta(hours=8))


def _isoformat(value: object) -> str:
    if isinstance(value, datetime):
        normalized = value if value.tzinfo is not None else value.replace(tzinfo=CN_TZ)
        return normalized.isoformat()
    if hasattr(value, "isoformat"):
        return str(value.isoformat())
    return str(value)


def load_latest_published_snapshot(settings: AppSettings) -> dict[str, object]:
    ensure_dev_duckdb(settings)

    connection = connect_duckdb(settings.duckdb_path)
    try:
        artifact_row = connection.execute(
            """
            SELECT
              snapshot_id,
              raw_snapshot_id,
              status,
              published_at,
              price_basis
            FROM artifact_publish
            WHERE status = 'READY'
            ORDER BY published_at DESC, publish_seq DESC
            LIMIT 1
            """
        ).fetchone()
        if artifact_row is None:
            raise RuntimeError("No READY snapshot found in artifact_publish")

        (
            snapshot_id,
            raw_snapshot_id,
            status,
            published_at,
            price_basis,
        ) = artifact_row

        market_row = connection.execute(
            """
            SELECT
              trade_date,
              summary,
              regime_label,
              snapshot_source,
              indices_json,
              breadth_json,
              highlights_json
            FROM market_regime_daily
            WHERE snapshot_id = ?
            ORDER BY trade_date DESC
            LIMIT 1
            """,
            [snapshot_id],
        ).fetchone()
        if market_row is None:
            raise RuntimeError(f"No market overview row found for snapshot_id={snapshot_id}")

        (
            trade_date,
            market_summary,
            regime_label,
            snapshot_source,
            indices_json,
            breadth_json,
            highlights_json,
        ) = market_row

        screener_run_row = connection.execute(
            """
            SELECT
              run_id,
              strategy_name,
              as_of_date,
              signal_price_basis
            FROM screener_run
            WHERE snapshot_id = ?
            ORDER BY finished_at DESC, started_at DESC
            LIMIT 1
            """,
            [snapshot_id],
        ).fetchone()
        if screener_run_row is None:
            raise RuntimeError(f"No screener run found for snapshot_id={snapshot_id}")

        (
            screener_run_id,
            screener_strategy_name,
            screener_as_of_date,
            screener_signal_price_basis,
        ) = screener_run_row

        screener_rows = connection.execute(
            """
            SELECT
              symbol,
              display_name,
              total_score,
              thesis,
              matched_rules_json,
              risk_flags_json
            FROM screener_result
            WHERE run_id = ?
            ORDER BY rank_no ASC, symbol ASC
            """,
            [screener_run_id],
        ).fetchall()

        backtest_row = connection.execute(
            """
            SELECT
              strategy_name,
              start_date,
              end_date,
              annual_return,
              max_drawdown,
              win_rate,
              profit_loss_ratio,
              notes_json
            FROM backtest_run
            WHERE snapshot_id = ?
            ORDER BY created_at DESC
            LIMIT 1
            """,
            [snapshot_id],
        ).fetchone()
        if backtest_row is None:
            raise RuntimeError(f"No backtest run found for snapshot_id={snapshot_id}")

        (
            backtest_strategy_name,
            backtest_start_date,
            backtest_end_date,
            annual_return,
            max_drawdown,
            win_rate,
            profit_loss_ratio,
            backtest_notes_json,
        ) = backtest_row

        task_rows = connection.execute(
            """
            SELECT
              task_name,
              status,
              finished_at,
              detail_json
            FROM task_run_log
            WHERE snapshot_id = ?
            ORDER BY finished_at DESC, task_name ASC
            """,
            [snapshot_id],
        ).fetchall()

        task_status: dict[str, object] = {}
        last_run = None
        next_window = None
        for task_name, task_state, finished_at, detail_json in task_rows:
            task_status[str(task_name)] = str(task_state)
            if last_run is None and finished_at is not None:
                last_run = _isoformat(finished_at)
            detail = _decode_json_text(detail_json, {})
            if isinstance(detail, dict) and not next_window:
                detail_next_window = detail.get("next_window")
                if isinstance(detail_next_window, str) and detail_next_window:
                    next_window = detail_next_window

        if last_run is not None:
            task_status["last_run"] = last_run
        if next_window is not None:
            task_status["next_window"] = next_window

        return {
            "snapshot_id": str(snapshot_id),
            "raw_snapshot_id": str(raw_snapshot_id),
            "status": str(status),
            "generated_at": _isoformat(published_at),
            "price_basis": str(price_basis),
            "market_overview": {
                "trade_date": _isoformat(trade_date),
                "summary": str(market_summary),
                "regime_label": str(regime_label),
                "snapshot_source": str(snapshot_source),
                "indices": _decode_json_text(indices_json, []),
                "breadth": _decode_json_text(breadth_json, {}),
                "highlights": _decode_json_text(highlights_json, []),
            },
            "screener": {
                "strategy_name": str(screener_strategy_name),
                "as_of_date": _isoformat(screener_as_of_date),
                "signal_price_basis": str(screener_signal_price_basis),
                "top_candidates": [
                    {
                        "symbol": str(symbol),
                        "name": str(display_name),
                        "score": int(total_score),
                        "thesis": str(thesis),
                        "signals": _decode_json_text(matched_rules_json, []),
                        "risks": _decode_json_text(risk_flags_json, []),
                    }
                    for (
                        symbol,
                        display_name,
                        total_score,
                        thesis,
                        matched_rules_json,
                        risk_flags_json,
                    ) in screener_rows
                ],
            },
            "backtest": {
                "strategy_name": str(backtest_strategy_name),
                "window": f"{_isoformat(backtest_start_date)} to {_isoformat(backtest_end_date)}",
                "metrics": {
                    "cagr_pct": float(annual_return),
                    "max_drawdown_pct": float(max_drawdown),
                    "win_rate_pct": float(win_rate),
                    "profit_factor": float(profit_loss_ratio),
                },
                "notes": _decode_json_text(backtest_notes_json, []),
            },
            "task_status": task_status,
        }
    finally:
        connection.close()
