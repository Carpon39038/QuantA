from __future__ import annotations

import argparse
import json
from pathlib import Path

from backend.app.app_wiring.settings import AppSettings, load_settings
from backend.app.domains.market_data.schema import TABLE_DEFINITIONS, iter_ddl_statements
from backend.app.domains.tasking.bootstrap import ensure_runtime_directories
from backend.app.shared.providers.duckdb import connect_duckdb
from backend.app.shared.providers.local_fixture import load_json_fixture


def ensure_dev_duckdb(settings: AppSettings) -> dict[str, object]:
    ensure_runtime_directories(settings)

    connection = connect_duckdb(settings.duckdb_path)
    try:
        for statement in iter_ddl_statements():
            connection.execute(statement)

        seeded = _seed_dev_dataset_if_empty(connection, settings.fixture_path)
        table_counts = {
            table.name: int(
                connection.execute(f"SELECT COUNT(*) FROM {table.name}").fetchone()[0]
            )
            for table in TABLE_DEFINITIONS
        }
    finally:
        connection.close()

    return {
        "duckdb_path": str(settings.duckdb_path),
        "seed_fixture_path": str(settings.fixture_path),
        "seeded": seeded,
        "table_counts": table_counts,
    }


def _seed_dev_dataset_if_empty(connection: object, fixture_path: Path) -> bool:
    artifact_count = int(connection.execute("SELECT COUNT(*) FROM artifact_publish").fetchone()[0])
    if artifact_count > 0:
        return False

    fixture = load_json_fixture(fixture_path)
    snapshot_id = str(fixture["snapshot_id"])
    raw_snapshot_id = str(fixture["raw_snapshot_id"])
    generated_at = str(fixture["generated_at"])
    trade_date = str(fixture["market_overview"]["trade_date"])
    price_basis = str(fixture["price_basis"])
    task_status = dict(fixture["task_status"])
    last_run = str(task_status.get("last_run", generated_at))
    next_window = str(task_status.get("next_window", ""))

    connection.execute(
        """
        INSERT INTO raw_snapshot (
          raw_snapshot_id,
          biz_date,
          status,
          source_name,
          created_at,
          notes_json
        ) VALUES (?, ?, ?, ?, ?, ?)
        """,
        [
            raw_snapshot_id,
            trade_date,
            "READY",
            "dev-seed-fixture",
            generated_at,
            json.dumps({"seed_fixture_path": str(fixture_path)}, ensure_ascii=False),
        ],
    )

    connection.execute(
        """
        INSERT INTO artifact_publish (
          snapshot_id,
          publish_seq,
          biz_date,
          raw_snapshot_id,
          status,
          price_basis,
          required_artifacts_json,
          artifact_status_json,
          published_at,
          attempt_no
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        [
            snapshot_id,
            1,
            trade_date,
            raw_snapshot_id,
            str(fixture["status"]),
            price_basis,
            json.dumps(
                [
                    "market_regime_daily",
                    "screener_run",
                    "screener_result",
                    "backtest_run",
                    "task_run_log",
                ],
                ensure_ascii=False,
            ),
            json.dumps(
                {
                    "market_regime_daily": "READY",
                    "screener_run": "READY",
                    "screener_result": "READY",
                    "backtest_run": "READY",
                    "task_run_log": "READY",
                },
                ensure_ascii=False,
            ),
            generated_at,
            1,
        ],
    )

    candidates = list(fixture["screener"]["top_candidates"])
    for candidate in candidates:
        symbol = str(candidate["symbol"])
        exchange = symbol.split(".")[-1]
        board = "创业板" if symbol.startswith("300") else "科创板" if symbol.startswith("688") else "主板"
        connection.execute(
            """
            INSERT INTO stock_basic (
              symbol,
              display_name,
              exchange,
              board,
              industry,
              is_active,
              listed_at,
              updated_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """,
            [
                symbol,
                str(candidate["name"]),
                exchange,
                board,
                "待补充",
                True,
                None,
                generated_at,
            ],
        )

    connection.execute(
        """
        INSERT INTO trade_calendar (
          trade_date,
          market_code,
          is_open,
          updated_at
        ) VALUES (?, ?, ?, ?)
        """,
        [trade_date, "CN-A", True, generated_at],
    )

    market_overview = dict(fixture["market_overview"])
    connection.execute(
        """
        INSERT INTO market_regime_daily (
          snapshot_id,
          trade_date,
          summary,
          regime_label,
          snapshot_source,
          indices_json,
          breadth_json,
          highlights_json
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        """,
        [
            snapshot_id,
            trade_date,
            str(market_overview["summary"]),
            str(market_overview["regime_label"]),
            str(market_overview["snapshot_source"]),
            json.dumps(market_overview["indices"], ensure_ascii=False),
            json.dumps(market_overview["breadth"], ensure_ascii=False),
            json.dumps(market_overview["highlights"], ensure_ascii=False),
        ],
    )

    screener_run_id = f"screener_run_{trade_date.replace('-', '')}_001"
    connection.execute(
        """
        INSERT INTO screener_run (
          run_id,
          trade_date,
          snapshot_id,
          strategy_name,
          strategy_version,
          signal_price_basis,
          universe_size,
          result_count,
          status,
          as_of_date,
          started_at,
          finished_at
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        [
            screener_run_id,
            trade_date,
            snapshot_id,
            str(fixture["screener"]["strategy_name"]),
            "dev-seed-v1",
            price_basis,
            len(candidates),
            len(candidates),
            "SUCCESS",
            str(fixture["screener"]["as_of_date"]),
            generated_at,
            generated_at,
        ],
    )

    for rank_no, candidate in enumerate(candidates, start=1):
        connection.execute(
            """
            INSERT INTO screener_result (
              run_id,
              symbol,
              trade_date,
              strategy_name,
              snapshot_id,
              signal_price_basis,
              total_score,
              display_name,
              thesis,
              matched_rules_json,
              risk_flags_json,
              rank_no
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            [
                screener_run_id,
                str(candidate["symbol"]),
                trade_date,
                str(fixture["screener"]["strategy_name"]),
                snapshot_id,
                price_basis,
                int(candidate["score"]),
                str(candidate["name"]),
                str(candidate["thesis"]),
                json.dumps(candidate["signals"], ensure_ascii=False),
                json.dumps(candidate["risks"], ensure_ascii=False),
                rank_no,
            ],
        )

    backtest_id = f"backtest_run_{trade_date.replace('-', '')}_001"
    window_start, _, window_end = str(fixture["backtest"]["window"]).partition(" to ")
    backtest_metrics = dict(fixture["backtest"]["metrics"])
    connection.execute(
        """
        INSERT INTO backtest_run (
          backtest_id,
          strategy_name,
          strategy_version,
          param_json,
          snapshot_id,
          raw_snapshot_id,
          signal_price_basis,
          execution_price_basis,
          cost_model_json,
          engine_version,
          start_date,
          end_date,
          benchmark,
          total_return,
          annual_return,
          max_drawdown,
          win_rate,
          profit_loss_ratio,
          status,
          created_at,
          notes_json
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        [
            backtest_id,
            str(fixture["backtest"]["strategy_name"]),
            "dev-seed-v1",
            json.dumps({}, ensure_ascii=False),
            snapshot_id,
            raw_snapshot_id,
            price_basis,
            "raw",
            json.dumps({"fees_included": True, "stamp_duty_included": True}, ensure_ascii=False),
            "dev-seed-v1",
            window_start,
            window_end,
            "000300.SH",
            None,
            float(backtest_metrics["cagr_pct"]),
            float(backtest_metrics["max_drawdown_pct"]),
            float(backtest_metrics["win_rate_pct"]),
            float(backtest_metrics["profit_factor"]),
            "SUCCESS",
            generated_at,
            json.dumps(fixture["backtest"]["notes"], ensure_ascii=False),
        ],
    )

    for task_name, task_state in task_status.items():
        if task_name in {"last_run", "next_window"}:
            continue

        detail = {}
        if task_name == "data_update" and next_window:
            detail["next_window"] = next_window

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
                f"{snapshot_id}:{task_name}:1",
                task_name,
                trade_date,
                snapshot_id,
                1,
                str(task_state),
                None,
                None,
                last_run,
                last_run,
                json.dumps(detail, ensure_ascii=False) if detail else None,
            ],
        )

    return True


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
        print(f"- seeded: {summary['seeded']}")
        for table_name, row_count in summary["table_counts"].items():
            print(f"- {table_name}: {row_count}")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
