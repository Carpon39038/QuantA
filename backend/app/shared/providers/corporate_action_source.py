from __future__ import annotations

from datetime import datetime, timedelta, timezone
import importlib
from typing import Any, Protocol

from backend.app.app_wiring.settings import AppSettings
from backend.app.shared.providers.local_fixture import load_json_fixture
from backend.app.shared.providers.market_data_source import (
    _call_tushare_dataset,
    _float_or_none,
    _frame_records,
    _normalize_tushare_symbol,
    _normalize_tushare_trade_date_or_none,
    _symbol_to_tushare_code,
)


CN_TZ = timezone(timedelta(hours=8))


class CorporateActionProvider(Protocol):
    def fetch_actions(
        self,
        *,
        biz_date: str,
        stock_basic: tuple[dict[str, object], ...],
    ) -> tuple[dict[str, object], ...]:
        ...


class NoneCorporateActionProvider:
    def fetch_actions(
        self,
        *,
        biz_date: str,
        stock_basic: tuple[dict[str, object], ...],
    ) -> tuple[dict[str, object], ...]:
        return ()


class FixtureJsonCorporateActionProvider:
    def __init__(self, settings: AppSettings) -> None:
        self._settings = settings

    def fetch_actions(
        self,
        *,
        biz_date: str,
        stock_basic: tuple[dict[str, object], ...],
    ) -> tuple[dict[str, object], ...]:
        fixture_path = self._settings.corporate_action_fixture_dir / f"{biz_date}.json"
        if not fixture_path.exists():
            return ()

        payload = load_json_fixture(fixture_path)
        raw_items = payload if isinstance(payload, list) else payload.get("items", [])
        items: list[dict[str, object]] = []
        for raw_item in raw_items:
            item = dict(raw_item)
            item.setdefault(
                "action_id",
                _build_action_id(
                    symbol=str(item["symbol"]),
                    report_period=_normalize_tushare_trade_date_or_none(item.get("report_period")),
                    ann_date=_normalize_tushare_trade_date_or_none(item.get("ann_date")),
                    stock_div=_float_or_none(item.get("stock_div")),
                    cash_div_tax=_float_or_none(item.get("cash_div_tax")),
                ),
            )
            item.setdefault("trade_date", biz_date)
            item.setdefault("knowledge_date", item.get("ann_date") or biz_date)
            item.setdefault("action_stage", "ANNOUNCED")
            item.setdefault(
                "action_summary",
                _build_action_summary(
                    stock_div=_float_or_none(item.get("stock_div")),
                    cash_div_tax=_float_or_none(item.get("cash_div_tax")),
                    ex_date=_normalize_tushare_trade_date_or_none(item.get("ex_date")),
                ),
            )
            item.setdefault("source", "fixture_json.corporate_action")
            item.setdefault("updated_at", f"{biz_date}T18:00:00+08:00")
            items.append(item)
        return tuple(items)


class TushareCorporateActionProvider:
    def __init__(self, settings: AppSettings) -> None:
        if not settings.tushare_token:
            raise ValueError(
                "Tushare corporate action provider requires QUANTA_TUSHARE_TOKEN"
            )
        self._settings = settings
        self._ts = importlib.import_module("tushare")
        self._pro = self._ts.pro_api(settings.tushare_token)
        self._dividend_records_by_symbol: dict[str, list[dict[str, object]]] = {}

    def fetch_actions(
        self,
        *,
        biz_date: str,
        stock_basic: tuple[dict[str, object], ...],
    ) -> tuple[dict[str, object], ...]:
        fetched_at = datetime.now(CN_TZ).isoformat(timespec="seconds")
        rows: list[dict[str, object]] = []

        for stock in stock_basic:
            symbol = str(stock["symbol"])
            records = self._load_dividend_records(symbol)
            normalized_rows = _normalize_tushare_dividend_rows(
                symbol=symbol,
                biz_date=biz_date,
                fetched_at=fetched_at,
                rows=records,
            )
            rows.extend(normalized_rows)

        rows.sort(
            key=lambda item: (
                str(item["trade_date"]),
                str(item.get("knowledge_date") or ""),
                str(item["action_id"]),
            )
        )
        return tuple(rows)

    def _load_dividend_records(self, symbol: str) -> list[dict[str, object]]:
        cached_records = self._dividend_records_by_symbol.get(symbol)
        if cached_records is not None:
            return cached_records
        records = _frame_records(
            _call_tushare_dataset(
                self._pro,
                dataset_name="dividend",
                ts_code=_symbol_to_tushare_code(symbol),
                fields=(
                    "ts_code,end_date,ann_date,imp_ann_date,record_date,"
                    "ex_date,pay_date,div_listdate,stk_div,cash_div_tax"
                ),
            )
        )
        self._dividend_records_by_symbol[symbol] = records
        return records


