from __future__ import annotations

import argparse
import json
import math
from statistics import fmean

from backend.app.app_wiring.settings import AppSettings, load_settings
from backend.app.domains.market_data.bootstrap import ensure_dev_duckdb
from backend.app.shared.providers.duckdb import connect_duckdb


def ensure_analysis_artifacts(settings: AppSettings) -> dict[str, object]:
    ensure_dev_duckdb(settings)

    connection = connect_duckdb(settings.duckdb_path)
    try:
        snapshot_rows = connection.execute(
            """
            SELECT snapshot_id, publish_seq, price_basis, published_at
            FROM artifact_publish
            WHERE status = 'READY'
            ORDER BY publish_seq ASC
            """
        ).fetchall()

        connection.execute("DELETE FROM indicator_daily")
        connection.execute("DELETE FROM pattern_signal_daily")
        connection.execute("DELETE FROM capital_feature_daily")
        connection.execute("DELETE FROM fundamental_feature_daily")

        inserted = {
            "indicator_daily": 0,
            "pattern_signal_daily": 0,
            "capital_feature_daily": 0,
            "fundamental_feature_daily": 0,
        }

        previous_indicator_rows: dict[tuple[str, str, str], dict[str, object]] = {}
        previous_pattern_rows: dict[tuple[str, str, str, str], dict[str, object]] = {}
        previous_capital_rows: dict[tuple[str, str], dict[str, object]] = {}
        previous_fundamental_rows: dict[tuple[str, str], dict[str, object]] = {}

        for snapshot_id, _, price_basis, published_at in snapshot_rows:
            series_rows = _load_price_series_asof_rows(
                connection,
                snapshot_id=str(snapshot_id),
                price_basis=str(price_basis),
            )

            grouped_rows = _group_rows_by_symbol(series_rows)
            indicator_rows = _build_indicator_rows(
                grouped_rows,
                snapshot_id=str(snapshot_id),
                price_basis=str(price_basis),
                updated_at=str(published_at),
            )
            capital_rows = _build_capital_feature_rows(
                grouped_rows,
                snapshot_id=str(snapshot_id),
                updated_at=str(published_at),
            )
            fundamental_rows = _build_fundamental_feature_rows(
                grouped_rows,
                snapshot_id=str(snapshot_id),
                updated_at=str(published_at),
            )
            pattern_rows = _build_pattern_signal_rows(
                grouped_rows,
                indicator_rows,
                snapshot_id=str(snapshot_id),
                price_basis=str(price_basis),
                updated_at=str(published_at),
            )

            delta_indicator_rows = _diff_rows(
                rows=indicator_rows,
                previous_rows=previous_indicator_rows,
                key_fields=("symbol", "trade_date", "price_basis"),
                ignore_fields=("snapshot_id", "updated_at"),
            )
            delta_capital_rows = _diff_rows(
                rows=capital_rows,
                previous_rows=previous_capital_rows,
                key_fields=("symbol", "trade_date"),
                ignore_fields=("snapshot_id", "updated_at"),
            )
            delta_pattern_rows = _diff_rows(
                rows=pattern_rows,
                previous_rows=previous_pattern_rows,
                key_fields=("symbol", "trade_date", "price_basis", "signal_code"),
                ignore_fields=("snapshot_id", "updated_at"),
            )
            delta_fundamental_rows = _diff_rows(
                rows=fundamental_rows,
                previous_rows=previous_fundamental_rows,
                key_fields=("symbol", "trade_date"),
                ignore_fields=("snapshot_id", "updated_at"),
            )

            inserted["indicator_daily"] += _insert_rows(
                connection,
                "indicator_daily",
                delta_indicator_rows,
            )
            inserted["capital_feature_daily"] += _insert_rows(
                connection,
                "capital_feature_daily",
                delta_capital_rows,
            )
            inserted["pattern_signal_daily"] += _insert_rows(
                connection,
                "pattern_signal_daily",
                delta_pattern_rows,
            )
            inserted["fundamental_feature_daily"] += _insert_rows(
                connection,
                "fundamental_feature_daily",
                delta_fundamental_rows,
            )

            previous_indicator_rows = {
                (str(row["symbol"]), str(row["trade_date"]), str(row["price_basis"])): row
                for row in indicator_rows
            }
            previous_capital_rows = {
                (str(row["symbol"]), str(row["trade_date"])): row for row in capital_rows
            }
            previous_pattern_rows = {
                (
                    str(row["symbol"]),
                    str(row["trade_date"]),
                    str(row["price_basis"]),
                    str(row["signal_code"]),
                ): row
                for row in pattern_rows
            }
            previous_fundamental_rows = {
                (str(row["symbol"]), str(row["trade_date"])): row
                for row in fundamental_rows
            }

        table_counts = {
            table_name: int(
                connection.execute(f"SELECT COUNT(*) FROM {table_name}").fetchone()[0]
            )
            for table_name in inserted
        }
    finally:
        connection.close()

    return {
        "duckdb_path": str(settings.duckdb_path),
        "inserted": inserted,
        "table_counts": table_counts,
    }


