from __future__ import annotations

import argparse
from datetime import datetime, timedelta, timezone
import json

from backend.app.app_wiring.settings import AppSettings, load_settings
from backend.app.domains.analysis.bootstrap import materialize_analysis_snapshot
from backend.app.domains.market_data.bootstrap import ensure_dev_duckdb
from backend.app.domains.tasking.bootstrap import ensure_runtime_directories
from backend.app.shared.providers.duckdb import connect_duckdb
from backend.app.shared.providers.market_data_source import build_market_data_provider


CN_TZ = timezone(timedelta(hours=8))


def sync_market_data(
    settings: AppSettings,
    *,
    biz_date: str | None = None,
) -> dict[str, object]:
    ensure_runtime_directories(settings)
    ensure_dev_duckdb(settings)

    provider = build_market_data_provider(settings)
    _consume_simulated_source_failure(settings, biz_date=biz_date)
    source_snapshot = provider.fetch_daily_snapshot(biz_date=biz_date)
    if not source_snapshot.daily_bars:
        raise RuntimeError(
            f"Source provider {source_snapshot.provider} returned an empty daily snapshot "
            f"for biz_date={source_snapshot.biz_date}"
        )

    connection = connect_duckdb(settings.duckdb_path)
    try:
        publish_seq = _next_publish_seq(connection)
        snapshot_seq = _next_snapshot_seq(connection)
        raw_snapshot_id = f"raw_snapshot_{source_snapshot.biz_date}_close_{snapshot_seq:03d}"
        snapshot_id = f"snapshot_{source_snapshot.biz_date}_ready_{publish_seq:03d}"
        published_at = source_snapshot.fetched_at

        _upsert_stock_basic_rows(
            connection,
            rows=list(source_snapshot.stock_basic),
            updated_at=published_at,
        )
        _upsert_trade_calendar_row(
            connection,
            row=dict(source_snapshot.trade_calendar),
            updated_at=published_at,
        )

        connection.execute(
            """
            INSERT INTO raw_snapshot (
              raw_snapshot_id,
              snapshot_seq,
              biz_date,
              status,
              required_datasets_json,
              completeness_json,
              source_watermark_json,
              created_at,
              attempt_no
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            [
                raw_snapshot_id,
                snapshot_seq,
                source_snapshot.biz_date,
                "READY",
                json.dumps(["stock_basic", "trade_calendar", "daily_bar"], ensure_ascii=False),
                json.dumps(
                    {
                        "stock_basic": "READY",
                        "trade_calendar": "READY",
                        "daily_bar": "READY",
                    },
                    ensure_ascii=False,
                ),
                json.dumps(
                    {
                        **source_snapshot.source_watermark,
                        "provider": source_snapshot.provider,
                        "source": source_snapshot.source,
                        "fetched_at": source_snapshot.fetched_at,
                    },
                    ensure_ascii=False,
                ),
                published_at,
                1,
            ],
        )

        _insert_daily_bar_rows(
            connection,
            raw_snapshot_id=raw_snapshot_id,
            rows=list(source_snapshot.daily_bars),
            updated_at=published_at,
            source=source_snapshot.source,
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
                publish_seq,
                source_snapshot.biz_date,
                raw_snapshot_id,
                "BUILDING",
                source_snapshot.price_basis,
                json.dumps(
                    [
                        "price_series_daily",
                        "market_regime_daily",
                        "indicator_daily",
                        "pattern_signal_daily",
                        "capital_feature_daily",
                        "fundamental_feature_daily",
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
                json.dumps(
                    {
                        "price_series_daily": "PENDING",
                        "market_regime_daily": "PENDING",
                        "indicator_daily": "PENDING",
                        "pattern_signal_daily": "PENDING",
                        "capital_feature_daily": "PENDING",
                        "fundamental_feature_daily": "PENDING",
                        "screener_run": "PENDING",
                        "screener_result": "PENDING",
                        "backtest_request": "PENDING",
                        "backtest_run": "PENDING",
                        "backtest_trade": "PENDING",
                        "backtest_equity_curve": "PENDING",
                        "task_run_log": "PENDING",
                    },
                    ensure_ascii=False,
                ),
                published_at,
                1,
            ],
        )

        price_series_count = _materialize_price_series_snapshot(
            connection,
            snapshot_id=snapshot_id,
            raw_snapshot_id=raw_snapshot_id,
            price_basis=source_snapshot.price_basis,
            updated_at=published_at,
        )
        market_regime_count = _materialize_market_overview_snapshot(
            connection,
            snapshot_id=snapshot_id,
            market_overview=source_snapshot.market_overview,
        )
        analysis_counts = materialize_analysis_snapshot(
            connection,
            snapshot_id=snapshot_id,
            price_basis=source_snapshot.price_basis,
            updated_at=published_at,
            capital_feature_overrides=source_snapshot.capital_feature_overrides,
            fundamental_feature_overrides=source_snapshot.fundamental_feature_overrides,
        )
        _update_artifact_publish_status(
            connection,
            snapshot_id=snapshot_id,
            status="BUILDING",
            artifact_status={
                "price_series_daily": "READY",
                "market_regime_daily": "READY",
                "indicator_daily": "READY",
                "pattern_signal_daily": "READY",
                "capital_feature_daily": "READY",
                "fundamental_feature_daily": "READY",
                "screener_run": "PENDING",
                "screener_result": "PENDING",
                "backtest_request": "PENDING",
                "backtest_run": "PENDING",
                "backtest_trade": "PENDING",
                "backtest_equity_curve": "PENDING",
                "task_run_log": "PENDING",
            },
            published_at=published_at,
        )
    finally:
        connection.close()

    return {
        "provider": source_snapshot.provider,
        "source": source_snapshot.source,
        "biz_date": source_snapshot.biz_date,
        "snapshot_id": snapshot_id,
        "raw_snapshot_id": raw_snapshot_id,
        "published_at": published_at,
        "status": "BUILDING",
        "inserted": {
            "stock_basic": len(source_snapshot.stock_basic),
            "trade_calendar": 1,
            "daily_bar": len(source_snapshot.daily_bars),
            "price_series_daily": price_series_count,
            "market_regime_daily": market_regime_count,
            **analysis_counts,
        },
    }


def load_latest_building_snapshot(settings: AppSettings) -> dict[str, object] | None:
    connection = connect_duckdb(settings.duckdb_path, read_only=True)
    try:
        row = connection.execute(
            """
            SELECT snapshot_id, raw_snapshot_id, biz_date, price_basis, published_at
            FROM artifact_publish
            WHERE status = 'BUILDING'
            ORDER BY publish_seq DESC
            LIMIT 1
            """
        ).fetchone()
        if row is None:
            return None
        snapshot_id, raw_snapshot_id, biz_date, price_basis, published_at = row
        return {
            "snapshot_id": str(snapshot_id),
            "raw_snapshot_id": str(raw_snapshot_id),
            "biz_date": str(biz_date),
            "price_basis": str(price_basis),
            "published_at": str(published_at),
        }
    finally:
        connection.close()


def finalize_snapshot_publish(
    settings: AppSettings,
    *,
    snapshot_id: str,
) -> None:
    connection = connect_duckdb(settings.duckdb_path)
    try:
        row = connection.execute(
            """
            SELECT artifact_status_json, published_at
            FROM artifact_publish
            WHERE snapshot_id = ?
            LIMIT 1
            """,
            [snapshot_id],
        ).fetchone()
        if row is None:
            raise LookupError(f"Unknown snapshot_id: {snapshot_id}")
        artifact_status_json, published_at = row
        artifact_status = json.loads(artifact_status_json)
        artifact_status["screener_run"] = "READY"
        artifact_status["screener_result"] = "READY"
        artifact_status["backtest_request"] = "READY"
        artifact_status["backtest_run"] = "READY"
        artifact_status["backtest_trade"] = "READY"
        artifact_status["backtest_equity_curve"] = "READY"
        artifact_status["task_run_log"] = "READY"
        _update_artifact_publish_status(
            connection,
            snapshot_id=snapshot_id,
            status="READY",
            artifact_status=artifact_status,
            published_at=str(published_at),
        )
    finally:
        connection.close()


def delete_snapshot_artifacts(
    settings: AppSettings,
    *,
    snapshot_id: str,
    raw_snapshot_id: str,
) -> None:
    connection = connect_duckdb(settings.duckdb_path)
    try:
        snapshot_row = connection.execute(
            """
            SELECT biz_date
            FROM artifact_publish
            WHERE snapshot_id = ?
            LIMIT 1
            """,
            [snapshot_id],
        ).fetchone()
        biz_date = str(snapshot_row[0]) if snapshot_row is not None else None
        run_id = f"screener_run_{snapshot_id.replace('-', '_')}"
        backtest_id = f"backtest_run_{snapshot_id.replace('-', '_')}"
        connection.execute("DELETE FROM task_run_log WHERE snapshot_id = ?", [snapshot_id])
        connection.execute("DELETE FROM backtest_equity_curve WHERE backtest_id = ?", [backtest_id])
        connection.execute("DELETE FROM backtest_trade WHERE backtest_id = ?", [backtest_id])
        connection.execute("DELETE FROM backtest_run WHERE backtest_id = ?", [backtest_id])
        connection.execute("DELETE FROM backtest_request WHERE backtest_id = ?", [backtest_id])
        connection.execute("DELETE FROM screener_result WHERE run_id = ?", [run_id])
        connection.execute("DELETE FROM screener_run WHERE run_id = ?", [run_id])
        connection.execute("DELETE FROM indicator_daily WHERE snapshot_id = ?", [snapshot_id])
        connection.execute("DELETE FROM pattern_signal_daily WHERE snapshot_id = ?", [snapshot_id])
        connection.execute("DELETE FROM capital_feature_daily WHERE snapshot_id = ?", [snapshot_id])
        connection.execute("DELETE FROM fundamental_feature_daily WHERE snapshot_id = ?", [snapshot_id])
        connection.execute("DELETE FROM market_regime_daily WHERE snapshot_id = ?", [snapshot_id])
        connection.execute("DELETE FROM price_series_daily WHERE snapshot_id = ?", [snapshot_id])
        connection.execute("DELETE FROM artifact_publish WHERE snapshot_id = ?", [snapshot_id])
        connection.execute("DELETE FROM daily_bar WHERE raw_snapshot_id = ?", [raw_snapshot_id])
        connection.execute("DELETE FROM raw_snapshot WHERE raw_snapshot_id = ?", [raw_snapshot_id])
        if biz_date is not None:
            remaining_rows = connection.execute(
                """
                SELECT COUNT(*)
                FROM raw_snapshot
                WHERE biz_date = CAST(? AS DATE)
                """,
                [biz_date],
            ).fetchone()
            if remaining_rows is not None and int(remaining_rows[0]) == 0:
                connection.execute(
                    """
                    DELETE FROM trade_calendar
                    WHERE trade_date = CAST(? AS DATE)
                      AND market_code = 'CN-A'
                    """,
                    [biz_date],
                )
    finally:
        connection.close()


def latest_source_biz_date(settings: AppSettings) -> str:
    provider = build_market_data_provider(settings)
    return provider.latest_available_biz_date()


def _consume_simulated_source_failure(
    settings: AppSettings,
    *,
    biz_date: str | None,
) -> None:
    if settings.source_fail_first_n <= 0:
        return

    state_path = settings.logs_dir / "source-failure-state.json"
    state: dict[str, int] = {}
    if state_path.exists():
        state = json.loads(state_path.read_text(encoding="utf-8"))

    state_key = f"{settings.source_provider}:{biz_date or 'latest'}"
    remaining = int(state.get(state_key, settings.source_fail_first_n))
    if remaining <= 0:
        return

    state[state_key] = remaining - 1
    state_path.parent.mkdir(parents=True, exist_ok=True)
    state_path.write_text(json.dumps(state, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    raise RuntimeError(
        f"Simulated source failure for {state_key}; remaining_failures={remaining - 1}"
    )


def _next_snapshot_seq(connection) -> int:
    row = connection.execute("SELECT COALESCE(MAX(snapshot_seq), 0) FROM raw_snapshot").fetchone()
    return int(row[0]) + 1


def _next_publish_seq(connection) -> int:
    row = connection.execute("SELECT COALESCE(MAX(publish_seq), 0) FROM artifact_publish").fetchone()
    return int(row[0]) + 1


def _upsert_stock_basic_rows(connection, *, rows: list[dict[str, object]], updated_at: str) -> None:
    for row in rows:
        connection.execute("DELETE FROM stock_basic WHERE symbol = ?", [row["symbol"]])
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
                row["symbol"],
                row["display_name"],
                row["exchange"],
                row["board"],
                row["industry"],
                bool(row.get("is_active", True)),
                row.get("listed_at"),
                updated_at,
            ],
        )


def _upsert_trade_calendar_row(connection, *, row: dict[str, object], updated_at: str) -> None:
    connection.execute(
        "DELETE FROM trade_calendar WHERE trade_date = ? AND market_code = ?",
        [row["trade_date"], row.get("market_code", "CN-A")],
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
        [
            row["trade_date"],
            row.get("market_code", "CN-A"),
            bool(row.get("is_open", True)),
            updated_at,
        ],
    )


def _insert_daily_bar_rows(
    connection,
    *,
    raw_snapshot_id: str,
    rows: list[dict[str, object]],
    updated_at: str,
    source: str,
) -> None:
    for row in rows:
        connection.execute(
            """
            INSERT INTO daily_bar (
              raw_snapshot_id,
              symbol,
              trade_date,
              open_raw,
              high_raw,
              low_raw,
              close_raw,
              pre_close_raw,
              volume,
              amount,
              turnover_rate,
              high_limit,
              low_limit,
              limit_rule_code,
              is_suspended,
              source,
              updated_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            [
                raw_snapshot_id,
                row["symbol"],
                row["trade_date"],
                row["open_raw"],
                row["high_raw"],
                row["low_raw"],
                row["close_raw"],
                row.get("pre_close_raw"),
                row.get("volume"),
                row.get("amount"),
                row.get("turnover_rate"),
                row.get("high_limit"),
                row.get("low_limit"),
                row.get("limit_rule_code"),
                bool(row.get("is_suspended", False)),
                row.get("source", source),
                updated_at,
            ],
        )


def _materialize_price_series_snapshot(
    connection,
    *,
    snapshot_id: str,
    raw_snapshot_id: str,
    price_basis: str,
    updated_at: str,
) -> int:
    rows = connection.execute(
        """
        WITH target AS (
          SELECT snapshot_seq
          FROM raw_snapshot
          WHERE raw_snapshot_id = ?
        ),
        ranked AS (
          SELECT
            db.symbol,
            db.trade_date,
            db.open_raw,
            db.high_raw,
            db.low_raw,
            db.close_raw,
            db.pre_close_raw,
            db.volume,
            db.amount,
            ROW_NUMBER() OVER (
              PARTITION BY db.symbol, db.trade_date
              ORDER BY rs.snapshot_seq DESC
            ) AS row_num
          FROM daily_bar db
          JOIN raw_snapshot rs
            ON rs.raw_snapshot_id = db.raw_snapshot_id
          JOIN target
            ON rs.snapshot_seq <= target.snapshot_seq
        )
        SELECT
          symbol,
          trade_date,
          open_raw,
          high_raw,
          low_raw,
          close_raw,
          pre_close_raw,
          volume,
          amount
        FROM ranked
        WHERE row_num = 1
        ORDER BY symbol ASC, trade_date ASC
        """,
        [raw_snapshot_id],
    ).fetchall()

    connection.execute("DELETE FROM price_series_daily WHERE snapshot_id = ?", [snapshot_id])
    inserted = 0
    for symbol, trade_date, open_raw, high_raw, low_raw, close_raw, pre_close_raw, volume, amount in rows:
        connection.execute(
            """
            INSERT INTO price_series_daily (
              symbol,
              trade_date,
              price_basis,
              open,
              high,
              low,
              close,
              pre_close,
              adj_factor,
              snapshot_id,
              volume,
              amount,
              updated_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            [
                str(symbol),
                str(trade_date),
                price_basis,
                open_raw,
                high_raw,
                low_raw,
                close_raw,
                pre_close_raw,
                1.0,
                snapshot_id,
                volume,
                amount,
                updated_at,
            ],
        )
        inserted += 1
    return inserted


def _materialize_market_overview_snapshot(
    connection,
    *,
    snapshot_id: str,
    market_overview: dict[str, object],
) -> int:
    connection.execute("DELETE FROM market_regime_daily WHERE snapshot_id = ?", [snapshot_id])
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
            market_overview["trade_date"],
            market_overview["summary"],
            market_overview["regime_label"],
            market_overview["snapshot_source"],
            json.dumps(market_overview.get("indices", []), ensure_ascii=False),
            json.dumps(market_overview.get("breadth", {}), ensure_ascii=False),
            json.dumps(market_overview.get("highlights", []), ensure_ascii=False),
        ],
    )
    return 1


def _update_artifact_publish_status(
    connection,
    *,
    snapshot_id: str,
    status: str,
    artifact_status: dict[str, object],
    published_at: str,
) -> None:
    connection.execute(
        """
        UPDATE artifact_publish
        SET status = ?, artifact_status_json = ?, published_at = ?
        WHERE snapshot_id = ?
        """,
        [
            status,
            json.dumps(artifact_status, ensure_ascii=False),
            published_at,
            snapshot_id,
        ],
    )


def _print_summary(summary: dict[str, object]) -> None:
    print("QuantA market data sync complete:")
    print(f"- provider: {summary['provider']}")
    print(f"- source: {summary['source']}")
    print(f"- biz_date: {summary['biz_date']}")
    print(f"- raw_snapshot_id: {summary['raw_snapshot_id']}")
    print(f"- snapshot_id: {summary['snapshot_id']}")
    print(f"- status: {summary['status']}")
    for key, value in summary["inserted"].items():
        print(f"- inserted_{key}: {value}")


def main() -> int:
    parser = argparse.ArgumentParser(description="Sync market data from the configured source provider.")
    parser.add_argument("--biz-date", default=None, help="Optional target biz_date in YYYY-MM-DD format.")
    parser.add_argument("--print-summary", action="store_true", help="Print a short sync summary.")
    args = parser.parse_args()

    settings = load_settings()
    summary = sync_market_data(settings, biz_date=args.biz_date)
    if args.print_summary:
        _print_summary(summary)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
