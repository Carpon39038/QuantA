from __future__ import annotations

import argparse
import json
from pathlib import Path

import duckdb

from backend.app.app_wiring.settings import AppSettings, load_settings
from backend.app.domains.market_data.schema import TABLE_DEFINITIONS, iter_ddl_statements
from backend.app.domains.tasking.bootstrap import ensure_runtime_directories
from backend.app.shared.providers.duckdb import connect_duckdb
from backend.app.shared.providers.local_fixture import load_json_fixture


REQUIRED_SCHEMA_COLUMNS = {
    "raw_snapshot": {
        "raw_snapshot_id",
        "snapshot_seq",
        "required_datasets_json",
        "completeness_json",
        "source_watermark_json",
        "attempt_no",
    },
    "daily_bar": {
        "open_raw",
        "high_raw",
        "low_raw",
        "close_raw",
        "pre_close_raw",
        "high_limit",
        "low_limit",
        "limit_rule_code",
        "source",
        "updated_at",
    },
    "price_series_daily": {
        "open",
        "high",
        "low",
        "close",
        "pre_close",
        "adj_factor",
        "updated_at",
    },
    "indicator_daily": {
        "ma5",
        "macd_dif",
        "kdj_k",
        "rsi6",
        "boll_upper",
        "volume_ratio",
        "updated_at",
    },
    "pattern_signal_daily": {
        "signal_code",
        "signal_type",
        "direction",
        "is_triggered",
        "signal_score",
        "payload_json",
        "updated_at",
    },
    "capital_feature_daily": {
        "main_net_inflow",
        "main_net_inflow_ratio",
        "northbound_net_inflow",
        "has_dragon_tiger",
        "updated_at",
    },
    "fundamental_feature_daily": {
        "report_period",
        "ann_date",
        "roe_dt",
        "grossprofit_margin",
        "debt_to_assets",
        "cash_to_profit",
        "fundamental_score",
        "updated_at",
    },
    "screener_result": {
        "trend_score",
        "price_volume_score",
        "capital_score",
        "fundamental_score",
        "matched_rules_json",
        "risk_flags_json",
    },
    "backtest_request": {
        "requested_at",
        "snapshot_id",
        "raw_snapshot_id",
        "strategy_version",
        "signal_price_basis",
        "payload_json",
        "status",
        "retry_count",
    },
    "backtest_trade": {
        "side",
        "price_basis",
        "trade_price",
        "quantity",
        "notional",
        "fee",
        "tax",
        "pnl",
        "holding_days",
        "reason",
        "rank_no",
    },
    "backtest_equity_curve": {
        "position_count",
        "cash",
        "market_value",
        "equity",
        "drawdown",
        "daily_return",
        "benchmark_close",
        "updated_at",
    },
}


def ensure_dev_duckdb(settings: AppSettings) -> dict[str, object]:
    ensure_runtime_directories(settings)

    rebuilt = _rebuild_duckdb_if_needed(settings.duckdb_path)
    connection = connect_duckdb(settings.duckdb_path)
    try:
        for statement in iter_ddl_statements():
            connection.execute(statement)

        before_counts = _read_table_counts(connection)
        seeded = _seed_dev_dataset(connection, settings.fixture_path)
        after_counts = _read_table_counts(connection)
    finally:
        connection.close()

    return {
        "duckdb_path": str(settings.duckdb_path),
        "seed_fixture_path": str(settings.fixture_path),
        "rebuilt": rebuilt,
        "seeded": seeded or rebuilt,
        "table_counts": after_counts,
        "changed_tables": [
            table_name
            for table_name, row_count in after_counts.items()
            if row_count != before_counts.get(table_name, 0)
        ],
    }


def _rebuild_duckdb_if_needed(duckdb_path: Path) -> bool:
    if not duckdb_path.exists():
        return False

    connection = connect_duckdb(duckdb_path)
    try:
        if _schema_is_compatible(connection):
            return False
    finally:
        connection.close()

    duckdb_path.unlink(missing_ok=True)
    return True


def _schema_is_compatible(connection: duckdb.DuckDBPyConnection) -> bool:
    for table_name, required_columns in REQUIRED_SCHEMA_COLUMNS.items():
        columns = {
            row[0]
            for row in connection.execute(
                """
                SELECT column_name
                FROM information_schema.columns
                WHERE table_name = ?
                """,
                [table_name],
            ).fetchall()
        }
        if columns and required_columns.issubset(columns):
            continue
        if not columns:
            continue
        return False

    return True