def materialize_analysis_snapshot(
    connection,
    *,
    snapshot_id: str,
    price_basis: str,
    updated_at: str,
    capital_feature_overrides: list[dict[str, object]] | tuple[dict[str, object], ...] | None = None,
    fundamental_feature_overrides: list[dict[str, object]] | tuple[dict[str, object], ...] | None = None,
) -> dict[str, int]:
    series_rows = _load_price_series_asof_rows(
        connection,
        snapshot_id=snapshot_id,
        price_basis=price_basis,
    )
    grouped_rows = _group_rows_by_symbol(series_rows)
    indicator_rows = _build_indicator_rows(
        grouped_rows,
        snapshot_id=snapshot_id,
        price_basis=price_basis,
        updated_at=updated_at,
    )
    capital_rows = _build_capital_feature_rows(
        grouped_rows,
        snapshot_id=snapshot_id,
        updated_at=updated_at,
        capital_feature_overrides=capital_feature_overrides,
    )
    fundamental_rows = _build_fundamental_feature_rows(
        grouped_rows,
        snapshot_id=snapshot_id,
        updated_at=updated_at,
        fundamental_feature_overrides=fundamental_feature_overrides,
    )
    pattern_rows = _build_pattern_signal_rows(
        grouped_rows,
        indicator_rows,
        snapshot_id=snapshot_id,
        price_basis=price_basis,
        updated_at=updated_at,
    )

    connection.execute("DELETE FROM indicator_daily WHERE snapshot_id = ?", [snapshot_id])
    connection.execute("DELETE FROM pattern_signal_daily WHERE snapshot_id = ?", [snapshot_id])
    connection.execute("DELETE FROM capital_feature_daily WHERE snapshot_id = ?", [snapshot_id])
    connection.execute("DELETE FROM fundamental_feature_daily WHERE snapshot_id = ?", [snapshot_id])

    return {
        "indicator_daily": _insert_rows(connection, "indicator_daily", indicator_rows),
        "pattern_signal_daily": _insert_rows(
            connection,
            "pattern_signal_daily",
            pattern_rows,
        ),
        "capital_feature_daily": _insert_rows(
            connection,
            "capital_feature_daily",
            capital_rows,
        ),
        "fundamental_feature_daily": _insert_rows(
            connection,
            "fundamental_feature_daily",
            fundamental_rows,
        ),
    }


