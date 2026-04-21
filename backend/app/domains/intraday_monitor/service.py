from __future__ import annotations

from datetime import datetime, timedelta, timezone
import json

from backend.app.app_wiring.settings import AppSettings
from backend.app.domains.strategy_watchlist.service import list_strategy_watchlist
from backend.app.shared.providers.intraday_preview_source import (
    IntradayQuote,
    build_intraday_preview_provider,
)
from backend.app.shared.telemetry.alerts import emit_alert


CN_TZ = timezone(timedelta(hours=8))
INTRADAY_SIGNAL_PRIORITY = (
    "STOP_LOSS_TRIGGERED",
    "RISK_WARNING",
    "TAKE_PROFIT_TRIGGERED",
    "BUY_TRIGGERED",
    "WATCHING",
    "UNAVAILABLE",
)
INTRADAY_ALERTABLE_STAGES = {
    "STOP_LOSS_TRIGGERED",
    "RISK_WARNING",
    "TAKE_PROFIT_TRIGGERED",
    "BUY_TRIGGERED",
}


def preview_strategy_watchlist(
    settings: AppSettings,
    *,
    emit_signal_alerts: bool = False,
) -> dict[str, object]:
    watchlist_payload = list_strategy_watchlist(settings)
    base_items = list(watchlist_payload["items"])
    provider = build_intraday_preview_provider(settings)
    now_value = datetime.now(CN_TZ)
    market_phase = _market_phase(now_value)
    session_active = market_phase in {"open_am", "open_pm"}
    state = _load_intraday_monitor_state(settings, session_date=now_value.date().isoformat())
    emitted_alerts: list[str] = []

    if provider.provider_name == "none":
        return {
            "snapshot_id": watchlist_payload["snapshot_id"],
            "raw_snapshot_id": watchlist_payload["raw_snapshot_id"],
            "as_of_date": watchlist_payload["as_of_date"],
            "items": [],
            "source_status": {
                "provider": provider.provider_name,
                "mode": provider.mode,
                "status": "disabled",
                "message": "未配置盘中预览 provider。",
                "market_phase": market_phase,
                "session_active": session_active,
                "poll_interval_seconds": settings.intraday_preview_poll_interval_seconds,
                "last_updated_at": None,
            },
        }

    if not base_items:
        return {
            "snapshot_id": watchlist_payload["snapshot_id"],
            "raw_snapshot_id": watchlist_payload["raw_snapshot_id"],
            "as_of_date": watchlist_payload["as_of_date"],
            "items": [],
            "source_status": {
                "provider": provider.provider_name,
                "mode": provider.mode,
                "status": "idle",
                "message": "当前没有手动监控的股票。",
                "market_phase": market_phase,
                "session_active": session_active,
                "poll_interval_seconds": settings.intraday_preview_poll_interval_seconds,
                "last_updated_at": None,
            },
        }

    try:
        quotes_by_symbol = provider.fetch_quotes(
            tuple(str(item["symbol"]) for item in base_items)
        )
    except Exception as exc:
        signature = f"{provider.provider_name}:{exc.__class__.__name__}:{exc}"
        if emit_signal_alerts and state.get("provider_error_signature") != signature:
            emit_alert(
                settings,
                alert_type="intraday_preview_provider_degraded",
                severity="WARNING",
                message=f"盘中预览源降级: {provider.provider_name} {exc}",
                detail={
                    "provider": provider.provider_name,
                    "mode": provider.mode,
                    "status": "degraded",
                    "message": str(exc),
                    "market_phase": market_phase,
                },
            )
            state["provider_error_signature"] = signature
            _save_intraday_monitor_state(settings, state)
        return {
            "snapshot_id": watchlist_payload["snapshot_id"],
            "raw_snapshot_id": watchlist_payload["raw_snapshot_id"],
            "as_of_date": watchlist_payload["as_of_date"],
            "items": [],
            "source_status": {
                "provider": provider.provider_name,
                "mode": provider.mode,
                "status": "degraded",
                "message": str(exc),
                "market_phase": market_phase,
                "session_active": session_active,
                "poll_interval_seconds": settings.intraday_preview_poll_interval_seconds,
                "last_updated_at": None,
            },
        }

    state["provider_error_signature"] = None
    evaluated_items = [
        _build_intraday_item(item=item, quote=quotes_by_symbol.get(str(item["symbol"])))
        for item in base_items
    ]
    latest_updated_at = _latest_updated_at(evaluated_items)
    source_status = {
        "provider": provider.provider_name,
        "mode": provider.mode,
        "status": "ok" if quotes_by_symbol else "unavailable",
        "message": (
            "盘中预览已刷新。"
            if quotes_by_symbol
            else "当前未拿到盘中报价，请稍后重试。"
        ),
        "market_phase": market_phase,
        "session_active": session_active,
        "poll_interval_seconds": settings.intraday_preview_poll_interval_seconds,
        "last_updated_at": latest_updated_at,
        "quote_count": len(quotes_by_symbol),
        "watchlist_count": len(base_items),
    }

    if emit_signal_alerts and session_active:
        emitted_alerts = _emit_intraday_threshold_alerts(
            settings,
            state=state,
            items=evaluated_items,
            source_status=source_status,
        )
        _save_intraday_monitor_state(settings, state)
    elif emit_signal_alerts and state.get("provider_error_signature") is not None:
        _save_intraday_monitor_state(settings, state)

    return {
        "snapshot_id": watchlist_payload["snapshot_id"],
        "raw_snapshot_id": watchlist_payload["raw_snapshot_id"],
        "as_of_date": watchlist_payload["as_of_date"],
        "items": evaluated_items,
        "source_status": source_status,
        "emitted_alerts": emitted_alerts,
    }


