from __future__ import annotations

import argparse
import json

from backend.app.app_wiring.settings import AppSettings, load_settings
from backend.app.domains.screener.bootstrap import ensure_screener_artifacts
from backend.app.shared.providers.duckdb import connect_duckdb


INITIAL_CASH = 1_000_000.0
BROKER_FEE_RATE = 0.0003
STAMP_DUTY_RATE = 0.001
LOT_SIZE = 100
SEED_STRATEGY_VERSION = "m4-dev-001"


def ensure_backtest_artifacts(settings: AppSettings) -> dict[str, object]:
    ensure_screener_artifacts(settings)

    connection = connect_duckdb(settings.duckdb_path)
    try:
        snapshot_rows = connection.execute(
            """
            SELECT
              snapshot_id,
              raw_snapshot_id,
              biz_date,
              price_basis,
              published_at
            FROM artifact_publish
            WHERE status = 'READY'
            ORDER BY publish_seq ASC
            """
        ).fetchall()

        seed_backtest_ids = [_seed_backtest_id(str(snapshot_id)) for snapshot_id, *_ in snapshot_rows]
        for backtest_id in seed_backtest_ids:
            delete_backtest_materialization(connection, backtest_id=backtest_id)
            connection.execute(
                "DELETE FROM backtest_request WHERE backtest_id = ?",
                [backtest_id],
            )

        inserted = {
            "backtest_request": 0,
            "backtest_run": 0,
            "backtest_trade": 0,
            "backtest_equity_curve": 0,
        }

        for snapshot_id, raw_snapshot_id, biz_date, price_basis, published_at in snapshot_rows:
            bundle = build_backtest_bundle(
                connection,
                backtest_id=_seed_backtest_id(str(snapshot_id)),
                snapshot_id=str(snapshot_id),
                raw_snapshot_id=str(raw_snapshot_id),
                biz_date=str(biz_date),
                price_basis=str(price_basis),
                requested_at=str(published_at),
                top_n=2,
                strategy_version=SEED_STRATEGY_VERSION,
                created_from="screener_result_seed",
            )
            if bundle is None:
                continue

            upsert_backtest_request_row(
                connection,
                backtest_id=bundle["backtest_id"],
                requested_at=bundle["requested_at"],
                snapshot_id=bundle["snapshot_id"],
                raw_snapshot_id=bundle["raw_snapshot_id"],
                strategy_version=bundle["strategy_version"],
                signal_price_basis=bundle["signal_price_basis"],
                payload_json=bundle["request_payload"],
                status=bundle["status"],
                retry_count=0,
                last_error=None,
            )
            inserted["backtest_request"] += 1

            row_counts = replace_backtest_materialization(connection, bundle=bundle)
            for key, value in row_counts.items():
                inserted[key] += value

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


