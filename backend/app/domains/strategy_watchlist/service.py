from __future__ import annotations

from datetime import datetime, timedelta, timezone
import json

from backend.app.app_wiring.settings import AppSettings
from backend.app.shared.providers.duckdb import connect_duckdb
from backend.app.shared.telemetry.alerts import emit_alert


CN_TZ = timezone(timedelta(hours=8))
SUPPORTED_MONITOR_STRATEGIES = ("AUTO", "趋势突破", "放量启动", "资金共振")
ACTION_PRIORITY = {
    "BUY": 0,
    "SELL": 1,
    "WATCH": 2,
    "AVOID": 3,
    "UNAVAILABLE": 4,
}


def list_strategy_watchlist(
    settings: AppSettings,
    *,
    snapshot_id: str | None = None,
) -> dict[str, object]:
    connection = connect_duckdb(settings.duckdb_path, read_only=True)
    try:
        snapshot_meta = _resolve_snapshot_meta(connection, snapshot_id=snapshot_id)
        watchlist_rows = connection.execute(
            """
            SELECT
              symbol,
              preferred_strategy_name,
              created_at,
              updated_at
            FROM strategy_watchlist
            ORDER BY updated_at DESC, symbol ASC
            """
        ).fetchall()
        items = _evaluate_watchlist_rows(
            connection,
            watchlist_rows=watchlist_rows,
            snapshot_meta=snapshot_meta,
        )
    finally:
        connection.close()

    return {
        "snapshot_id": snapshot_meta["snapshot_id"],
        "raw_snapshot_id": snapshot_meta["raw_snapshot_id"],
        "as_of_date": snapshot_meta["biz_date"],
        "price_basis": snapshot_meta["price_basis"],
        "supported_strategies": list(SUPPORTED_MONITOR_STRATEGIES),
        "items": items,
    }


def add_strategy_watchlist_item(
    settings: AppSettings,
    *,
    symbol: str,
    preferred_strategy_name: str | None = None,
) -> dict[str, object]:
    connection = connect_duckdb(settings.duckdb_path)
    try:
        resolved_symbol = _normalize_watchlist_symbol(connection, symbol)
        resolved_strategy = _normalize_preferred_strategy_name(preferred_strategy_name)
        display_name = _resolve_symbol_display_name(connection, resolved_symbol)
        now_value = _now_isoformat()
        connection.execute(
            """
            INSERT INTO strategy_watchlist (
              symbol,
              preferred_strategy_name,
              created_at,
              updated_at
            ) VALUES (?, ?, ?, ?)
            ON CONFLICT (symbol) DO UPDATE
            SET preferred_strategy_name = EXCLUDED.preferred_strategy_name,
                updated_at = EXCLUDED.updated_at
            """,
            [
                resolved_symbol,
                resolved_strategy,
                now_value,
                now_value,
            ],
        )
    finally:
        connection.close()

    payload = list_strategy_watchlist(settings)
    item = next(
        (entry for entry in payload["items"] if entry["symbol"] == resolved_symbol),
        None,
    )
    if item is None:
        item = {
            "symbol": resolved_symbol,
            "display_name": display_name,
            "preferred_strategy_name": resolved_strategy,
            "strategy_name": "AUTO" if resolved_strategy == "AUTO" else resolved_strategy,
            "monitoring_status": "UNAVAILABLE",
        }
    return item


def remove_strategy_watchlist_item(
    settings: AppSettings,
    *,
    symbol: str,
) -> dict[str, object]:
    connection = connect_duckdb(settings.duckdb_path)
    try:
        resolved_symbol = _normalize_watchlist_symbol(connection, symbol, allow_unknown=True)
        existing_row = connection.execute(
            "SELECT symbol FROM strategy_watchlist WHERE symbol = ? LIMIT 1",
            [resolved_symbol],
        ).fetchone()
        if existing_row is None:
            raise LookupError(f"Symbol is not in strategy watchlist: {resolved_symbol}")
        connection.execute(
            "DELETE FROM strategy_watchlist WHERE symbol = ?",
            [resolved_symbol],
        )
    finally:
        connection.close()

    return {
        "symbol": resolved_symbol,
        "status": "removed",
    }