def _load_price_series_asof_rows(
    connection,
    *,
    snapshot_id: str,
    price_basis: str,
) -> list[dict[str, object]]:
    rows = connection.execute(
        """
        WITH target AS (
          SELECT publish_seq
          FROM artifact_publish
          WHERE snapshot_id = ?
        ),
        ranked AS (
          SELECT
            ps.symbol,
            ps.trade_date,
            ps.price_basis,
            ps.open,
            ps.high,
            ps.low,
            ps.close,
            ps.pre_close,
            ps.adj_factor,
            ps.volume,
            ps.amount,
            ROW_NUMBER() OVER (
              PARTITION BY ps.symbol, ps.trade_date, ps.price_basis
              ORDER BY ap.publish_seq DESC
            ) AS row_num
          FROM price_series_daily ps
          JOIN artifact_publish ap
            ON ap.snapshot_id = ps.snapshot_id
          JOIN target
            ON ap.publish_seq <= target.publish_seq
          WHERE ps.price_basis = ?
        )
        SELECT
          symbol,
          trade_date,
          price_basis,
          open,
          high,
          low,
          close,
          pre_close,
          adj_factor,
          volume,
          amount
        FROM ranked
        WHERE row_num = 1
        ORDER BY symbol ASC, trade_date ASC
        """,
        [snapshot_id, price_basis],
    ).fetchall()

    return [
        {
            "symbol": str(symbol),
            "trade_date": str(trade_date),
            "price_basis": str(row_price_basis),
            "open": float(open),
            "high": float(high),
            "low": float(low),
            "close": float(close),
            "pre_close": float(pre_close),
            "adj_factor": float(adj_factor) if adj_factor is not None else None,
            "volume": float(volume) if volume is not None else None,
            "amount": float(amount) if amount is not None else None,
        }
        for (
            symbol,
            trade_date,
            row_price_basis,
            open,
            high,
            low,
            close,
            pre_close,
            adj_factor,
            volume,
            amount,
        ) in rows
    ]


def _group_rows_by_symbol(
    rows: list[dict[str, object]],
) -> dict[str, list[dict[str, object]]]:
    grouped_rows: dict[str, list[dict[str, object]]] = {}
    for row in rows:
        grouped_rows.setdefault(str(row["symbol"]), []).append(row)
    return grouped_rows


def _rolling_mean(values: list[float], window: int) -> float | None:
    if not values:
        return None
    sample = values[-min(window, len(values)) :]
    return float(fmean(sample))


def _ema_series(values: list[float], span: int) -> list[float]:
    if not values:
        return []

    alpha = 2.0 / (span + 1.0)
    series = [values[0]]
    for value in values[1:]:
        series.append(alpha * value + (1.0 - alpha) * series[-1])
    return series


def _compute_rsi(values: list[float], window: int) -> float | None:
    if len(values) < 2:
        return None

    sample = values[-min(window + 1, len(values)) :]
    gains: list[float] = []
    losses: list[float] = []
    for previous, current in zip(sample, sample[1:]):
        delta = current - previous
        gains.append(max(delta, 0.0))
        losses.append(max(-delta, 0.0))

    average_gain = fmean(gains) if gains else 0.0
    average_loss = fmean(losses) if losses else 0.0
    if average_gain == 0.0 and average_loss == 0.0:
        return 50.0
    if average_loss == 0.0:
        return 100.0
    rs = average_gain / average_loss
    return 100.0 - (100.0 / (1.0 + rs))


def _compute_bollinger(values: list[float], window: int) -> tuple[float | None, float | None, float | None]:
    if not values:
        return (None, None, None)

    sample = values[-min(window, len(values)) :]
    mid = float(fmean(sample))
    variance = fmean([(value - mid) ** 2 for value in sample]) if sample else 0.0
    stddev = math.sqrt(variance)
    return (mid + 2.0 * stddev, mid, mid - 2.0 * stddev)