def _read_table_counts(connection: duckdb.DuckDBPyConnection) -> dict[str, int]:
    return {
        table.name: int(connection.execute(f"SELECT COUNT(*) FROM {table.name}").fetchone()[0])
        for table in TABLE_DEFINITIONS
    }


def _insert_row(
    connection: duckdb.DuckDBPyConnection,
    table_name: str,
    row: dict[str, object],
) -> bool:
    columns = list(row.keys())
    column_sql = ", ".join(columns)
    placeholder_sql = ", ".join("?" for _ in columns)

    before_count = int(
        connection.execute(f"SELECT COUNT(*) FROM {table_name}").fetchone()[0]
    )
    connection.execute(
        f"""
        INSERT INTO {table_name} ({column_sql})
        VALUES ({placeholder_sql})
        ON CONFLICT DO NOTHING
        """,
        [row[column] for column in columns],
    )
    after_count = int(
        connection.execute(f"SELECT COUNT(*) FROM {table_name}").fetchone()[0]
    )
    return after_count > before_count


def _seed_dev_dataset(
    connection: duckdb.DuckDBPyConnection,
    fixture_path: Path,
) -> bool:
    fixture = load_json_fixture(fixture_path)
    latest_snapshot_id = str(fixture["snapshot_id"])
    latest_raw_snapshot_id = str(fixture["raw_snapshot_id"])
    latest_published_at = str(fixture["generated_at"])
    latest_trade_date = str(fixture["market_overview"]["trade_date"])
    latest_price_basis = str(fixture["price_basis"])
    latest_task_status = dict(fixture["task_status"])
    last_run = str(latest_task_status.get("last_run", latest_published_at))
    next_window = str(latest_task_status.get("next_window", ""))

    previous_snapshot_id = "snapshot_2026-03-26_ready_001"
    previous_raw_snapshot_id = "raw_snapshot_2026-03-26_close_001"
    previous_trade_date = "2026-03-26"
    previous_published_at = "2026-03-26T18:06:00+08:00"
    previous_raw_created_at = "2026-03-26T18:05:00+08:00"

    latest_raw_snapshot_row = {
        "raw_snapshot_id": latest_raw_snapshot_id,
        "snapshot_seq": 2,
        "biz_date": latest_trade_date,
        "status": "READY",
        "required_datasets_json": json.dumps(
            ["stock_basic", "trade_calendar", "daily_bar"],
            ensure_ascii=False,
        ),
        "completeness_json": json.dumps(
            {
                "stock_basic": "READY",
                "trade_calendar": "READY",
                "daily_bar": "READY",
            },
            ensure_ascii=False,
        ),
        "source_watermark_json": json.dumps(
            {
                "daily_bar": "2026-03-27T15:30:00+08:00",
                "seed": "deterministic dev seed",
            },
            ensure_ascii=False,
        ),
        "created_at": latest_published_at,
        "attempt_no": 1,
    }
    previous_raw_snapshot_row = {
        "raw_snapshot_id": previous_raw_snapshot_id,
        "snapshot_seq": 1,
        "biz_date": previous_trade_date,
        "status": "READY",
        "required_datasets_json": json.dumps(
            ["stock_basic", "trade_calendar", "daily_bar"],
            ensure_ascii=False,
        ),
        "completeness_json": json.dumps(
            {
                "stock_basic": "READY",
                "trade_calendar": "READY",
                "daily_bar": "READY",
            },
            ensure_ascii=False,
        ),
        "source_watermark_json": json.dumps(
            {
                "daily_bar": "2026-03-26T15:30:00+08:00",
                "seed": "deterministic dev seed",
            },
            ensure_ascii=False,
        ),
        "created_at": previous_raw_created_at,
        "attempt_no": 1,
    }

    latest_artifact_row = {
        "snapshot_id": latest_snapshot_id,
        "publish_seq": 2,
        "biz_date": latest_trade_date,
        "raw_snapshot_id": latest_raw_snapshot_id,
        "status": str(fixture["status"]),
        "price_basis": latest_price_basis,
        "required_artifacts_json": json.dumps(
            [
                "price_series_daily",
                "market_regime_daily",
                "screener_run",
                "screener_result",
                "backtest_request",
                "backtest_run",
                "backtest_trade",
                "backtest_equity_curve",
                "task_run_log",
            ],
            ensure_ascii=False,
        ),
        "artifact_status_json": json.dumps(
            {
                "price_series_daily": "READY",
                "market_regime_daily": "READY",
                "screener_run": "READY",
                "screener_result": "READY",
                "backtest_request": "READY",
                "backtest_run": "READY",
                "backtest_trade": "READY",
                "backtest_equity_curve": "READY",
                "task_run_log": "READY",
            },
            ensure_ascii=False,
        ),
        "published_at": latest_published_at,
        "attempt_no": 1,
    }
    previous_artifact_row = {
        "snapshot_id": previous_snapshot_id,
        "publish_seq": 1,
        "biz_date": previous_trade_date,
        "raw_snapshot_id": previous_raw_snapshot_id,
        "status": "READY",
        "price_basis": latest_price_basis,
        "required_artifacts_json": json.dumps(
            ["price_series_daily"],
            ensure_ascii=False,
        ),
        "artifact_status_json": json.dumps(
            {"price_series_daily": "READY"},
            ensure_ascii=False,
        ),
        "published_at": previous_published_at,
        "attempt_no": 1,
    }

    seeded_any = False
    seeded_any |= _insert_row(connection, "raw_snapshot", previous_raw_snapshot_row)
    seeded_any |= _insert_row(connection, "raw_snapshot", latest_raw_snapshot_row)
    seeded_any |= _insert_row(connection, "artifact_publish", previous_artifact_row)
    seeded_any |= _insert_row(connection, "artifact_publish", latest_artifact_row)

    stock_profiles = {
        "300750.SZ": {
            "display_name": "宁德时代",
            "exchange": "SZ",
            "board": "创业板",
            "industry": "电力设备",
        },
        "002475.SZ": {
            "display_name": "立讯精密",
            "exchange": "SZ",
            "board": "主板",
            "industry": "消费电子",
        },
        "688017.SH": {
            "display_name": "绿的谐波",
            "exchange": "SH",
            "board": "科创板",
            "industry": "机器人",
        },
    }

    for symbol, profile in stock_profiles.items():
        seeded_any |= _insert_row(
            connection,
            "stock_basic",
            {
                "symbol": symbol,
                "display_name": profile["display_name"],
                "exchange": profile["exchange"],
                "board": profile["board"],
                "industry": profile["industry"],
                "is_active": True,
                "listed_at": None,
                "updated_at": latest_published_at,
            },
        )

    for trade_date, updated_at in (
        ("2026-03-25", previous_raw_created_at),
        ("2026-03-26", previous_raw_created_at),
        ("2026-03-27", latest_published_at),
    ):
        seeded_any |= _insert_row(
            connection,
            "trade_calendar",
            {
                "trade_date": trade_date,
                "market_code": "CN-A",
                "is_open": True,
                "updated_at": updated_at,
            },
        )

    market_overview = dict(fixture["market_overview"])
    seeded_any |= _insert_row(
        connection,
        "market_regime_daily",
        {
            "snapshot_id": latest_snapshot_id,
            "trade_date": latest_trade_date,
            "summary": str(market_overview["summary"]),
            "regime_label": str(market_overview["regime_label"]),
            "snapshot_source": str(market_overview["snapshot_source"]),
            "indices_json": json.dumps(market_overview["indices"], ensure_ascii=False),
            "breadth_json": json.dumps(market_overview["breadth"], ensure_ascii=False),
            "highlights_json": json.dumps(market_overview["highlights"], ensure_ascii=False),
        },
    )

    for task_name, task_state in latest_task_status.items():
        if task_name in {"last_run", "next_window"}:
            continue

        detail: dict[str, object] = {}
        if task_name == "data_update" and next_window:
            detail["next_window"] = next_window

        seeded_any |= _insert_row(
            connection,
            "task_run_log",
            {
                "task_id": f"{latest_snapshot_id}:{task_name}:1",
                "task_name": task_name,
                "biz_date": latest_trade_date,
                "snapshot_id": latest_snapshot_id,
                "attempt_no": 1,
                "status": str(task_state),
                "error_code": None,
                "error_message": None,
                "started_at": last_run,
                "finished_at": last_run,
                "detail_json": json.dumps(detail, ensure_ascii=False) if detail else None,
            },
        )

    for daily_bar_row in _build_seed_daily_bar_rows(
        previous_raw_snapshot_id=previous_raw_snapshot_id,
        previous_updated_at=previous_raw_created_at,
        latest_raw_snapshot_id=latest_raw_snapshot_id,
        latest_updated_at=latest_published_at,
    ):
        seeded_any |= _insert_row(connection, "daily_bar", daily_bar_row)

    for price_series_row in _build_seed_price_series_rows(
        previous_snapshot_id=previous_snapshot_id,
        previous_updated_at=previous_published_at,
        latest_snapshot_id=latest_snapshot_id,
        latest_updated_at=latest_published_at,
        price_basis=latest_price_basis,
    ):
        seeded_any |= _insert_row(connection, "price_series_daily", price_series_row)

    return seeded_any