def run_intraday_monitor_tick(settings: AppSettings) -> dict[str, object]:
    payload = preview_strategy_watchlist(settings, emit_signal_alerts=True)
    return {
        "provider": payload["source_status"]["provider"],
        "status": payload["source_status"]["status"],
        "market_phase": payload["source_status"]["market_phase"],
        "watchlist_count": payload["source_status"].get("watchlist_count", 0),
        "quote_count": payload["source_status"].get("quote_count", 0),
        "emitted_alert_count": len(payload.get("emitted_alerts", [])),
        "last_updated_at": payload["source_status"].get("last_updated_at"),
    }


def _build_intraday_item(
    *,
    item: dict[str, object],
    quote: IntradayQuote | None,
) -> dict[str, object]:
    realtime_price = quote.price if quote is not None else None
    buy_trigger_price = _float_or_none(item.get("buy_trigger_price"))
    take_profit_price = _float_or_none(item.get("sell_trigger_price"))
    defensive_exit_price = _float_or_none(item.get("defensive_exit_price"))
    stop_loss_price = _float_or_none(item.get("stop_loss_price"))

    buy_triggered = bool(
        realtime_price is not None
        and buy_trigger_price is not None
        and realtime_price >= buy_trigger_price
    )
    take_profit_triggered = bool(
        realtime_price is not None
        and take_profit_price is not None
        and realtime_price >= take_profit_price
    )
    risk_warning_triggered = bool(
        realtime_price is not None
        and defensive_exit_price is not None
        and realtime_price <= defensive_exit_price
    )
    stop_loss_triggered = bool(
        realtime_price is not None
        and stop_loss_price is not None
        and realtime_price <= stop_loss_price
    )
    signal_stage = _resolve_intraday_signal_stage(
        quote=quote,
        buy_triggered=buy_triggered,
        take_profit_triggered=take_profit_triggered,
        risk_warning_triggered=risk_warning_triggered,
        stop_loss_triggered=stop_loss_triggered,
    )

    return {
        **item,
        "realtime_price": round(realtime_price, 2) if realtime_price is not None else None,
        "realtime_pct_chg": quote.pct_chg if quote is not None else None,
        "realtime_trade_date": quote.trade_date if quote is not None else None,
        "realtime_trade_time": quote.trade_time if quote is not None else None,
        "realtime_updated_at": quote.updated_at if quote is not None else None,
        "realtime_source": quote.source if quote is not None else None,
        "realtime_status": "ok" if quote is not None else "unavailable",
        "signal_stage": signal_stage,
        "signal_message": _build_intraday_signal_message(
            signal_stage=signal_stage,
            display_name=str(item["display_name"]),
            strategy_name=str(item["strategy_name"]),
            realtime_price=realtime_price,
            buy_trigger_price=buy_trigger_price,
            take_profit_price=take_profit_price,
            defensive_exit_price=defensive_exit_price,
            stop_loss_price=stop_loss_price,
        ),
        "threshold_flags": {
            "buy_triggered": buy_triggered,
            "take_profit_triggered": take_profit_triggered,
            "risk_warning_triggered": risk_warning_triggered,
            "stop_loss_triggered": stop_loss_triggered,
        },
    }


