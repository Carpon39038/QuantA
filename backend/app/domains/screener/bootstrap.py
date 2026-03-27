from __future__ import annotations

import argparse
import json

from backend.app.app_wiring.settings import AppSettings, load_settings
from backend.app.domains.analysis.bootstrap import ensure_analysis_artifacts
from backend.app.shared.providers.duckdb import connect_duckdb


def ensure_screener_artifacts(settings: AppSettings) -> dict[str, object]:
    ensure_analysis_artifacts(settings)

    connection = connect_duckdb(settings.duckdb_path)
    try:
        snapshot_rows = connection.execute(
            """
            SELECT
              snapshot_id,
              raw_snapshot_id,
              publish_seq,
              biz_date,
              price_basis,
              published_at
            FROM artifact_publish
            WHERE status = 'READY'
            ORDER BY publish_seq ASC
            """
        ).fetchall()

        connection.execute("DELETE FROM screener_result")
        connection.execute("DELETE FROM screener_run")

        inserted = {
            "screener_run": 0,
            "screener_result": 0,
        }

        for (
            snapshot_id,
            raw_snapshot_id,
            _publish_seq,
            biz_date,
            price_basis,
            published_at,
        ) in snapshot_rows:
            candidates = _build_snapshot_candidates(
                connection,
                snapshot_id=str(snapshot_id),
                raw_snapshot_id=str(raw_snapshot_id),
                biz_date=str(biz_date),
                price_basis=str(price_basis),
            )
            run_id = f"screener_run_{str(snapshot_id).replace('-', '_')}"

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
                    run_id,
                    str(biz_date),
                    str(snapshot_id),
                    "三策略候选池",
                    "m3-dev-001",
                    str(price_basis),
                    len(candidates["universe"]),
                    len(candidates["results"]),
                    "SUCCESS",
                    str(biz_date),
                    str(published_at),
                    str(published_at),
                ],
            )
            inserted["screener_run"] += 1

            for rank_no, result in enumerate(candidates["results"], start=1):
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
                      trend_score,
                      price_volume_score,
                      capital_score,
                      fundamental_score,
                      display_name,
                      thesis,
                      matched_rules_json,
                      risk_flags_json,
                      rank_no
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    [
                        run_id,
                        result["symbol"],
                        str(biz_date),
                        result["strategy_name"],
                        str(snapshot_id),
                        str(price_basis),
                        result["total_score"],
                        result["trend_score"],
                        result["price_volume_score"],
                        result["capital_score"],
                        result["fundamental_score"],
                        result["display_name"],
                        result["thesis"],
                        json.dumps(result["matched_rules"], ensure_ascii=False),
                        json.dumps(result["risk_flags"], ensure_ascii=False),
                        rank_no,
                    ],
                )
                inserted["screener_result"] += 1

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


