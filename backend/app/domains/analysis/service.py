from __future__ import annotations

from backend.app.app_wiring.settings import AppSettings
from backend.app.domains.market_data.repo import (
    load_stock_capital_flow,
    load_stock_indicators,
    load_stock_kline_asof,
    load_stock_snapshot,
)


def build_market_overview(snapshot: dict[str, object]) -> dict[str, object]:
    return dict(snapshot["market_overview"])


def build_stock_price_volume_analysis(
    settings: AppSettings,
    *,
    symbol: str,
    snapshot_id: str | None = None,
    price_basis: str | None = None,
) -> dict[str, object]:
    snapshot = load_stock_snapshot(
        settings,
        symbol=symbol,
        snapshot_id=snapshot_id,
        price_basis=price_basis,
    )
    kline = load_stock_kline_asof(
        settings,
        symbol=symbol,
        dataset="price_series",
        snapshot_id=snapshot_id,
        price_basis=price_basis,
    )
    indicators = load_stock_indicators(
        settings,
        symbol=symbol,
        snapshot_id=snapshot_id,
        price_basis=price_basis,
    )
    capital_flow = load_stock_capital_flow(
        settings,
        symbol=symbol,
        snapshot_id=snapshot_id,
    )

    daily_bar = _dict_or_none(snapshot.get("latest_daily_bar"))
    latest_price_bar = _dict_or_none(snapshot.get("latest_price_bar"))
    latest_indicator = _dict_or_none(indicators.get("latest_indicator"))
    latest_capital = _dict_or_none(capital_flow.get("latest_capital_feature"))
    latest_patterns = [
        dict(item)
        for item in indicators.get("latest_patterns", [])
        if isinstance(item, dict)
    ]
    triggered_patterns = [
        pattern
        for pattern in latest_patterns
        if bool(pattern.get("is_triggered"))
    ]
    signal_codes = {
        str(pattern.get("signal_code"))
        for pattern in triggered_patterns
        if pattern.get("signal_code") is not None
    }

    close = _float_value(daily_bar, "close_raw")
    pre_close = _float_value(daily_bar, "pre_close_raw")
    change_pct = (
        ((close - pre_close) / pre_close) * 100.0
        if close is not None and pre_close not in (None, 0.0)
        else None
    )
    ma5 = _float_value(latest_indicator, "ma5")
    ma10 = _float_value(latest_indicator, "ma10")
    ma20 = _float_value(latest_indicator, "ma20")
    ma60 = _float_value(latest_indicator, "ma60")
    macd_hist = _float_value(latest_indicator, "macd_hist")
    rsi6 = _float_value(latest_indicator, "rsi6")
    volume_ratio = _float_value(latest_indicator, "volume_ratio")
    amount = _float_value(daily_bar, "amount")
    main_net_inflow_ratio = _float_value(latest_capital, "main_net_inflow_ratio")
    northbound_net_inflow = _float_value(latest_capital, "northbound_net_inflow")

    close_for_basis = _float_value(latest_price_bar, "close") or close
    kline_items = [
        dict(item)
        for item in kline.get("items", [])
        if isinstance(item, dict)
    ]
    return_5d = _window_return_pct(kline_items, 5)
    return_20d = _window_return_pct(kline_items, 20)
    ma5_gap_pct = _gap_pct(close_for_basis, ma5)
    ma20_gap_pct = _gap_pct(close_for_basis, ma20)
    above_ma5 = _gte(close_for_basis, ma5)
    above_ma20 = _gte(close_for_basis, ma20)
    ma_alignment = _ma_alignment(ma5=ma5, ma10=ma10, ma20=ma20, ma60=ma60)
    trend_state = _trend_state(
        close=close_for_basis,
        ma5=ma5,
        ma20=ma20,
        macd_hist=macd_hist,
    )
    volume_state = _volume_state(volume_ratio)
    breakout_up = "breakout_up" in signal_codes or (
        close_for_basis is not None
        and ma5 is not None
        and close_for_basis >= ma5 * 1.01
    )
    volume_expansion = "volume_expansion" in signal_codes or (
        volume_ratio is not None and volume_ratio >= 1.12
    )
    pullback_low_volume = "pullback_low_volume" in signal_codes
    macd_positive = macd_hist is not None and macd_hist >= 0.0

    price_volume_score = _clamp_score(
        38.0
        + (18.0 if above_ma5 else 0.0)
        + (14.0 if above_ma20 else 0.0)
        + (14.0 if macd_positive else 0.0)
        + min(max((volume_ratio or 1.0) - 1.0, 0.0) * 28.0, 16.0)
        + (12.0 if breakout_up else 0.0)
        + (10.0 if volume_expansion else 0.0)
        + (6.0 if pullback_low_volume and above_ma20 else 0.0)
        + max(float(main_net_inflow_ratio or 0.0), 0.0) * 3000.0
    )

    reasons: list[str] = []
    risks: list[str] = []
    if close is not None and change_pct is not None:
        reasons.append(f"收盘 {close:.2f}，日涨跌 {change_pct:+.2f}%。")
    if ma5_gap_pct is not None:
        reasons.append(f"相对 MA5 偏离 {ma5_gap_pct:+.2f}%。")
    if ma20_gap_pct is not None:
        reasons.append(f"相对 MA20 偏离 {ma20_gap_pct:+.2f}%。")
    if volume_ratio is not None:
        reasons.append(f"量比 {volume_ratio:.2f}，{volume_state['label']}。")
    if breakout_up:
        reasons.append("价格处在突破或强于 MA5 的量价结构中。")
    if pullback_low_volume:
        reasons.append("出现缩量回踩信号，适合观察回踩承接。")
    if main_net_inflow_ratio is not None:
        reasons.append(f"主力净流入占比 {main_net_inflow_ratio * 100:.2f}%。")
    if northbound_net_inflow is not None and northbound_net_inflow > 0:
        reasons.append("北向资金同步净流入。")

    if close_for_basis is None or latest_indicator is None:
        action = "UNAVAILABLE"
        title = "量价产物不足"
        risks.append("当前 READY snapshot 缺少日线或技术指标，不能形成量价判断。")
    else:
        if volume_ratio is not None and volume_ratio >= 1.45:
            risks.append("量能放大过快，追高波动风险上升。")
        if rsi6 is not None and rsi6 >= 82.0:
            risks.append("RSI6 处于短线过热区。")
        if amount is not None and amount < 800_000_000.0:
            risks.append("成交额低于 8 亿，流动性确认不足。")
        if ma20 is not None and close_for_basis < ma20:
            risks.append("价格仍在 MA20 下方，中期趋势未修复。")
        if macd_hist is not None and macd_hist < 0:
            risks.append("MACD 柱仍为负，动能未确认转强。")

        if (
            price_volume_score >= 72.0
            and above_ma5
            and above_ma20
            and macd_positive
            and volume_expansion
            and not (rsi6 is not None and rsi6 >= 82.0)
        ):
            action = "BUY"
            title = "量价买点触发"
        elif (
            price_volume_score < 50.0
            or (ma20 is not None and close_for_basis < ma20 and not pullback_low_volume)
            or (macd_hist is not None and macd_hist < 0 and not volume_expansion)
        ):
            action = "AVOID"
            title = "量价结构偏弱"
        else:
            action = "WATCH"
            title = "等待量价确认"

    next_trigger_price = _next_trigger_price(
        close=close_for_basis,
        ma5=ma5,
        ma20=ma20,
        triggered_patterns=triggered_patterns,
    )
    invalidation_price = _invalidation_price(close=close_for_basis, ma5=ma5, ma20=ma20)

    if action == "BUY":
        summary = "价格、均线与量能形成共振，可按买点计划评估仓位。"
    elif action == "WATCH":
        summary = "已有局部量价线索，但还需要突破、放量或均线修复确认。"
    elif action == "AVOID":
        summary = "当前量价结构未达入场条件，优先等待风险释放。"
    else:
        summary = "当前快照缺少足够数据，不能输出买点状态。"

    as_of = dict(snapshot.get("as_of", {})) if isinstance(snapshot.get("as_of"), dict) else {}
    return {
        "symbol": snapshot["symbol"],
        "display_name": snapshot["display_name"],
        "as_of": {
            "snapshot_id": as_of.get("snapshot_id"),
            "raw_snapshot_id": as_of.get("raw_snapshot_id"),
            "trade_date": daily_bar.get("trade_date") if daily_bar else None,
            "price_basis": as_of.get("price_basis"),
        },
        "price_state": {
            "close": close,
            "change_pct": change_pct,
            "ma5_gap_pct": ma5_gap_pct,
            "ma20_gap_pct": ma20_gap_pct,
            "return_5d_pct": return_5d,
            "return_20d_pct": return_20d,
            "ma_alignment": ma_alignment,
            "trend_state": trend_state,
            "above_ma5": above_ma5,
            "above_ma20": above_ma20,
        },
        "volume_state": {
            "volume": _float_value(daily_bar, "volume"),
            "amount": amount,
            "volume_ratio": volume_ratio,
            **volume_state,
        },
        "signals": [
            {
                "signal_code": str(pattern.get("signal_code")),
                "signal_type": str(pattern.get("signal_type")),
                "direction": str(pattern.get("direction")),
                "signal_score": _float_value(pattern, "signal_score"),
            }
            for pattern in triggered_patterns
        ],
        "decision": {
            "action": action,
            "title": title,
            "summary": summary,
            "confidence_score": round(price_volume_score, 2),
            "next_trigger_price": next_trigger_price,
            "invalidation_price": invalidation_price,
            "reasons": reasons[:6],
            "risks": risks,
        },
        "capital_confirmation": {
            "main_net_inflow_ratio": main_net_inflow_ratio,
            "northbound_net_inflow": northbound_net_inflow,
        },
    }