def _emit_intraday_threshold_alerts(
    settings: AppSettings,
    *,
    state: dict[str, object],
    items: list[dict[str, object]],
    source_status: dict[str, object],
) -> list[str]:
    symbol_state_map = state.setdefault("symbols", {})
    if not isinstance(symbol_state_map, dict):
        symbol_state_map = {}
        state["symbols"] = symbol_state_map

    emitted_alerts: list[str] = []
    for item in items:
        signal_stage = str(item["signal_stage"])
        if signal_stage not in INTRADAY_ALERTABLE_STAGES:
            continue

        symbol = str(item["symbol"])
        symbol_state = symbol_state_map.setdefault(symbol, {})
        if not isinstance(symbol_state, dict):
            symbol_state = {}
            symbol_state_map[symbol] = symbol_state
        if bool(symbol_state.get(signal_stage)):
            continue

        severity, alert_type = _alert_meta_for_signal_stage(signal_stage)
        emit_alert(
            settings,
            alert_type=alert_type,
            severity=severity,
            message=str(item["signal_message"]),
            detail={
                "provider": source_status["provider"],
                "mode": source_status["mode"],
                "symbol": symbol,
                "display_name": item["display_name"],
                "strategy_name": item["strategy_name"],
                "signal_stage": signal_stage,
                "snapshot_id": item["snapshot_id"],
                "realtime_price": item["realtime_price"],
                "realtime_updated_at": item["realtime_updated_at"],
                "buy_trigger_price": item["buy_trigger_price"],
                "sell_trigger_price": item["sell_trigger_price"],
                "defensive_exit_price": item.get("defensive_exit_price"),
                "stop_loss_price": item.get("stop_loss_price"),
            },
        )
        symbol_state[signal_stage] = True
        symbol_state["last_signal_stage"] = signal_stage
        symbol_state["last_signal_updated_at"] = item["realtime_updated_at"]
        emitted_alerts.append(f"{symbol}:{signal_stage}")

    return emitted_alerts


def _resolve_intraday_signal_stage(
    *,
    quote: IntradayQuote | None,
    buy_triggered: bool,
    take_profit_triggered: bool,
    risk_warning_triggered: bool,
    stop_loss_triggered: bool,
) -> str:
    if quote is None or quote.price is None:
        return "UNAVAILABLE"
    if stop_loss_triggered:
        return "STOP_LOSS_TRIGGERED"
    if risk_warning_triggered:
        return "RISK_WARNING"
    if take_profit_triggered:
        return "TAKE_PROFIT_TRIGGERED"
    if buy_triggered:
        return "BUY_TRIGGERED"
    return "WATCHING"