def emit_strategy_watchlist_alerts(
    settings: AppSettings,
    *,
    snapshot_id: str | None = None,
) -> dict[str, object]:
    current_payload = list_strategy_watchlist(settings, snapshot_id=snapshot_id)
    current_items = current_payload["items"]
    if not current_items:
        return {
            "snapshot_id": current_payload["snapshot_id"],
            "evaluated_count": 0,
            "emitted_count": 0,
            "emitted_symbols": [],
        }

    connection = connect_duckdb(settings.duckdb_path, read_only=True)
    try:
        previous_snapshot = _resolve_previous_ready_snapshot_meta(
            connection,
            snapshot_id=str(current_payload["snapshot_id"]),
        )
    finally:
        connection.close()

    previous_items_by_symbol: dict[str, dict[str, object]] = {}
    if previous_snapshot is not None:
        previous_payload = list_strategy_watchlist(
            settings,
            snapshot_id=str(previous_snapshot["snapshot_id"]),
        )
        previous_items_by_symbol = {
            str(item["symbol"]): item for item in previous_payload["items"]
        }

    emitted_symbols: list[str] = []
    for item in current_items:
        monitoring_status = str(item["monitoring_status"])
        if monitoring_status not in {"BUY", "SELL"}:
            continue

        previous_status = str(
            previous_items_by_symbol.get(str(item["symbol"]), {}).get("monitoring_status")
            or ""
        )
        if previous_status == monitoring_status:
            continue

        current_price = item.get("current_price")
        buy_trigger_price = item.get("buy_trigger_price")
        sell_trigger_price = item.get("sell_trigger_price")
        defensive_exit_price = item.get("defensive_exit_price")
        strategy_name = str(item.get("strategy_name") or "AUTO")
        display_name = str(item.get("display_name") or item["symbol"])
        action_label = "买点触发" if monitoring_status == "BUY" else "风控离场触发"
        emit_alert(
            settings,
            alert_type="strategy_watchlist_signal",
            severity="WARNING",
            message=(
                f"{action_label}: {display_name}({strategy_name}) "
                f"当前价 {current_price if current_price is not None else '--'} "
                f"买点 {buy_trigger_price if buy_trigger_price is not None else '--'} / "
                f"止盈 {sell_trigger_price if sell_trigger_price is not None else '--'} / "
                f"风控 {defensive_exit_price if defensive_exit_price is not None else '--'}"
            ),
            detail={
                "symbol": str(item["symbol"]),
                "display_name": display_name,
                "strategy_name": strategy_name,
                "monitoring_status": monitoring_status,
                "snapshot_id": str(current_payload["snapshot_id"]),
                "trade_date": str(item.get("trade_date")),
                "current_price": current_price,
                "buy_trigger_price": buy_trigger_price,
                "sell_trigger_price": sell_trigger_price,
                "defensive_exit_price": defensive_exit_price,
                "stop_loss_price": item.get("stop_loss_price"),
                "entry_reason": item.get("entry_reason"),
                "exit_reason": item.get("exit_reason"),
            },
        )
        emitted_symbols.append(str(item["symbol"]))

    return {
        "snapshot_id": current_payload["snapshot_id"],
        "evaluated_count": len(current_items),
        "emitted_count": len(emitted_symbols),
        "emitted_symbols": emitted_symbols,
    }