def _dict_or_none(value: object) -> dict[str, object] | None:
    return dict(value) if isinstance(value, dict) else None


def _float_value(payload: dict[str, object] | None, field_name: str) -> float | None:
    if payload is None:
        return None
    value = payload.get(field_name)
    if value is None:
        return None
    return float(value)


def _gap_pct(value: float | None, baseline: float | None) -> float | None:
    if value is None or baseline in (None, 0.0):
        return None
    return ((value - baseline) / baseline) * 100.0


def _gte(value: float | None, baseline: float | None) -> bool:
    return value is not None and baseline is not None and value >= baseline


def _window_return_pct(items: list[dict[str, object]], window: int) -> float | None:
    if len(items) <= window:
        return None
    start_close = _float_value(items[-window - 1], "close")
    end_close = _float_value(items[-1], "close")
    if start_close in (None, 0.0) or end_close is None:
        return None
    return ((end_close - start_close) / start_close) * 100.0


def _ma_alignment(
    *,
    ma5: float | None,
    ma10: float | None,
    ma20: float | None,
    ma60: float | None,
) -> str:
    if None in (ma5, ma10, ma20):
        return "INSUFFICIENT"
    if ma5 >= ma10 >= ma20 and (ma60 is None or ma20 >= ma60):
        return "BULLISH"
    if ma5 <= ma10 <= ma20 and (ma60 is None or ma20 <= ma60):
        return "BEARISH"
    return "MIXED"