def _build_intraday_signal_message(
    *,
    signal_stage: str,
    display_name: str,
    strategy_name: str,
    realtime_price: float | None,
    buy_trigger_price: float | None,
    take_profit_price: float | None,
    defensive_exit_price: float | None,
    stop_loss_price: float | None,
) -> str:
    if signal_stage == "STOP_LOSS_TRIGGERED":
        return (
            f"实盘止损触发: {display_name}({strategy_name}) 盘中价 {realtime_price} "
            f"<= 止损线 {stop_loss_price}"
        )
    if signal_stage == "RISK_WARNING":
        return (
            f"实盘风控预警: {display_name}({strategy_name}) 盘中价 {realtime_price} "
            f"<= 风控线 {defensive_exit_price}"
        )
    if signal_stage == "TAKE_PROFIT_TRIGGERED":
        return (
            f"实盘止盈触发: {display_name}({strategy_name}) 盘中价 {realtime_price} "
            f">= 止盈位 {take_profit_price}"
        )
    if signal_stage == "BUY_TRIGGERED":
        return (
            f"实盘买点触发: {display_name}({strategy_name}) 盘中价 {realtime_price} "
            f">= 买点 {buy_trigger_price}"
        )
    if signal_stage == "UNAVAILABLE":
        return f"{display_name} 当前没有可用盘中报价。"
    return f"{display_name} 盘中未触发新的买卖点。"


def _alert_meta_for_signal_stage(signal_stage: str) -> tuple[str, str]:
    if signal_stage == "STOP_LOSS_TRIGGERED":
        return "ERROR", "intraday_stop_loss_triggered"
    if signal_stage == "RISK_WARNING":
        return "WARNING", "intraday_risk_warning"
    if signal_stage == "TAKE_PROFIT_TRIGGERED":
        return "WARNING", "intraday_take_profit_triggered"
    return "WARNING", "intraday_buy_point_triggered"


def _latest_updated_at(items: list[dict[str, object]]) -> str | None:
    candidates = [
        str(item["realtime_updated_at"])
        for item in items
        if item.get("realtime_updated_at")
    ]
    return max(candidates) if candidates else None


def _load_intraday_monitor_state(
    settings: AppSettings,
    *,
    session_date: str,
) -> dict[str, object]:
    if not settings.intraday_preview_state_path.exists():
        return _default_intraday_monitor_state(session_date=session_date)
    try:
        payload = json.loads(
            settings.intraday_preview_state_path.read_text(encoding="utf-8")
        )
    except json.JSONDecodeError:
        return _default_intraday_monitor_state(session_date=session_date)
    if not isinstance(payload, dict):
        return _default_intraday_monitor_state(session_date=session_date)
    if payload.get("session_date") != session_date:
        return _default_intraday_monitor_state(session_date=session_date)
    payload.setdefault("symbols", {})
    payload.setdefault("provider_error_signature", None)
    return payload


def _save_intraday_monitor_state(
    settings: AppSettings,
    payload: dict[str, object],
) -> None:
    settings.intraday_preview_state_path.parent.mkdir(parents=True, exist_ok=True)
    settings.intraday_preview_state_path.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True),
        encoding="utf-8",
    )


def _default_intraday_monitor_state(*, session_date: str) -> dict[str, object]:
    return {
        "session_date": session_date,
        "provider_error_signature": None,
        "symbols": {},
    }


def _market_phase(now_value: datetime) -> str:
    local_now = now_value.astimezone(CN_TZ)
    weekday = local_now.weekday()
    current_time = local_now.time()
    if weekday >= 5:
        return "closed"
    if current_time < datetime.strptime("09:30:00", "%H:%M:%S").time():
        return "pre_open"
    if current_time <= datetime.strptime("11:30:00", "%H:%M:%S").time():
        return "open_am"
    if current_time < datetime.strptime("13:00:00", "%H:%M:%S").time():
        return "lunch_break"
    if current_time <= datetime.strptime("15:00:00", "%H:%M:%S").time():
        return "open_pm"
    return "closed"


def _float_or_none(raw_value: object) -> float | None:
    if raw_value in {None, ""}:
        return None
    try:
        return float(raw_value)
    except (TypeError, ValueError):
        return None