def build_backtest_bundle(
    connection,
    *,
    backtest_id: str,
    snapshot_id: str,
    raw_snapshot_id: str,
    biz_date: str,
    price_basis: str,
    requested_at: str,
    top_n: int = 2,
    strategy_version: str = SEED_STRATEGY_VERSION,
    created_from: str = "screener_result",
) -> dict[str, object] | None:
    candidate_rows = connection.execute(
        """
        SELECT
          sr.symbol,
          sr.display_name,
          sr.strategy_name,
          sr.rank_no
        FROM screener_result sr
        JOIN screener_run srun
          ON srun.run_id = sr.run_id
        WHERE srun.snapshot_id = ?
        ORDER BY sr.rank_no ASC, sr.symbol ASC
        LIMIT ?
        """,
        [snapshot_id, top_n],
    ).fetchall()
    if not candidate_rows:
        return None

    candidate_price_paths: list[dict[str, object]] = []
    for symbol, display_name, strategy_name, rank_no in candidate_rows:
        price_rows = _query_raw_price_path(
            connection,
            raw_snapshot_id=raw_snapshot_id,
            symbol=str(symbol),
            date_to=biz_date,
        )
        if len(price_rows) < 2:
            continue
        candidate_price_paths.append(
            {
                "symbol": str(symbol),
                "display_name": str(display_name),
                "strategy_name": str(strategy_name),
                "rank_no": int(rank_no),
                "price_rows": price_rows,
            }
        )

    if not candidate_price_paths:
        return None

    position_budget = INITIAL_CASH / len(candidate_price_paths)
    buy_trades: list[dict[str, object]] = []
    sell_trades: list[dict[str, object]] = []
    active_positions: list[dict[str, object]] = []
    notes: list[str] = [
        f"基于 {snapshot_id} 的 Top {len(candidate_price_paths)} 候选做等权回放。",
        "成交使用 raw close，包含 0.03% 手续费与卖出 0.10% 印花税。",
    ]

    cash = INITIAL_CASH
    available_dates = sorted(
        {
            row["trade_date"]
            for candidate in candidate_price_paths
            for row in candidate["price_rows"]
        }
    )
    if len(available_dates) < 2:
        return None

    start_date = available_dates[0]
    end_date = available_dates[-1]

    for candidate in candidate_price_paths:
        entry_row = candidate["price_rows"][0]
        exit_row = candidate["price_rows"][-1]
        buy_price = float(entry_row["close_raw"])
        sell_price = float(exit_row["close_raw"])
        quantity = int(position_budget / buy_price / LOT_SIZE) * LOT_SIZE
        if quantity <= 0:
            continue

        buy_notional = round(quantity * buy_price, 2)
        buy_fee = round(max(5.0, buy_notional * BROKER_FEE_RATE), 2)
        cash = round(cash - buy_notional - buy_fee, 2)

        buy_trades.append(
            {
                "symbol": candidate["symbol"],
                "trade_date": entry_row["trade_date"],
                "side": "BUY",
                "price_basis": "raw",
                "trade_price": round(buy_price, 2),
                "quantity": quantity,
                "notional": buy_notional,
                "fee": buy_fee,
                "tax": 0.0,
                "pnl": None,
                "holding_days": None,
                "reason": f"equal_weight_entry:{candidate['strategy_name']}",
                "rank_no": candidate["rank_no"],
            }
        )

        sell_notional = round(quantity * sell_price, 2)
        sell_fee = round(max(5.0, sell_notional * BROKER_FEE_RATE), 2)
        sell_tax = round(sell_notional * STAMP_DUTY_RATE, 2)
        pnl = round(sell_notional - sell_fee - sell_tax - buy_notional - buy_fee, 2)
        holding_days = max(0, len(candidate["price_rows"]) - 1)
        sell_trades.append(
            {
                "symbol": candidate["symbol"],
                "trade_date": exit_row["trade_date"],
                "side": "SELL",
                "price_basis": "raw",
                "trade_price": round(sell_price, 2),
                "quantity": quantity,
                "notional": sell_notional,
                "fee": sell_fee,
                "tax": sell_tax,
                "pnl": pnl,
                "holding_days": holding_days,
                "reason": "window_exit",
                "rank_no": candidate["rank_no"],
            }
        )
        active_positions.append(
            {
                "symbol": candidate["symbol"],
                "display_name": candidate["display_name"],
                "rank_no": candidate["rank_no"],
                "strategy_name": candidate["strategy_name"],
                "quantity": quantity,
                "sell_proceeds_net": round(sell_notional - sell_fee - sell_tax, 2),
                "price_by_date": {
                    row["trade_date"]: float(row["close_raw"])
                    for row in candidate["price_rows"]
                },
            }
        )

    if not active_positions:
        return None

    final_cash = round(
        cash + sum(position["sell_proceeds_net"] for position in active_positions),
        2,
    )

    equity_curve: list[dict[str, object]] = []
    previous_equity: float | None = None
    peak_equity = INITIAL_CASH

    for trade_date in available_dates:
        if trade_date == end_date:
            market_value = 0.0
            equity = final_cash
            curve_cash = final_cash
            position_count = 0
        else:
            market_value = round(
                sum(
                    position["quantity"] * position["price_by_date"].get(trade_date, 0.0)
                    for position in active_positions
                ),
                2,
            )
            equity = round(cash + market_value, 2)
            curve_cash = cash
            position_count = len(active_positions)

        peak_equity = max(peak_equity, equity)
        daily_return = None
        if previous_equity not in (None, 0):
            daily_return = round((equity / previous_equity - 1.0) * 100.0, 4)
        drawdown = round(max(0.0, (peak_equity - equity) / peak_equity * 100.0), 4)
        equity_curve.append(
            {
                "trade_date": trade_date,
                "position_count": position_count,
                "cash": round(curve_cash, 2),
                "market_value": market_value,
                "equity": round(equity, 2),
                "drawdown": drawdown,
                "daily_return": daily_return,
                "benchmark_close": None,
            }
        )
        previous_equity = equity

    closed_pnls = [float(trade["pnl"]) for trade in sell_trades if trade["pnl"] is not None]
    total_return_ratio = final_cash / INITIAL_CASH - 1.0
    annual_return_pct = round(
        total_return_ratio * 252.0 / max(1, len(available_dates) - 1) * 100.0,
        2,
    )
    max_drawdown_pct = round(max(row["drawdown"] for row in equity_curve), 2)
    win_rate_pct = round(
        sum(1 for pnl in closed_pnls if pnl > 0.0) / len(closed_pnls) * 100.0,
        2,
    )
    positive_pnls = [pnl for pnl in closed_pnls if pnl > 0.0]
    negative_pnls = [abs(pnl) for pnl in closed_pnls if pnl < 0.0]
    if positive_pnls and negative_pnls:
        profit_factor = round(
            (sum(positive_pnls) / len(positive_pnls))
            / (sum(negative_pnls) / len(negative_pnls)),
            2,
        )
    elif positive_pnls:
        profit_factor = 9.99
    else:
        profit_factor = 0.0

    notes.append(
        "持仓标的: "
        + " / ".join(
            f"{position['display_name']}({position['strategy_name']})"
            for position in active_positions
        )
    )
    notes.append(f"样本窗口: {start_date} to {end_date}")

    strategy_names = sorted({position["strategy_name"] for position in active_positions})
    return {
        "backtest_id": backtest_id,
        "requested_at": requested_at,
        "snapshot_id": snapshot_id,
        "raw_snapshot_id": raw_snapshot_id,
        "strategy_name": " / ".join(strategy_names) + " 等权回放",
        "strategy_version": strategy_version,
        "signal_price_basis": price_basis,
        "engine_version": strategy_version,
        "benchmark": "000300.SH",
        "status": "SUCCESS",
        "start_date": start_date,
        "end_date": end_date,
        "request_payload": {
            "top_n": len(active_positions),
            "initial_cash": INITIAL_CASH,
            "holding_mode": "window_hold",
            "created_from": created_from,
        },
        "params": {
            "top_n": len(active_positions),
            "rebalance": "none",
            "holding_mode": "window_hold",
        },
        "cost_model": {
            "broker_fee_rate": BROKER_FEE_RATE,
            "stamp_duty_rate": STAMP_DUTY_RATE,
            "min_fee": 5.0,
        },
        "metrics": {
            "total_return_pct": round(total_return_ratio * 100.0, 2),
            "annual_return_pct": annual_return_pct,
            "max_drawdown_pct": max_drawdown_pct,
            "win_rate_pct": win_rate_pct,
            "profit_factor": profit_factor,
        },
        "notes": notes,
        "trades": sorted(
            buy_trades + sell_trades,
            key=lambda row: (str(row["trade_date"]), str(row["symbol"]), str(row["side"])),
        ),
        "equity_curve": equity_curve,
    }