def _trend_state(
    *,
    close: float | None,
    ma5: float | None,
    ma20: float | None,
    macd_hist: float | None,
) -> str:
    if close is None or ma5 is None or ma20 is None:
        return "UNKNOWN"
    if close >= ma5 and close >= ma20 and (macd_hist is None or macd_hist >= 0.0):
        return "STRENGTHENING"
    if close >= ma20:
        return "REPAIRING"
    if close < ma20 and (macd_hist is not None and macd_hist < 0.0):
        return "WEAKENING"
    return "NEUTRAL"


def _volume_state(volume_ratio: float | None) -> dict[str, str]:
    if volume_ratio is None:
        return {"state": "UNKNOWN", "label": "量能未知"}
    if volume_ratio >= 1.45:
        return {"state": "OVER_EXPANDED", "label": "放量过快"}
    if volume_ratio >= 1.12:
        return {"state": "EXPANDING", "label": "有效放量"}
    if volume_ratio <= 0.9:
        return {"state": "CONTRACTING", "label": "缩量"}
    return {"state": "NORMAL", "label": "量能平稳"}


def _next_trigger_price(
    *,
    close: float | None,
    ma5: float | None,
    ma20: float | None,
    triggered_patterns: list[dict[str, object]],
) -> float | None:
    for pattern in triggered_patterns:
        payload = pattern.get("payload")
        if isinstance(payload, dict) and payload.get("previous_high") is not None:
            return round(float(payload["previous_high"]), 2)
    candidates = [value for value in (close, ma5, ma20) if value is not None]
    if not candidates:
        return None
    return round(max(candidates), 2)


def _invalidation_price(
    *,
    close: float | None,
    ma5: float | None,
    ma20: float | None,
) -> float | None:
    candidates = [value for value in (ma5, ma20, close) if value is not None]
    if not candidates:
        return None
    return round(min(candidates) * 0.995, 2)


def _clamp_score(value: float) -> float:
    return max(0.0, min(100.0, value))