def _build_snapshot_candidates(
    connection,
    *,
    snapshot_id: str,
    raw_snapshot_id: str,
    biz_date: str,
    price_basis: str,
) -> dict[str, object]:
    universe_rows = connection.execute(
        """
        WITH raw_target AS (
          SELECT snapshot_seq
          FROM raw_snapshot
          WHERE raw_snapshot_id = ?
        ),
        latest_bar AS (
          SELECT
            db.symbol,
            db.trade_date,
            db.close_raw,
            db.amount,
            db.is_suspended,
            ROW_NUMBER() OVER (
              PARTITION BY db.symbol, db.trade_date
              ORDER BY rs.snapshot_seq DESC
            ) AS row_num
          FROM daily_bar db
          JOIN raw_snapshot rs
            ON rs.raw_snapshot_id = db.raw_snapshot_id
          JOIN raw_target rt
            ON rs.snapshot_seq <= rt.snapshot_seq
          WHERE db.trade_date = CAST(? AS DATE)
        ),
        latest_indicator AS (
          SELECT
            ind.symbol,
            ind.ma5,
            ind.macd_hist,
            ind.rsi6,
            ind.volume_ratio,
            ROW_NUMBER() OVER (
              PARTITION BY ind.symbol, ind.trade_date, ind.price_basis
              ORDER BY ap.publish_seq DESC
            ) AS row_num
          FROM indicator_daily ind
          JOIN artifact_publish ap
            ON ap.snapshot_id = ind.snapshot_id
          WHERE ind.trade_date = CAST(? AS DATE)
            AND ind.snapshot_id = ?
            AND ind.price_basis = ?
        ),
        latest_capital AS (
          SELECT
            cf.symbol,
            cf.main_net_inflow_ratio,
            cf.northbound_net_inflow,
            cf.has_dragon_tiger,
            ROW_NUMBER() OVER (
              PARTITION BY cf.symbol, cf.trade_date
              ORDER BY ap.publish_seq DESC
            ) AS row_num
          FROM capital_feature_daily cf
          JOIN artifact_publish ap
            ON ap.snapshot_id = cf.snapshot_id
          WHERE cf.trade_date = CAST(? AS DATE)
            AND cf.snapshot_id = ?
        ),
        pattern_signals AS (
          SELECT
            ps.symbol,
            LIST(ps.signal_code ORDER BY ps.signal_code) AS signal_codes
          FROM pattern_signal_daily ps
          WHERE ps.trade_date = CAST(? AS DATE)
            AND ps.snapshot_id = ?
            AND ps.price_basis = ?
          GROUP BY ps.symbol
        )
        SELECT
          sb.symbol,
          sb.display_name,
          sb.board,
          sb.industry,
          lb.close_raw,
          lb.amount,
          lb.is_suspended,
          li.ma5,
          li.macd_hist,
          li.rsi6,
          li.volume_ratio,
          lc.main_net_inflow_ratio,
          lc.northbound_net_inflow,
          lc.has_dragon_tiger,
          COALESCE(ps.signal_codes, []) AS signal_codes
        FROM stock_basic sb
        JOIN latest_bar lb
          ON lb.symbol = sb.symbol
         AND lb.row_num = 1
        JOIN latest_indicator li
          ON li.symbol = sb.symbol
         AND li.row_num = 1
        JOIN latest_capital lc
          ON lc.symbol = sb.symbol
         AND lc.row_num = 1
        LEFT JOIN pattern_signals ps
          ON ps.symbol = sb.symbol
        WHERE sb.is_active = TRUE
        ORDER BY sb.symbol ASC
        """,
        [
            raw_snapshot_id,
            biz_date,
            biz_date,
            snapshot_id,
            price_basis,
            biz_date,
            snapshot_id,
            biz_date,
            snapshot_id,
            price_basis,
        ],
    ).fetchall()

    universe: list[str] = []
    results: list[dict[str, object]] = []

    for (
        symbol,
        display_name,
        _board,
        industry,
        close_raw,
        amount,
        is_suspended,
        ma5,
        macd_hist,
        rsi6,
        volume_ratio,
        main_net_inflow_ratio,
        northbound_net_inflow,
        has_dragon_tiger,
        signal_codes,
    ) in universe_rows:
        if is_suspended:
            continue
        if amount is None or float(amount) < 800_000_000.0:
            continue

        universe.append(str(symbol))
        signal_set = set(signal_codes)
        trend_score = _clamp_score(
            55.0
            + max(float(macd_hist or 0.0), 0.0) * 120.0
            + max((float(close_raw) / float(ma5 or close_raw) - 1.0), 0.0) * 1200.0
        )
        price_volume_score = _clamp_score(
            40.0
            + float(volume_ratio or 1.0) * 22.0
            + (18.0 if "breakout_up" in signal_set else 0.0)
            + (15.0 if "volume_expansion" in signal_set else 0.0)
        )
        capital_score = _clamp_score(
            42.0
            + max(float(main_net_inflow_ratio or 0.0), 0.0) * 8000.0
            + max(float(northbound_net_inflow or 0.0), 0.0) / 5_000_000.0
        )
        fundamental_score = _clamp_score(
            62.0
            - (6.0 if bool(has_dragon_tiger) else 0.0)
            - (4.0 if float(rsi6 or 50.0) >= 82.0 else 0.0)
        )

        strategy_candidates = []
        if "breakout_up" in signal_set or float(close_raw) >= float(ma5 or close_raw) * 1.01:
            strategy_candidates.append(
                (
                    "趋势突破",
                    _clamp_score(trend_score * 0.56 + price_volume_score * 0.29 + capital_score * 0.1 + fundamental_score * 0.05 + 6.0),
                )
            )
        if "volume_expansion" in signal_set or float(volume_ratio or 1.0) >= 1.12:
            strategy_candidates.append(
                (
                    "放量启动",
                    _clamp_score(trend_score * 0.18 + price_volume_score * 0.52 + capital_score * 0.2 + fundamental_score * 0.1 + 5.0),
                )
            )
        if (
            float(main_net_inflow_ratio or 0.0) > 0.0
            and float(northbound_net_inflow or 0.0) > 0.0
        ):
            strategy_candidates.append(
                (
                    "资金共振",
                    _clamp_score(trend_score * 0.18 + price_volume_score * 0.12 + capital_score * 0.58 + fundamental_score * 0.12 + 5.0),
                )
            )

        if not strategy_candidates:
            continue

        strategy_name, total_score = max(strategy_candidates, key=lambda item: item[1])
        matched_rules = [
            "liquidity_pass",
            f"industry:{industry}",
            f"strategy:{strategy_name}",
        ]
        for signal_code in sorted(signal_set):
            matched_rules.append(signal_code)
        if float(main_net_inflow_ratio or 0.0) > 0:
            matched_rules.append("main_inflow_positive")
        if float(northbound_net_inflow or 0.0) > 0:
            matched_rules.append("northbound_positive")

        risk_flags: list[str] = []
        if bool(has_dragon_tiger):
            risk_flags.append("龙虎榜波动放大")
        if float(rsi6 or 50.0) >= 82.0:
            risk_flags.append("短线过热")
        if float(volume_ratio or 1.0) >= 1.45:
            risk_flags.append("放量过快")

        thesis = _build_thesis(
            strategy_name=str(strategy_name),
            display_name=str(display_name),
            signal_set=signal_set,
            trend_score=trend_score,
            capital_score=capital_score,
        )

        results.append(
            {
                "symbol": str(symbol),
                "display_name": str(display_name),
                "strategy_name": str(strategy_name),
                "total_score": int(round(total_score)),
                "trend_score": round(trend_score, 2),
                "price_volume_score": round(price_volume_score, 2),
                "capital_score": round(capital_score, 2),
                "fundamental_score": round(fundamental_score, 2),
                "matched_rules": matched_rules,
                "risk_flags": risk_flags,
                "thesis": thesis,
            }
        )

    results.sort(key=lambda row: (-int(row["total_score"]), str(row["symbol"])))
    for index, row in enumerate(results, start=1):
        row["rank_no"] = index

    return {"universe": universe, "results": results[:10]}