def upsert_backtest_request_row(
    connection,
    *,
    backtest_id: str,
    requested_at: str,
    snapshot_id: str,
    raw_snapshot_id: str,
    strategy_version: str,
    signal_price_basis: str,
    payload_json: dict[str, object],
    status: str,
    retry_count: int,
    last_error: str | None,
) -> None:
    connection.execute("DELETE FROM backtest_request WHERE backtest_id = ?", [backtest_id])
    connection.execute(
        """
        INSERT INTO backtest_request (
          backtest_id,
          requested_at,
          snapshot_id,
          raw_snapshot_id,
          strategy_version,
          signal_price_basis,
          payload_json,
          status,
          retry_count,
          last_error
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        [
            backtest_id,
            requested_at,
            snapshot_id,
            raw_snapshot_id,
            strategy_version,
            signal_price_basis,
            json.dumps(payload_json, ensure_ascii=False),
            status,
            retry_count,
            last_error,
        ],
    )


def delete_backtest_materialization(connection, *, backtest_id: str) -> None:
    connection.execute("DELETE FROM backtest_equity_curve WHERE backtest_id = ?", [backtest_id])
    connection.execute("DELETE FROM backtest_trade WHERE backtest_id = ?", [backtest_id])
    connection.execute("DELETE FROM backtest_run WHERE backtest_id = ?", [backtest_id])


def replace_backtest_materialization(
    connection,
    *,
    bundle: dict[str, object],
) -> dict[str, int]:
    delete_backtest_materialization(connection, backtest_id=str(bundle["backtest_id"]))

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
            bundle["backtest_id"],
            bundle["strategy_name"],
            bundle["strategy_version"],
            json.dumps(bundle["params"], ensure_ascii=False),
            bundle["snapshot_id"],
            bundle["raw_snapshot_id"],
            bundle["signal_price_basis"],
            "raw",
            json.dumps(bundle["cost_model"], ensure_ascii=False),
            bundle["engine_version"],
            bundle["start_date"],
            bundle["end_date"],
            bundle["benchmark"],
            bundle["metrics"]["total_return_pct"],
            bundle["metrics"]["annual_return_pct"],
            bundle["metrics"]["max_drawdown_pct"],
            bundle["metrics"]["win_rate_pct"],
            bundle["metrics"]["profit_factor"],
            bundle["status"],
            bundle["requested_at"],
            json.dumps(bundle["notes"], ensure_ascii=False),
        ],
    )

    trade_count = 0
    for trade in bundle["trades"]:
        connection.execute(
            """
            INSERT INTO backtest_trade (
              backtest_id,
              symbol,
              trade_date,
              side,
              price_basis,
              trade_price,
              quantity,
              notional,
              fee,
              tax,
              pnl,
              holding_days,
              reason,
              rank_no
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            [
                bundle["backtest_id"],
                trade["symbol"],
                trade["trade_date"],
                trade["side"],
                trade["price_basis"],
                trade["trade_price"],
                trade["quantity"],
                trade["notional"],
                trade["fee"],
                trade["tax"],
                trade["pnl"],
                trade["holding_days"],
                trade["reason"],
                trade["rank_no"],
            ],
        )
        trade_count += 1

    curve_count = 0
    for curve_row in bundle["equity_curve"]:
        connection.execute(
            """
            INSERT INTO backtest_equity_curve (
              backtest_id,
              trade_date,
              position_count,
              cash,
              market_value,
              equity,
              drawdown,
              daily_return,
              benchmark_close,
              updated_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            [
                bundle["backtest_id"],
                curve_row["trade_date"],
                curve_row["position_count"],
                curve_row["cash"],
                curve_row["market_value"],
                curve_row["equity"],
                curve_row["drawdown"],
                curve_row["daily_return"],
                curve_row["benchmark_close"],
                bundle["requested_at"],
            ],
        )
        curve_count += 1

    return {
        "backtest_run": 1,
        "backtest_trade": trade_count,
        "backtest_equity_curve": curve_count,
    }


def _seed_backtest_id(snapshot_id: str) -> str:
    return f"backtest_run_{snapshot_id.replace('-', '_')}"


def _query_raw_price_path(
    connection,
    *,
    raw_snapshot_id: str,
    symbol: str,
    date_to: str,
) -> list[dict[str, object]]:
    rows = connection.execute(
        """
        WITH target AS (
          SELECT snapshot_seq
          FROM raw_snapshot
          WHERE raw_snapshot_id = ?
        ),
        ranked AS (
          SELECT
            db.trade_date,
            db.open_raw,
            db.close_raw,
            ROW_NUMBER() OVER (
              PARTITION BY db.symbol, db.trade_date
              ORDER BY rs.snapshot_seq DESC
            ) AS row_num
          FROM daily_bar db
          JOIN raw_snapshot rs
            ON rs.raw_snapshot_id = db.raw_snapshot_id
          JOIN target
            ON rs.snapshot_seq <= target.snapshot_seq
          WHERE db.symbol = ?
            AND db.trade_date <= CAST(? AS DATE)
        )
        SELECT trade_date, open_raw, close_raw
        FROM ranked
        WHERE row_num = 1
        ORDER BY trade_date ASC
        """,
        [raw_snapshot_id, symbol, date_to],
    ).fetchall()
    return [
        {
            "trade_date": str(trade_date),
            "open_raw": float(open_raw),
            "close_raw": float(close_raw),
        }
        for trade_date, open_raw, close_raw in rows
    ]


def _print_summary(summary: dict[str, object]) -> None:
    inserted = summary["inserted"]
    table_counts = summary["table_counts"]
    print("QuantA backtest artifacts ready:")
    print(f"- duckdb_path: {summary['duckdb_path']}")
    print(f"- inserted_backtest_request: {inserted['backtest_request']}")
    print(f"- inserted_backtest_run: {inserted['backtest_run']}")
    print(f"- inserted_backtest_trade: {inserted['backtest_trade']}")
    print(f"- inserted_backtest_equity_curve: {inserted['backtest_equity_curve']}")
    print(f"- backtest_request: {table_counts['backtest_request']}")
    print(f"- backtest_run: {table_counts['backtest_run']}")
    print(f"- backtest_trade: {table_counts['backtest_trade']}")
    print(f"- backtest_equity_curve: {table_counts['backtest_equity_curve']}")


def main() -> int:
    parser = argparse.ArgumentParser(description="Bootstrap QuantA backtest artifacts.")
    parser.add_argument(
        "--print-summary",
        action="store_true",
        help="Print a short backtest bootstrap summary.",
    )
    args = parser.parse_args()

    settings = load_settings()
    summary = ensure_backtest_artifacts(settings)
    if args.print_summary:
        _print_summary(summary)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