def _build_indicator_rows(
    grouped_rows: dict[str, list[dict[str, object]]],
    *,
    snapshot_id: str,
    price_basis: str,
    updated_at: str,
) -> list[dict[str, object]]:
    rows: list[dict[str, object]] = []

    for symbol, series in grouped_rows.items():
        closes = [float(row["close"]) for row in series]
        highs = [float(row["high"]) for row in series]
        lows = [float(row["low"]) for row in series]
        volumes = [float(row["volume"] or 0.0) for row in series]

        ema12 = _ema_series(closes, 12)
        ema26 = _ema_series(closes, 26)
        difs = [ema12[index] - ema26[index] for index in range(len(closes))]
        deas = _ema_series(difs, 9)

        prev_k = 50.0
        prev_d = 50.0

        for index, row in enumerate(series):
            window_closes = closes[: index + 1]
            window_highs = highs[: index + 1]
            window_lows = lows[: index + 1]
            window_volumes = volumes[: index + 1]

            lookback_high = max(window_highs[max(0, index - 8) : index + 1])
            lookback_low = min(window_lows[max(0, index - 8) : index + 1])
            if lookback_high == lookback_low:
                rsv = 50.0
            else:
                rsv = ((closes[index] - lookback_low) / (lookback_high - lookback_low)) * 100.0
            prev_k = (2.0 * prev_k + rsv) / 3.0
            prev_d = (2.0 * prev_d + prev_k) / 3.0
            kdj_j = 3.0 * prev_k - 2.0 * prev_d

            previous_volumes = window_volumes[:-1]
            volume_ratio = 1.0
            if previous_volumes:
                baseline_volume = fmean(previous_volumes[-min(5, len(previous_volumes)) :])
                if baseline_volume > 0:
                    volume_ratio = window_volumes[-1] / baseline_volume

            boll_upper, boll_mid, boll_lower = _compute_bollinger(window_closes, 20)

            rows.append(
                {
                    "symbol": symbol,
                    "trade_date": str(row["trade_date"]),
                    "snapshot_id": snapshot_id,
                    "price_basis": price_basis,
                    "ma5": _rolling_mean(window_closes, 5),
                    "ma10": _rolling_mean(window_closes, 10),
                    "ma20": _rolling_mean(window_closes, 20),
                    "ma60": _rolling_mean(window_closes, 60),
                    "macd_dif": float(difs[index]),
                    "macd_dea": float(deas[index]),
                    "macd_hist": float((difs[index] - deas[index]) * 2.0),
                    "kdj_k": float(prev_k),
                    "kdj_d": float(prev_d),
                    "kdj_j": float(kdj_j),
                    "rsi6": _compute_rsi(window_closes, 6),
                    "rsi12": _compute_rsi(window_closes, 12),
                    "boll_upper": boll_upper,
                    "boll_mid": boll_mid,
                    "boll_lower": boll_lower,
                    "volume_ratio": float(volume_ratio),
                    "updated_at": updated_at,
                }
            )

    return rows


def _build_capital_feature_rows(
    grouped_rows: dict[str, list[dict[str, object]]],
    *,
    snapshot_id: str,
    updated_at: str,
    capital_feature_overrides: list[dict[str, object]] | tuple[dict[str, object], ...] | None = None,
) -> list[dict[str, object]]:
    rows: list[dict[str, object]] = []
    override_by_key = {
        (str(item["symbol"]), str(item["trade_date"])): dict(item)
        for item in (capital_feature_overrides or [])
    }

    for symbol, series in grouped_rows.items():
        for row in series:
            amount = float(row["amount"] or 0.0)
            open_price = float(row["open"])
            close_price = float(row["close"])
            pre_close = float(row["pre_close"])

            intraday_strength = ((close_price - open_price) / open_price) if open_price else 0.0
            change_pct = ((close_price - pre_close) / pre_close) if pre_close else 0.0

            main_net_inflow = amount * intraday_strength * 0.18
            super_large_order_inflow = main_net_inflow * 0.52
            large_order_inflow = main_net_inflow * 0.81
            northbound_net_inflow = amount * change_pct * 0.04

            base_row = {
                "symbol": symbol,
                "trade_date": str(row["trade_date"]),
                "snapshot_id": snapshot_id,
                "main_net_inflow": float(main_net_inflow),
                "main_net_inflow_ratio": float(main_net_inflow / amount) if amount else 0.0,
                "super_large_order_inflow": float(super_large_order_inflow),
                "large_order_inflow": float(large_order_inflow),
                "northbound_net_inflow": float(northbound_net_inflow),
                "has_dragon_tiger": bool(abs(change_pct) >= 0.095 or amount >= 1_000_000_000.0),
                "updated_at": updated_at,
            }
            override = override_by_key.get((symbol, str(row["trade_date"])))
            if override is not None:
                for field_name in (
                    "main_net_inflow",
                    "main_net_inflow_ratio",
                    "super_large_order_inflow",
                    "large_order_inflow",
                    "northbound_net_inflow",
                    "has_dragon_tiger",
                ):
                    if field_name in override and override[field_name] is not None:
                        base_row[field_name] = override[field_name]

            rows.append(base_row)

    return rows


