from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
import importlib
from typing import Any

from backend.app.app_wiring.settings import AppSettings
from backend.app.shared.providers.local_fixture import load_json_fixture


CN_TZ = timezone(timedelta(hours=8))


@dataclass(frozen=True)
class IntradayQuote:
    symbol: str
    display_name: str | None
    trade_date: str | None
    trade_time: str | None
    updated_at: str | None
    price: float | None
    pre_close: float | None
    open_price: float | None
    high_price: float | None
    low_price: float | None
    volume: float | None
    amount: float | None
    pct_chg: float | None
    source: str


class IntradayPreviewProvider:
    provider_name = "none"
    mode = "disabled"

    def fetch_quotes(
        self,
        symbols: tuple[str, ...],
    ) -> dict[str, IntradayQuote]:
        raise NotImplementedError


class NullIntradayPreviewProvider(IntradayPreviewProvider):
    provider_name = "none"
    mode = "disabled"

    def fetch_quotes(
        self,
        symbols: tuple[str, ...],
    ) -> dict[str, IntradayQuote]:
        return {}


class FixtureJsonIntradayPreviewProvider(IntradayPreviewProvider):
    provider_name = "fixture_json"
    mode = "fixture"

    def __init__(self, settings: AppSettings) -> None:
        self._settings = settings

    def fetch_quotes(
        self,
        symbols: tuple[str, ...],
    ) -> dict[str, IntradayQuote]:
        if not symbols:
            return {}
        payload = load_json_fixture(self._settings.intraday_preview_fixture_path)
        quotes_by_symbol = payload.get("quotes", {})
        if not isinstance(quotes_by_symbol, dict):
            return {}

        normalized_quotes: dict[str, IntradayQuote] = {}
        for symbol in symbols:
            raw_item = quotes_by_symbol.get(symbol)
            if not isinstance(raw_item, dict):
                continue
            normalized_quotes[symbol] = _normalize_quote_row(
                raw_item,
                default_symbol=symbol,
                source="fixture_json",
            )
        return normalized_quotes


class TushareRealtimePreviewProvider(IntradayPreviewProvider):
    provider_name = "tushare_realtime"
    mode = "experimental"

    def __init__(self, settings: AppSettings) -> None:
        if not settings.tushare_token:
            raise ValueError(
                "Tushare realtime preview provider requires QUANTA_TUSHARE_TOKEN"
            )
        self._settings = settings
        self._ts = importlib.import_module("tushare")
        self._ts.set_token(settings.tushare_token)

    def fetch_quotes(
        self,
        symbols: tuple[str, ...],
    ) -> dict[str, IntradayQuote]:
        if not symbols:
            return {}

        normalized_quotes: dict[str, IntradayQuote] = {}
        for chunk in _chunk_symbols(symbols, size=50):
            frame = self._ts.realtime_quote(
                ts_code=",".join(chunk),
                src=self._settings.intraday_preview_tushare_src,
            )
            for item in _frame_records(frame):
                quote = _normalize_quote_row(
                    item,
                    default_symbol=None,
                    source=f"tushare.realtime_quote:{self._settings.intraday_preview_tushare_src}",
                )
                if quote.symbol:
                    normalized_quotes[quote.symbol] = quote
        return normalized_quotes


def build_intraday_preview_provider(
    settings: AppSettings,
) -> IntradayPreviewProvider:
    provider_name = settings.intraday_preview_provider
    if provider_name == "auto":
        if settings.source_provider == "fixture_json":
            provider_name = "fixture_json"
        elif settings.tushare_token:
            provider_name = "tushare_realtime"
        else:
            provider_name = "none"

    if provider_name == "none":
        return NullIntradayPreviewProvider()
    if provider_name == "fixture_json":
        return FixtureJsonIntradayPreviewProvider(settings)
    if provider_name == "tushare_realtime":
        return TushareRealtimePreviewProvider(settings)
    raise ValueError(f"Unsupported intraday preview provider: {provider_name}")


def _chunk_symbols(
    symbols: tuple[str, ...],
    *,
    size: int,
) -> list[tuple[str, ...]]:
    return [
        symbols[index:index + size]
        for index in range(0, len(symbols), size)
    ]


def _frame_records(frame: Any) -> list[dict[str, object]]:
    if frame is None:
        return []
    if getattr(frame, "empty", False):
        return []
    records = frame.to_dict(orient="records")
    return [dict(item) for item in records]


def _normalize_quote_row(
    raw_row: dict[str, object],
    *,
    default_symbol: str | None,
    source: str,
) -> IntradayQuote:
    symbol = (
        _normalize_symbol(_row_value(raw_row, "ts_code"))
        or default_symbol
        or ""
    )
    display_name = _string_or_none(_row_value(raw_row, "name"))
    trade_date = _normalize_trade_date_or_none(_row_value(raw_row, "date"))
    trade_time = _normalize_trade_time_or_none(_row_value(raw_row, "time"))
    updated_at = _compose_updated_at(trade_date, trade_time)
    price = _float_or_none(_row_value(raw_row, "price"))
    pre_close = _float_or_none(_row_value(raw_row, "pre_close"))
    pct_chg = _resolve_pct_chg(price=price, pre_close=pre_close)
    return IntradayQuote(
        symbol=symbol,
        display_name=display_name,
        trade_date=trade_date,
        trade_time=trade_time,
        updated_at=updated_at,
        price=price,
        pre_close=pre_close,
        open_price=_float_or_none(_row_value(raw_row, "open")),
        high_price=_float_or_none(_row_value(raw_row, "high")),
        low_price=_float_or_none(_row_value(raw_row, "low")),
        volume=_float_or_none(_row_value(raw_row, "volume")),
        amount=_float_or_none(_row_value(raw_row, "amount")),
        pct_chg=pct_chg,
        source=source,
    )


def _row_value(raw_row: dict[str, object], field_name: str) -> object:
    if field_name in raw_row:
        return raw_row[field_name]
    upper_name = field_name.upper()
    if upper_name in raw_row:
        return raw_row[upper_name]
    return None


def _normalize_symbol(raw_value: object) -> str | None:
    if raw_value is None:
        return None
    normalized = str(raw_value).strip().upper()
    return normalized or None


def _string_or_none(raw_value: object) -> str | None:
    if raw_value is None:
        return None
    normalized = str(raw_value).strip()
    return normalized or None


def _normalize_trade_date_or_none(raw_value: object) -> str | None:
    normalized = _string_or_none(raw_value)
    if normalized is None:
        return None
    if len(normalized) == 8 and normalized.isdigit():
        return (
            f"{normalized[0:4]}-{normalized[4:6]}-{normalized[6:8]}"
        )
    return normalized


def _normalize_trade_time_or_none(raw_value: object) -> str | None:
    normalized = _string_or_none(raw_value)
    if normalized is None:
        return None
    return normalized


def _compose_updated_at(
    trade_date: str | None,
    trade_time: str | None,
) -> str | None:
    if trade_date is None and trade_time is None:
        return None
    if trade_date is None:
        return trade_time
    if trade_time is None:
        return trade_date
    return f"{trade_date}T{trade_time}+08:00"


def _float_or_none(raw_value: object) -> float | None:
    if raw_value in {None, ""}:
        return None
    try:
        return float(raw_value)
    except (TypeError, ValueError):
        return None


def _resolve_pct_chg(
    *,
    price: float | None,
    pre_close: float | None,
) -> float | None:
    if price is None or pre_close in {None, 0.0}:
        return None
    return round((price - pre_close) / pre_close * 100.0, 2)