def _build_seed_daily_bar_rows(
    *,
    previous_raw_snapshot_id: str,
    previous_updated_at: str,
    latest_raw_snapshot_id: str,
    latest_updated_at: str,
) -> list[dict[str, object]]:
    return [
        {
            "raw_snapshot_id": previous_raw_snapshot_id,
            "symbol": "300750.SZ",
            "trade_date": "2026-03-25",
            "open_raw": 248.10,
            "high_raw": 252.80,
            "low_raw": 247.00,
            "close_raw": 250.30,
            "pre_close_raw": 247.50,
            "volume": 15234500.0,
            "amount": 3824500000.0,
            "turnover_rate": 1.23,
            "high_limit": 297.00,
            "low_limit": 198.00,
            "limit_rule_code": "20pct",
            "is_suspended": False,
            "source": "dev-seed-initial",
            "updated_at": previous_updated_at,
        },
        {
            "raw_snapshot_id": previous_raw_snapshot_id,
            "symbol": "300750.SZ",
            "trade_date": "2026-03-26",
            "open_raw": 252.60,
            "high_raw": 258.00,
            "low_raw": 251.80,
            "close_raw": 257.40,
            "pre_close_raw": 250.30,
            "volume": 18432100.0,
            "amount": 4652000000.0,
            "turnover_rate": 1.49,
            "high_limit": 300.36,
            "low_limit": 200.24,
            "limit_rule_code": "20pct",
            "is_suspended": False,
            "source": "dev-seed-initial",
            "updated_at": previous_updated_at,
        },
        {
            "raw_snapshot_id": previous_raw_snapshot_id,
            "symbol": "002475.SZ",
            "trade_date": "2026-03-25",
            "open_raw": 34.15,
            "high_raw": 34.98,
            "low_raw": 33.92,
            "close_raw": 34.82,
            "pre_close_raw": 34.10,
            "volume": 26543000.0,
            "amount": 918600000.0,
            "turnover_rate": 2.08,
            "high_limit": 37.51,
            "low_limit": 30.69,
            "limit_rule_code": "10pct",
            "is_suspended": False,
            "source": "dev-seed-initial",
            "updated_at": previous_updated_at,
        },
        {
            "raw_snapshot_id": previous_raw_snapshot_id,
            "symbol": "002475.SZ",
            "trade_date": "2026-03-26",
            "open_raw": 34.90,
            "high_raw": 36.10,
            "low_raw": 34.76,
            "close_raw": 35.94,
            "pre_close_raw": 34.82,
            "volume": 31287000.0,
            "amount": 1115300000.0,
            "turnover_rate": 2.46,
            "high_limit": 38.30,
            "low_limit": 31.34,
            "limit_rule_code": "10pct",
            "is_suspended": False,
            "source": "dev-seed-initial",
            "updated_at": previous_updated_at,
        },
        {
            "raw_snapshot_id": previous_raw_snapshot_id,
            "symbol": "688017.SH",
            "trade_date": "2026-03-25",
            "open_raw": 122.50,
            "high_raw": 126.10,
            "low_raw": 121.90,
            "close_raw": 125.60,
            "pre_close_raw": 121.40,
            "volume": 5432100.0,
            "amount": 678200000.0,
            "turnover_rate": 3.41,
            "high_limit": 145.68,
            "low_limit": 97.12,
            "limit_rule_code": "20pct",
            "is_suspended": False,
            "source": "dev-seed-initial",
            "updated_at": previous_updated_at,
        },
        {
            "raw_snapshot_id": previous_raw_snapshot_id,
            "symbol": "688017.SH",
            "trade_date": "2026-03-26",
            "open_raw": 125.90,
            "high_raw": 130.40,
            "low_raw": 124.80,
            "close_raw": 129.40,
            "pre_close_raw": 125.60,
            "volume": 6387000.0,
            "amount": 823500000.0,
            "turnover_rate": 4.01,
            "high_limit": 150.72,
            "low_limit": 100.48,
            "limit_rule_code": "20pct",
            "is_suspended": False,
            "source": "dev-seed-initial",
            "updated_at": previous_updated_at,
        },
        {
            "raw_snapshot_id": latest_raw_snapshot_id,
            "symbol": "300750.SZ",
            "trade_date": "2026-03-26",
            "open_raw": 252.60,
            "high_raw": 258.60,
            "low_raw": 251.80,
            "close_raw": 258.10,
            "pre_close_raw": 250.30,
            "volume": 18678000.0,
            "amount": 4711000000.0,
            "turnover_rate": 1.51,
            "high_limit": 300.36,
            "low_limit": 200.24,
            "limit_rule_code": "20pct",
            "is_suspended": False,
            "source": "dev-seed-revision",
            "updated_at": latest_updated_at,
        },
        {
            "raw_snapshot_id": latest_raw_snapshot_id,
            "symbol": "300750.SZ",
            "trade_date": "2026-03-27",
            "open_raw": 258.90,
            "high_raw": 264.50,
            "low_raw": 257.80,
            "close_raw": 263.80,
            "pre_close_raw": 258.10,
            "volume": 21987000.0,
            "amount": 5762000000.0,
            "turnover_rate": 1.78,
            "high_limit": 309.72,
            "low_limit": 206.48,
            "limit_rule_code": "20pct",
            "is_suspended": False,
            "source": "dev-seed-latest",
            "updated_at": latest_updated_at,
        },
        {
            "raw_snapshot_id": latest_raw_snapshot_id,
            "symbol": "002475.SZ",
            "trade_date": "2026-03-27",
            "open_raw": 36.00,
            "high_raw": 36.88,
            "low_raw": 35.72,
            "close_raw": 36.55,
            "pre_close_raw": 35.94,
            "volume": 29876000.0,
            "amount": 1085400000.0,
            "turnover_rate": 2.34,
            "high_limit": 39.53,
            "low_limit": 32.35,
            "limit_rule_code": "10pct",
            "is_suspended": False,
            "source": "dev-seed-latest",
            "updated_at": latest_updated_at,
        },
        {
            "raw_snapshot_id": latest_raw_snapshot_id,
            "symbol": "688017.SH",
            "trade_date": "2026-03-27",
            "open_raw": 129.80,
            "high_raw": 134.90,
            "low_raw": 128.90,
            "close_raw": 133.20,
            "pre_close_raw": 129.40,
            "volume": 7123400.0,
            "amount": 947600000.0,
            "turnover_rate": 4.47,
            "high_limit": 155.28,
            "low_limit": 103.52,
            "limit_rule_code": "20pct",
            "is_suspended": False,
            "source": "dev-seed-latest",
            "updated_at": latest_updated_at,
        },
    ]