def _clamp_score(value: float) -> float:
    return max(0.0, min(100.0, value))


def _build_thesis(
    *,
    strategy_name: str,
    display_name: str,
    signal_set: set[str],
    trend_score: float,
    capital_score: float,
) -> str:
    if strategy_name == "趋势突破":
        return (
            f"{display_name} 在已发布快照下走出突破形态，"
            f"趋势分 {trend_score:.1f} 且信号命中 {', '.join(sorted(signal_set)) or '无显式形态'}。"
        )
    if strategy_name == "放量启动":
        return (
            f"{display_name} 的量价共振更强，"
            f"放量信号带动 price-volume 评分抬升，适合作为启动候选。"
        )
    return (
        f"{display_name} 的资金面修复更突出，"
        f"资金分 {capital_score:.1f}，适合作为资金共振方向的跟踪对象。"
    )


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Generate QuantA screener runs and results from analysis artifacts."
    )
    parser.add_argument(
        "--print-summary",
        action="store_true",
        help="Print inserted screener run/result counts and current table sizes.",
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    settings = load_settings()
    summary = ensure_screener_artifacts(settings)

    if args.print_summary:
        print("QuantA screener artifacts ready:")
        print(f"- duckdb_path: {summary['duckdb_path']}")
        for table_name, inserted in summary["inserted"].items():
            print(f"- inserted_{table_name}: {inserted}")
        for table_name, row_count in summary["table_counts"].items():
            print(f"- {table_name}: {row_count}")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