def _build_fundamental_feature_rows(
    grouped_rows: dict[str, list[dict[str, object]]],
    *,
    snapshot_id: str,
    updated_at: str,
    fundamental_feature_overrides: list[dict[str, object]] | tuple[dict[str, object], ...] | None = None,
) -> list[dict[str, object]]:
    rows: list[dict[str, object]] = []
    override_by_key = {
        (str(item["symbol"]), str(item["trade_date"])): dict(item)
        for item in (fundamental_feature_overrides or [])
    }

    for symbol, series in grouped_rows.items():
        for row in series:
            override = override_by_key.get((symbol, str(row["trade_date"])))
            if override is None:
                continue

            base_row = {
                "symbol": symbol,
                "trade_date": str(row["trade_date"]),
                "snapshot_id": snapshot_id,
                "report_period": None,
                "ann_date": None,
                "roe_dt": None,
                "grossprofit_margin": None,
                "debt_to_assets": None,
                "total_revenue": None,
                "net_profit_attr_p": None,
                "n_cashflow_act": None,
                "total_assets": None,
                "total_liab": None,
                "cash_to_profit": None,
                "fundamental_score": None,
                "updated_at": updated_at,
            }
            for field_name in (
                "report_period",
                "ann_date",
                "roe_dt",
                "grossprofit_margin",
                "debt_to_assets",
                "total_revenue",
                "net_profit_attr_p",
                "n_cashflow_act",
                "total_assets",
                "total_liab",
                "cash_to_profit",
                "fundamental_score",
            ):
                if field_name in override:
                    base_row[field_name] = override[field_name]

            meaningful_values = [
                base_row[field_name]
                for field_name in (
                    "roe_dt",
                    "grossprofit_margin",
                    "debt_to_assets",
                    "total_revenue",
                    "net_profit_attr_p",
                    "n_cashflow_act",
                    "total_assets",
                    "total_liab",
                    "cash_to_profit",
                    "fundamental_score",
                )
            ]
            if any(value is not None for value in meaningful_values):
                rows.append(base_row)

    return rows