def build_corporate_action_provider(
    settings: AppSettings,
) -> CorporateActionProvider:
    provider_name = settings.corporate_action_provider
    if provider_name == "auto":
        if settings.source_provider == "fixture_json":
            provider_name = "fixture_json"
        elif settings.source_provider == "tushare":
            provider_name = "tushare"
        else:
            provider_name = "none"

    if provider_name == "none":
        return NoneCorporateActionProvider()
    if provider_name == "fixture_json":
        return FixtureJsonCorporateActionProvider(settings)
    if provider_name == "tushare":
        return TushareCorporateActionProvider(settings)
    raise ValueError(f"Unsupported corporate action provider: {provider_name}")


def _normalize_tushare_dividend_rows(
    *,
    symbol: str,
    biz_date: str,
    fetched_at: str,
    rows: list[dict[str, object]],
) -> list[dict[str, object]]:
    deduped: dict[str, dict[str, object]] = {}

    for raw_row in rows:
        ts_code = str(raw_row.get("ts_code") or "").strip()
        if not ts_code or _normalize_tushare_symbol(ts_code) != symbol:
            continue

        report_period = _normalize_tushare_trade_date_or_none(raw_row.get("end_date"))
        ann_date = _normalize_tushare_trade_date_or_none(raw_row.get("ann_date"))
        imp_ann_date = _normalize_tushare_trade_date_or_none(raw_row.get("imp_ann_date"))
        record_date = _normalize_tushare_trade_date_or_none(raw_row.get("record_date"))
        ex_date = _normalize_tushare_trade_date_or_none(raw_row.get("ex_date"))
        pay_date = _normalize_tushare_trade_date_or_none(raw_row.get("pay_date"))
        div_listdate = _normalize_tushare_trade_date_or_none(raw_row.get("div_listdate"))
        stock_div = _float_or_none(raw_row.get("stk_div"))
        cash_div_tax = _float_or_none(raw_row.get("cash_div_tax"))
        knowledge_date = imp_ann_date or ann_date or report_period
        if knowledge_date is None or knowledge_date > biz_date:
            continue

        event_date = ex_date or record_date or pay_date or div_listdate or knowledge_date
        if event_date is None:
            continue

        action_id = _build_action_id(
            symbol=symbol,
            report_period=report_period,
            ann_date=ann_date,
            stock_div=stock_div,
            cash_div_tax=cash_div_tax,
        )
        candidate = {
            "symbol": symbol,
            "trade_date": event_date,
            "action_id": action_id,
            "report_period": report_period,
            "knowledge_date": knowledge_date,
            "ann_date": ann_date,
            "imp_ann_date": imp_ann_date,
            "record_date": record_date,
            "ex_date": ex_date,
            "pay_date": pay_date,
            "div_listdate": div_listdate,
            "stock_div": stock_div,
            "cash_div_tax": cash_div_tax,
            "action_stage": _build_action_stage(
                ex_date=ex_date,
                record_date=record_date,
                pay_date=pay_date,
                div_listdate=div_listdate,
            ),
            "action_summary": _build_action_summary(
                stock_div=stock_div,
                cash_div_tax=cash_div_tax,
                ex_date=ex_date,
            ),
            "source": "tushare.dividend",
            "updated_at": fetched_at,
        }
        existing = deduped.get(action_id)
        if existing is None or _corporate_action_sort_key(candidate) >= _corporate_action_sort_key(existing):
            deduped[action_id] = candidate

    return list(deduped.values())


def _corporate_action_sort_key(row: dict[str, object]) -> tuple[int, int, int, int, str, str]:
    return (
        1 if row.get("ex_date") else 0,
        1 if row.get("record_date") else 0,
        1 if row.get("pay_date") else 0,
        1 if row.get("div_listdate") else 0,
        str(row.get("knowledge_date") or ""),
        str(row.get("trade_date") or ""),
    )


def _build_action_id(
    *,
    symbol: str,
    report_period: str | None,
    ann_date: str | None,
    stock_div: float | None,
    cash_div_tax: float | None,
) -> str:
    return "|".join(
        [
            symbol,
            report_period or "na",
            ann_date or "na",
            f"{stock_div:.4f}" if stock_div is not None else "na",
            f"{cash_div_tax:.4f}" if cash_div_tax is not None else "na",
        ]
    )


def _build_action_stage(
    *,
    ex_date: str | None,
    record_date: str | None,
    pay_date: str | None,
    div_listdate: str | None,
) -> str:
    if ex_date or record_date or pay_date or div_listdate:
        return "IMPLEMENTED"
    return "ANNOUNCED"


def _build_action_summary(
    *,
    stock_div: float | None,
    cash_div_tax: float | None,
    ex_date: str | None,
) -> str:
    parts: list[str] = []
    if cash_div_tax not in (None, 0.0):
        parts.append(f"每10股派现{cash_div_tax:.3f}元")
    if stock_div not in (None, 0.0):
        parts.append(f"每10股送转{stock_div:.3f}股")
    if not parts:
        parts.append("企业行为公告")
    if ex_date:
        parts.append(f"除权除息日 {ex_date}")
    return " · ".join(parts)