def _evaluate_watchlist_rows(
    connection,
    *,
    watchlist_rows: list[tuple[object, ...]],
    snapshot_meta: dict[str, object],
) -> list[dict[str, object]]:
    if not watchlist_rows:
        return []

    base_rows = connection.execute(
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
            ind.ma10,
            ind.ma20,
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
        latest_fundamental AS (
          SELECT
            ff.symbol,
            ff.report_period,
            ff.fundamental_score,
            ff.debt_to_assets,
            ff.cash_to_profit,
            ROW_NUMBER() OVER (
              PARTITION BY ff.symbol, ff.trade_date
              ORDER BY ap.publish_seq DESC
            ) AS row_num
          FROM fundamental_feature_daily ff
          JOIN artifact_publish ap
            ON ap.snapshot_id = ff.snapshot_id
          WHERE ff.trade_date = CAST(? AS DATE)
            AND ff.snapshot_id = ?
        )
        SELECT
          wl.symbol,
          wl.preferred_strategy_name,
          wl.created_at,
          wl.updated_at,
          sb.display_name,
          sb.exchange,
          sb.industry,
          lb.trade_date,
          lb.close_raw,
          lb.amount,
          lb.is_suspended,
          li.ma5,
          li.ma10,
          li.ma20,
          li.macd_hist,
          li.rsi6,
          li.volume_ratio,
          lc.main_net_inflow_ratio,
          lc.northbound_net_inflow,
          lc.has_dragon_tiger,
          lf.report_period,
          lf.fundamental_score,
          lf.debt_to_assets,
          lf.cash_to_profit
        FROM strategy_watchlist wl
        LEFT JOIN stock_basic sb
          ON sb.symbol = wl.symbol
        LEFT JOIN latest_bar lb
          ON lb.symbol = wl.symbol
         AND lb.row_num = 1
        LEFT JOIN latest_indicator li
          ON li.symbol = wl.symbol
         AND li.row_num = 1
        LEFT JOIN latest_capital lc
          ON lc.symbol = wl.symbol
         AND lc.row_num = 1
        LEFT JOIN latest_fundamental lf
          ON lf.symbol = wl.symbol
         AND lf.row_num = 1
        ORDER BY wl.updated_at DESC, wl.symbol ASC
        """,
        [
            snapshot_meta["raw_snapshot_id"],
            snapshot_meta["biz_date"],
            snapshot_meta["biz_date"],
            snapshot_meta["snapshot_id"],
            snapshot_meta["price_basis"],
            snapshot_meta["biz_date"],
            snapshot_meta["snapshot_id"],
            snapshot_meta["biz_date"],
            snapshot_meta["snapshot_id"],
        ],
    ).fetchall()

    pattern_signal_rows = connection.execute(
        """
        SELECT
          ps.symbol,
          ps.signal_code,
          ps.signal_score,
          ps.payload_json
        FROM pattern_signal_daily ps
        JOIN strategy_watchlist wl
          ON wl.symbol = ps.symbol
        WHERE ps.trade_date = CAST(? AS DATE)
          AND ps.snapshot_id = ?
          AND ps.price_basis = ?
        ORDER BY ps.symbol ASC, ps.signal_code ASC
        """,
        [
            snapshot_meta["biz_date"],
            snapshot_meta["snapshot_id"],
            snapshot_meta["price_basis"],
        ],
    ).fetchall()

    pattern_signals_by_symbol: dict[str, list[dict[str, object]]] = {}
    for symbol, signal_code, signal_score, payload_json in pattern_signal_rows:
        pattern_signals_by_symbol.setdefault(str(symbol), []).append(
            {
                "signal_code": str(signal_code),
                "signal_score": float(signal_score) if signal_score is not None else None,
                "payload": _decode_json_text(payload_json, {}),
            }
        )

    items: list[dict[str, object]] = []
    for row in base_rows:
        (
            symbol,
            preferred_strategy_name,
            created_at,
            updated_at,
            display_name,
            exchange,
            industry,
            trade_date,
            close_raw,
            amount,
            is_suspended,
            ma5,
            ma10,
            ma20,
            macd_hist,
            rsi6,
            volume_ratio,
            main_net_inflow_ratio,
            northbound_net_inflow,
            has_dragon_tiger,
            report_period,
            fundamental_score,
            debt_to_assets,
            cash_to_profit,
        ) = row

        signal_rows = pattern_signals_by_symbol.get(str(symbol), [])
        items.append(
            _build_watchlist_item(
                symbol=str(symbol),
                preferred_strategy_name=_normalize_preferred_strategy_name(
                    preferred_strategy_name
                ),
                created_at=_isoformat(created_at),
                updated_at=_isoformat(updated_at),
                display_name=str(display_name) if display_name is not None else str(symbol),
                exchange=str(exchange) if exchange is not None else None,
                industry=str(industry) if industry is not None else None,
                trade_date=_isoformat(trade_date) if trade_date is not None else None,
                current_price=float(close_raw) if close_raw is not None else None,
                amount=float(amount) if amount is not None else None,
                is_suspended=bool(is_suspended) if is_suspended is not None else False,
                ma5=float(ma5) if ma5 is not None else None,
                ma10=float(ma10) if ma10 is not None else None,
                ma20=float(ma20) if ma20 is not None else None,
                macd_hist=float(macd_hist) if macd_hist is not None else None,
                rsi6=float(rsi6) if rsi6 is not None else None,
                volume_ratio=float(volume_ratio) if volume_ratio is not None else None,
                main_net_inflow_ratio=(
                    float(main_net_inflow_ratio)
                    if main_net_inflow_ratio is not None
                    else None
                ),
                northbound_net_inflow=(
                    float(northbound_net_inflow)
                    if northbound_net_inflow is not None
                    else None
                ),
                has_dragon_tiger=bool(has_dragon_tiger)
                if has_dragon_tiger is not None
                else False,
                report_period=_isoformat(report_period) if report_period is not None else None,
                fundamental_score=(
                    float(fundamental_score) if fundamental_score is not None else None
                ),
                debt_to_assets=(
                    float(debt_to_assets) if debt_to_assets is not None else None
                ),
                cash_to_profit=(
                    float(cash_to_profit) if cash_to_profit is not None else None
                ),
                signal_rows=signal_rows,
                snapshot_id=str(snapshot_meta["snapshot_id"]),
            )
        )

    items.sort(
        key=lambda item: (
            ACTION_PRIORITY.get(str(item["monitoring_status"]), 99),
            -float(item.get("score") or 0.0),
            str(item["symbol"]),
        )
    )
    return items


def _build_watchlist_item(
    *,
    symbol: str,
    preferred_strategy_name: str,
    created_at: str | None,
    updated_at: str | None,
    display_name: str,
    exchange: str | None,
    industry: str | None,
    trade_date: str | None,
    current_price: float | None,
    amount: float | None,
    is_suspended: bool,
    ma5: float | None,
    ma10: float | None,
    ma20: float | None,
    macd_hist: float | None,
    rsi6: float | None,
    volume_ratio: float | None,
    main_net_inflow_ratio: float | None,
    northbound_net_inflow: float | None,
    has_dragon_tiger: bool,
    report_period: str | None,
    fundamental_score: float | None,
    debt_to_assets: float | None,
    cash_to_profit: float | None,
    signal_rows: list[dict[str, object]],
    snapshot_id: str,
) -> dict[str, object]:
    signal_set = {
        str(item["signal_code"])
        for item in signal_rows
        if item.get("signal_code") is not None
    }
    signal_payloads = {
        str(item["signal_code"]): item.get("payload")
        for item in signal_rows
        if item.get("signal_code") is not None
    }

    if trade_date is None or current_price is None:
        return {
            "symbol": symbol,
            "display_name": display_name,
            "exchange": exchange,
            "industry": industry,
            "preferred_strategy_name": preferred_strategy_name,
            "strategy_name": preferred_strategy_name if preferred_strategy_name != "AUTO" else "AUTO",
            "trade_date": None,
            "current_price": None,
            "score": None,
            "monitoring_status": "UNAVAILABLE",
            "entry_status": "UNAVAILABLE",
            "exit_status": "UNAVAILABLE",
            "buy_trigger_price": None,
            "sell_trigger_price": None,
            "defensive_exit_price": None,
            "stop_loss_price": None,
            "entry_reason": "当前快照中没有这只股票的分析产物。",
            "exit_reason": "缺少最新分析产物，无法判断止盈或风控位。",
            "thesis": "当前研究池没有这只股票的最新分析结果。",
            "matched_rules": [],
            "risk_flags": ["不在当前研究池或最新快照缺失"],
            "strategy_scores": {},
            "report_period": report_period,
            "snapshot_id": snapshot_id,
            "created_at": created_at,
            "updated_at": updated_at,
        }

    trend_score = _clamp_score(
        55.0
        + max(macd_hist or 0.0, 0.0) * 120.0
        + max((current_price / float(ma5 or current_price) - 1.0), 0.0) * 1200.0
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
    heuristic_fundamental_score = _clamp_score(
        62.0
        - (6.0 if bool(has_dragon_tiger) else 0.0)
        - (4.0 if float(rsi6 or 50.0) >= 82.0 else 0.0)
    )
    resolved_fundamental_score = _clamp_score(
        float(fundamental_score)
        if fundamental_score is not None
        else heuristic_fundamental_score
    )

    breakout_condition = "breakout_up" in signal_set or current_price >= float(ma5 or current_price) * 1.01
    volume_condition = "volume_expansion" in signal_set or float(volume_ratio or 1.0) >= 1.12
    capital_condition = (
        float(main_net_inflow_ratio or 0.0) > 0.0
        and float(northbound_net_inflow or 0.0) > 0.0
    )

    strategy_scores = {
        "趋势突破": round(
            _clamp_score(
                trend_score * 0.56
                + price_volume_score * 0.29
                + capital_score * 0.10
                + resolved_fundamental_score * 0.05
                + (6.0 if breakout_condition else 0.0)
            ),
            2,
        ),
        "放量启动": round(
            _clamp_score(
                trend_score * 0.18
                + price_volume_score * 0.52
                + capital_score * 0.20
                + resolved_fundamental_score * 0.10
                + (5.0 if volume_condition else 0.0)
            ),
            2,
        ),
        "资金共振": round(
            _clamp_score(
                trend_score * 0.18
                + price_volume_score * 0.12
                + capital_score * 0.58
                + resolved_fundamental_score * 0.12
                + (5.0 if capital_condition else 0.0)
            ),
            2,
        ),
    }

    if preferred_strategy_name == "AUTO":
        strategy_name = max(strategy_scores.items(), key=lambda item: item[1])[0]
    else:
        strategy_name = preferred_strategy_name

    breakout_payload = signal_payloads.get("breakout_up")
    volume_payload = signal_payloads.get("volume_expansion")
    previous_high = _payload_float(breakout_payload, "previous_high")
    previous_close = _payload_float(volume_payload, "previous_close")

    if strategy_name == "趋势突破":
        buy_trigger_price = round(previous_high or float(ma5 or current_price) * 1.01, 2)
        sell_trigger_price, defensive_exit_price, stop_loss_price = _build_trade_plan_prices(
            buy_trigger_price=buy_trigger_price,
            defensive_exit_price=float(ma10 or ma20 or current_price) * 0.995,
            hard_stop_price=min(float(ma10 or current_price), current_price * 0.95),
            minimum_risk_pct=0.035,
            reward_multiple=2.0,
        )
        entry_triggered = breakout_condition and float(macd_hist or 0.0) >= 0.0
        exit_triggered = current_price < defensive_exit_price or (
            float(macd_hist or 0.0) < 0.0 and current_price < float(ma5 or current_price)
        )
        entry_reason = (
            f"突破买点关注 {buy_trigger_price}，要求站上前高/MA5 且 MACD 不转弱。"
        )
        exit_reason = (
            f"止盈先看 {sell_trigger_price}，若跌破风控线 {defensive_exit_price} "
            f"或 MACD 转弱则减仓/离场。"
        )
    elif strategy_name == "放量启动":
        buy_trigger_price = round(
            max(float(previous_close or current_price), float(ma5 or current_price)),
            2,
        )
        sell_trigger_price, defensive_exit_price, stop_loss_price = _build_trade_plan_prices(
            buy_trigger_price=buy_trigger_price,
            defensive_exit_price=float(ma5 or ma10 or current_price) * 0.995,
            hard_stop_price=min(float(ma5 or current_price), current_price * 0.95),
            minimum_risk_pct=0.03,
            reward_multiple=1.8,
        )
        entry_triggered = volume_condition and current_price >= float(ma5 or current_price)
        exit_triggered = (
            current_price < defensive_exit_price
            or float(volume_ratio or 1.0) < 0.9
        )
        entry_reason = (
            f"放量启动买点关注 {buy_trigger_price}，需要量比放大且收盘维持在 MA5 上方。"
        )
        exit_reason = (
            f"止盈先看 {sell_trigger_price}，若缩量跌破风控线 {defensive_exit_price} "
            f"或量能回落过快则离场。"
        )
    else:
        buy_trigger_price = round(float(ma5 or current_price), 2)
        sell_trigger_price, defensive_exit_price, stop_loss_price = _build_trade_plan_prices(
            buy_trigger_price=buy_trigger_price,
            defensive_exit_price=float(ma10 or ma20 or current_price) * 0.995,
            hard_stop_price=min(float(ma10 or current_price), current_price * 0.94),
            minimum_risk_pct=0.04,
            reward_multiple=2.0,
        )
        entry_triggered = capital_condition and current_price >= float(ma5 or current_price)
        exit_triggered = current_price < defensive_exit_price or (
            float(main_net_inflow_ratio or 0.0) <= 0.0
            and float(northbound_net_inflow or 0.0) <= 0.0
        )
        entry_reason = (
            f"资金共振买点关注 {buy_trigger_price}，要求主力与北向同向净流入且价格不弱于 MA5。"
        )
        exit_reason = (
            f"止盈先看 {sell_trigger_price}，若资金共振消失或跌破风控线 {defensive_exit_price} "
            f"则离场。"
        )

    matched_rules = [
        f"strategy:{strategy_name}",
        f"snapshot:{snapshot_id}",
    ]
    if industry:
        matched_rules.append(f"industry:{industry}")
    if amount is not None and amount >= 800_000_000.0:
        matched_rules.append("liquidity_pass")
    for signal_code in sorted(signal_set):
        matched_rules.append(signal_code)
    if float(main_net_inflow_ratio or 0.0) > 0.0:
        matched_rules.append("main_inflow_positive")
    if float(northbound_net_inflow or 0.0) > 0.0:
        matched_rules.append("northbound_positive")
    if report_period is not None:
        matched_rules.append(f"financial_period:{report_period}")

    risk_flags: list[str] = []
    if is_suspended:
        risk_flags.append("停牌状态")
    if amount is not None and amount < 800_000_000.0:
        risk_flags.append("流动性不足")
    if bool(has_dragon_tiger):
        risk_flags.append("龙虎榜波动放大")
    if float(rsi6 or 50.0) >= 82.0:
        risk_flags.append("短线过热")
    if float(volume_ratio or 1.0) >= 1.45:
        risk_flags.append("放量过快")
    if debt_to_assets is not None and float(debt_to_assets) >= 65.0:
        risk_flags.append("资产负债率偏高")
    if cash_to_profit is not None and float(cash_to_profit) < 0.8:
        risk_flags.append("现金流弱于利润")
    if fundamental_score is not None and float(fundamental_score) < 45.0:
        risk_flags.append("财务质量偏弱")

    if is_suspended:
        monitoring_status = "AVOID"
        entry_status = "BLOCKED"
        exit_status = "BLOCKED"
        thesis = f"{display_name} 当前停牌，暂不适合执行买卖点监控。"
    elif exit_triggered:
        monitoring_status = "SELL"
        entry_status = "INACTIVE"
        exit_status = "TRIGGERED"
        thesis = f"{display_name} 当前更接近 {strategy_name} 的卖点条件，应优先看风控离场。"
    elif entry_triggered:
        monitoring_status = "BUY"
        entry_status = "TRIGGERED"
        exit_status = "HOLD"
        thesis = f"{display_name} 当前满足 {strategy_name} 的入场条件，可以按计划执行买点。"
    else:
        monitoring_status = "WATCH"
        entry_status = "WATCHING"
        exit_status = "HOLD"
        thesis = f"{display_name} 仍在等待 {strategy_name} 的触发条件，先按预设买点观察。"

    return {
        "symbol": symbol,
        "display_name": display_name,
        "exchange": exchange,
        "industry": industry,
        "preferred_strategy_name": preferred_strategy_name,
        "strategy_name": strategy_name,
        "trade_date": trade_date,
        "current_price": round(current_price, 2),
        "score": strategy_scores.get(strategy_name),
        "monitoring_status": monitoring_status,
        "entry_status": entry_status,
        "exit_status": exit_status,
        "buy_trigger_price": buy_trigger_price,
        "sell_trigger_price": sell_trigger_price,
        "defensive_exit_price": defensive_exit_price,
        "stop_loss_price": stop_loss_price,
        "entry_reason": entry_reason,
        "exit_reason": exit_reason,
        "thesis": thesis,
        "matched_rules": matched_rules,
        "risk_flags": risk_flags,
        "strategy_scores": strategy_scores,
        "report_period": report_period,
        "snapshot_id": snapshot_id,
        "created_at": created_at,
        "updated_at": updated_at,
    }


def _resolve_snapshot_meta(
    connection,
    *,
    snapshot_id: str | None,
) -> dict[str, object]:
    if snapshot_id is not None:
        row = connection.execute(
            """
            SELECT
              snapshot_id,
              raw_snapshot_id,
              biz_date,
              price_basis,
              published_at
            FROM artifact_publish
            WHERE snapshot_id = ?
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
              biz_date,
              price_basis,
              published_at
            FROM artifact_publish
            WHERE status = 'READY'
            ORDER BY publish_seq DESC
            LIMIT 1
            """
        ).fetchone()
    if row is None:
        raise LookupError(f"Unknown snapshot_id: {snapshot_id or 'latest READY'}")
    resolved_snapshot_id, raw_snapshot_id, biz_date, price_basis, published_at = row
    return {
        "snapshot_id": str(resolved_snapshot_id),
        "raw_snapshot_id": str(raw_snapshot_id),
        "biz_date": _isoformat(biz_date),
        "price_basis": str(price_basis),
        "published_at": _isoformat(published_at),
    }


def _resolve_previous_ready_snapshot_meta(
    connection,
    *,
    snapshot_id: str,
) -> dict[str, object] | None:
    row = connection.execute(
        """
        WITH target AS (
          SELECT publish_seq
          FROM artifact_publish
          WHERE snapshot_id = ?
          LIMIT 1
        )
        SELECT
          ap.snapshot_id,
          ap.raw_snapshot_id,
          ap.biz_date,
          ap.price_basis,
          ap.published_at
        FROM artifact_publish ap
        JOIN target t
          ON ap.publish_seq < t.publish_seq
        WHERE ap.status = 'READY'
        ORDER BY ap.publish_seq DESC
        LIMIT 1
        """,
        [snapshot_id],
    ).fetchone()
    if row is None:
        return None
    resolved_snapshot_id, raw_snapshot_id, biz_date, price_basis, published_at = row
    return {
        "snapshot_id": str(resolved_snapshot_id),
        "raw_snapshot_id": str(raw_snapshot_id),
        "biz_date": _isoformat(biz_date),
        "price_basis": str(price_basis),
        "published_at": _isoformat(published_at),
    }


def _normalize_watchlist_symbol(
    connection,
    raw_symbol: str,
    *,
    allow_unknown: bool = False,
) -> str:
    normalized = raw_symbol.strip().upper()
    if not normalized:
        raise ValueError("symbol is required")

    if "." not in normalized and normalized.isdigit():
        row = connection.execute(
            """
            SELECT symbol
            FROM stock_basic
            WHERE split_part(symbol, '.', 1) = ?
            LIMIT 1
            """,
            [normalized],
        ).fetchone()
        if row is not None:
            normalized = str(row[0])
        elif normalized.startswith(("600", "601", "603", "605", "688")):
            normalized = f"{normalized}.SH"
        else:
            normalized = f"{normalized}.SZ"

    if allow_unknown:
        return normalized

    known_row = connection.execute(
        "SELECT symbol FROM stock_basic WHERE symbol = ? LIMIT 1",
        [normalized],
    ).fetchone()
    if known_row is None:
        raise LookupError(
            f"Unknown symbol or not in current tracked universe: {normalized}"
        )
    return str(known_row[0])


def _resolve_symbol_display_name(connection, symbol: str) -> str:
    row = connection.execute(
        "SELECT display_name FROM stock_basic WHERE symbol = ? LIMIT 1",
        [symbol],
    ).fetchone()
    if row is None:
        return symbol
    return str(row[0])


def _normalize_preferred_strategy_name(raw_name: object) -> str:
    if raw_name is None:
        return "AUTO"
    normalized = str(raw_name).strip() or "AUTO"
    if normalized not in SUPPORTED_MONITOR_STRATEGIES:
        raise ValueError(
            "preferred_strategy_name must be one of: "
            + ", ".join(SUPPORTED_MONITOR_STRATEGIES)
        )
    return normalized


def _clamp_score(value: float) -> float:
    return max(0.0, min(100.0, value))


def _build_trade_plan_prices(
    *,
    buy_trigger_price: float,
    defensive_exit_price: float,
    hard_stop_price: float,
    minimum_risk_pct: float,
    reward_multiple: float,
) -> tuple[float, float, float]:
    normalized_buy = round(max(float(buy_trigger_price), 0.01), 2)
    normalized_defensive_exit = min(
        round(float(defensive_exit_price), 2),
        round(normalized_buy * 0.995, 2),
    )
    normalized_stop_loss = min(
        round(float(hard_stop_price), 2),
        normalized_defensive_exit,
    )
    risk_per_share = max(
        round(normalized_buy - normalized_stop_loss, 2),
        round(normalized_buy * minimum_risk_pct, 2),
    )
    take_profit_price = round(normalized_buy + risk_per_share * reward_multiple, 2)
    return take_profit_price, normalized_defensive_exit, normalized_stop_loss


def _decode_json_text(raw_value: object, default: object) -> object:
    if raw_value is None:
        return default
    try:
        return json.loads(str(raw_value))
    except json.JSONDecodeError:
        return default


def _payload_float(payload: object, field_name: str) -> float | None:
    if not isinstance(payload, dict):
        return None
    value = payload.get(field_name)
    if value is None:
        return None
    return float(value)


def _isoformat(value: object) -> str | None:
    if value is None:
        return None
    if isinstance(value, str):
        return value
    if isinstance(value, datetime):
        return value.isoformat()
    return str(value)


def _now_isoformat() -> str:
    return datetime.now(CN_TZ).isoformat(timespec="seconds")