def _build_pattern_signal_rows(
    grouped_rows: dict[str, list[dict[str, object]]],
    indicator_rows: list[dict[str, object]],
    *,
    snapshot_id: str,
    price_basis: str,
    updated_at: str,
) -> list[dict[str, object]]:
    indicator_by_key = {
        (str(row["symbol"]), str(row["trade_date"]), str(row["price_basis"])): row
        for row in indicator_rows
    }

    rows: list[dict[str, object]] = []
    for symbol, series in grouped_rows.items():
        closes = [float(row["close"]) for row in series]
        highs = [float(row["high"]) for row in series]
        volumes = [float(row["volume"] or 0.0) for row in series]

        for index, row in enumerate(series):
            indicator = indicator_by_key[(symbol, str(row["trade_date"]), price_basis)]
            volume_ratio = float(indicator["volume_ratio"] or 1.0)
            ma5 = float(indicator["ma5"] or row["close"])

            if index > 0:
                previous_close = closes[index - 1]
                previous_high = max(highs[:index])
                if closes[index] > previous_high and closes[index] > ma5:
                    breakout_score = min(
                        100.0,
                        (closes[index] / previous_high - 1.0) * 8000.0 + volume_ratio * 10.0,
                    )
                    rows.append(
                        {
                            "symbol": symbol,
                            "trade_date": str(row["trade_date"]),
                            "snapshot_id": snapshot_id,
                            "price_basis": price_basis,
                            "signal_code": "breakout_up",
                            "signal_type": "breakout",
                            "direction": "up",
                            "is_triggered": True,
                            "signal_score": float(breakout_score),
                            "payload_json": json.dumps(
                                {
                                    "previous_high": round(previous_high, 4),
                                    "close": round(closes[index], 4),
                                    "volume_ratio": round(volume_ratio, 4),
                                },
                                ensure_ascii=False,
                            ),
                            "updated_at": updated_at,
                        }
                    )

                if volume_ratio >= 1.1 and closes[index] >= previous_close:
                    rows.append(
                        {
                            "symbol": symbol,
                            "trade_date": str(row["trade_date"]),
                            "snapshot_id": snapshot_id,
                            "price_basis": price_basis,
                            "signal_code": "volume_expansion",
                            "signal_type": "volume",
                            "direction": "up",
                            "is_triggered": True,
                            "signal_score": float(min(100.0, volume_ratio * 35.0)),
                            "payload_json": json.dumps(
                                {
                                    "volume": round(volumes[index], 2),
                                    "previous_close": round(previous_close, 4),
                                    "close": round(closes[index], 4),
                                    "volume_ratio": round(volume_ratio, 4),
                                },
                                ensure_ascii=False,
                            ),
                            "updated_at": updated_at,
                        }
                    )

                if closes[index] < previous_close and volume_ratio <= 0.95 and closes[index] >= ma5 * 0.99:
                    rows.append(
                        {
                            "symbol": symbol,
                            "trade_date": str(row["trade_date"]),
                            "snapshot_id": snapshot_id,
                            "price_basis": price_basis,
                            "signal_code": "pullback_low_volume",
                            "signal_type": "pullback",
                            "direction": "up",
                            "is_triggered": True,
                            "signal_score": float(max(0.0, (1.05 - volume_ratio) * 100.0)),
                            "payload_json": json.dumps(
                                {
                                    "previous_close": round(previous_close, 4),
                                    "close": round(closes[index], 4),
                                    "ma5": round(ma5, 4),
                                    "volume_ratio": round(volume_ratio, 4),
                                },
                                ensure_ascii=False,
                            ),
                            "updated_at": updated_at,
                        }
                    )

    return rows


def _diff_rows(
    *,
    rows: list[dict[str, object]],
    previous_rows: dict[tuple[object, ...], dict[str, object]],
    key_fields: tuple[str, ...],
    ignore_fields: tuple[str, ...],
) -> list[dict[str, object]]:
    delta_rows: list[dict[str, object]] = []
    for row in rows:
        key = tuple(row[field] for field in key_fields)
        previous_row = previous_rows.get(key)
        if previous_row is None:
            delta_rows.append(row)
            continue

        comparable_row = {
            key: value for key, value in row.items() if key not in ignore_fields
        }
        comparable_previous = {
            key: value for key, value in previous_row.items() if key not in ignore_fields
        }
        if comparable_row != comparable_previous:
            delta_rows.append(row)

    return delta_rows


def _insert_rows(connection, table_name: str, rows: list[dict[str, object]]) -> int:
    if not rows:
        return 0

    columns = list(rows[0].keys())
    column_sql = ", ".join(columns)
    placeholder_sql = ", ".join("?" for _ in columns)
    inserted = 0
    for row in rows:
        connection.execute(
            f"INSERT INTO {table_name} ({column_sql}) VALUES ({placeholder_sql})",
            [row[column] for column in columns],
        )
        inserted += 1
    return inserted


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Generate QuantA analysis artifacts from the local DuckDB foundation."
    )
    parser.add_argument(
        "--print-summary",
        action="store_true",
        help="Print inserted row counts and current artifact table sizes.",
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    settings = load_settings()
    summary = ensure_analysis_artifacts(settings)

    if args.print_summary:
        print("QuantA analysis artifacts ready:")
        print(f"- duckdb_path: {summary['duckdb_path']}")
        for table_name, inserted in summary["inserted"].items():
            print(f"- inserted_{table_name}: {inserted}")
        for table_name, row_count in summary["table_counts"].items():
            print(f"- {table_name}: {row_count}")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