def _build_seed_price_series_rows(
    *,
    previous_snapshot_id: str,
    previous_updated_at: str,
    latest_snapshot_id: str,
    latest_updated_at: str,
    price_basis: str,
) -> list[dict[str, object]]:
    return [
        {
            "snapshot_id": previous_snapshot_id,
            "symbol": "300750.SZ",
            "trade_date": "2026-03-25",
            "price_basis": price_basis,
            "open": 248.60,
            "high": 253.20,
            "low": 247.40,
            "close": 251.20,
            "pre_close": 248.10,
            "adj_factor": 1.0036,
            "volume": 15234500.0,
            "amount": 3824500000.0,
            "updated_at": previous_updated_at,
        },
        {
            "snapshot_id": previous_snapshot_id,
            "symbol": "300750.SZ",
            "trade_date": "2026-03-26",
            "price_basis": price_basis,
            "open": 253.10,
            "high": 258.40,
            "low": 252.30,
            "close": 259.20,
            "pre_close": 251.20,
            "adj_factor": 1.0070,
            "volume": 18432100.0,
            "amount": 4652000000.0,
            "updated_at": previous_updated_at,
        },
        {
            "snapshot_id": previous_snapshot_id,
            "symbol": "002475.SZ",
            "trade_date": "2026-03-25",
            "price_basis": price_basis,
            "open": 34.22,
            "high": 35.02,
            "low": 33.98,
            "close": 34.88,
            "pre_close": 34.16,
            "adj_factor": 1.0019,
            "volume": 26543000.0,
            "amount": 918600000.0,
            "updated_at": previous_updated_at,
        },
        {
            "snapshot_id": previous_snapshot_id,
            "symbol": "002475.SZ",
            "trade_date": "2026-03-26",
            "price_basis": price_basis,
            "open": 34.96,
            "high": 36.18,
            "low": 34.82,
            "close": 36.02,
            "pre_close": 34.88,
            "adj_factor": 1.0030,
            "volume": 31287000.0,
            "amount": 1115300000.0,
            "updated_at": previous_updated_at,
        },
        {
            "snapshot_id": previous_snapshot_id,
            "symbol": "688017.SH",
            "trade_date": "2026-03-25",
            "price_basis": price_basis,
            "open": 122.90,
            "high": 126.40,
            "low": 122.20,
            "close": 125.90,
            "pre_close": 121.70,
            "adj_factor": 1.0000,
            "volume": 5432100.0,
            "amount": 678200000.0,
            "updated_at": previous_updated_at,
        },
        {
            "snapshot_id": previous_snapshot_id,
            "symbol": "688017.SH",
            "trade_date": "2026-03-26",
            "price_basis": price_basis,
            "open": 126.10,
            "high": 130.70,
            "low": 125.20,
            "close": 129.90,
            "pre_close": 125.90,
            "adj_factor": 1.0000,
            "volume": 6387000.0,
            "amount": 823500000.0,
            "updated_at": previous_updated_at,
        },
        {
            "snapshot_id": latest_snapshot_id,
            "symbol": "300750.SZ",
            "trade_date": "2026-03-26",
            "price_basis": price_basis,
            "open": 253.10,
            "high": 259.10,
            "low": 252.30,
            "close": 260.10,
            "pre_close": 251.20,
            "adj_factor": 1.0105,
            "volume": 18678000.0,
            "amount": 4711000000.0,
            "updated_at": latest_updated_at,
        },
        {
            "snapshot_id": latest_snapshot_id,
            "symbol": "300750.SZ",
            "trade_date": "2026-03-27",
            "price_basis": price_basis,
            "open": 260.80,
            "high": 266.90,
            "low": 259.70,
            "close": 266.40,
            "pre_close": 260.10,
            "adj_factor": 1.0141,
            "volume": 21987000.0,
            "amount": 5762000000.0,
            "updated_at": latest_updated_at,
        },
        {
            "snapshot_id": latest_snapshot_id,
            "symbol": "002475.SZ",
            "trade_date": "2026-03-27",
            "price_basis": price_basis,
            "open": 36.08,
            "high": 36.95,
            "low": 35.80,
            "close": 36.61,
            "pre_close": 36.02,
            "adj_factor": 1.0044,
            "volume": 29876000.0,
            "amount": 1085400000.0,
            "updated_at": latest_updated_at,
        },
        {
            "snapshot_id": latest_snapshot_id,
            "symbol": "688017.SH",
            "trade_date": "2026-03-27",
            "price_basis": price_basis,
            "open": 130.20,
            "high": 135.20,
            "low": 129.30,
            "close": 133.80,
            "pre_close": 129.90,
            "adj_factor": 1.0000,
            "volume": 7123400.0,
            "amount": 947600000.0,
            "updated_at": latest_updated_at,
        },
    ]


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Bootstrap QuantA's local DuckDB dev dataset."
    )
    parser.add_argument(
        "--print-summary",
        action="store_true",
        help="Print the seeded DuckDB path and per-table row counts.",
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    settings = load_settings()
    summary = ensure_dev_duckdb(settings)

    if args.print_summary:
        print("QuantA DuckDB dev foundation ready:")
        print(f"- duckdb_path: {summary['duckdb_path']}")
        print(f"- seed_fixture_path: {summary['seed_fixture_path']}")
        print(f"- rebuilt: {summary['rebuilt']}")
        print(f"- seeded: {summary['seeded']}")
        changed_tables = summary["changed_tables"]
        print(
            "- changed_tables:",
            ", ".join(changed_tables) if changed_tables else "none",
        )
        for table_name, row_count in summary["table_counts"].items():
            print(f"- {table_name}: {row_count}")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
