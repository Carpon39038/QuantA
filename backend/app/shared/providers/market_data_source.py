from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime, timedelta, timezone
import importlib
import json
from pathlib import Path
from typing import Any, Protocol

from backend.app.app_wiring.settings import AppSettings
from backend.app.shared.providers.local_fixture import load_json_fixture


CN_TZ = timezone(timedelta(hours=8))


@dataclass(frozen=True)
class MarketDataSnapshot:
    provider: str
    source: str
    biz_date: str
    fetched_at: str
    price_basis: str
    stock_basic: tuple[dict[str, object], ...]
    trade_calendar: dict[str, object]
    daily_bars: tuple[dict[str, object], ...]
    market_overview: dict[str, object]
    source_watermark: dict[str, object]
    capital_feature_overrides: tuple[dict[str, object], ...] = ()
    fundamental_feature_overrides: tuple[dict[str, object], ...] = ()


class MarketDataProvider(Protocol):
    def latest_available_biz_date(self) -> str:
        ...

    def fetch_daily_snapshot(self, biz_date: str | None = None) -> MarketDataSnapshot:
        ...


class FixtureJsonMarketDataProvider:
    def __init__(self, settings: AppSettings) -> None:
        self._settings = settings

    def latest_available_biz_date(self) -> str:
        snapshots = self._list_snapshot_paths()
        if not snapshots:
            raise FileNotFoundError(
                f"No source snapshots found in {self._settings.source_fixture_dir}"
            )
        return snapshots[-1].stem

    def fetch_daily_snapshot(self, biz_date: str | None = None) -> MarketDataSnapshot:
        target_biz_date = biz_date or self.latest_available_biz_date()
        snapshot_path = self._settings.source_fixture_dir / f"{target_biz_date}.json"
        if not snapshot_path.exists():
            raise FileNotFoundError(
                f"No source snapshot fixture found for biz_date={target_biz_date}"
            )

        payload = load_json_fixture(snapshot_path)
        return MarketDataSnapshot(
            provider="fixture_json",
            source=str(payload.get("source", "fixture-json-market-feed")),
            biz_date=str(payload["biz_date"]),
            fetched_at=str(payload["fetched_at"]),
            price_basis=str(payload.get("price_basis", "qfq")),
            stock_basic=tuple(dict(item) for item in list(payload["stock_basic"])),
            trade_calendar=dict(payload["trade_calendar"]),
            daily_bars=tuple(dict(item) for item in list(payload["daily_bars"])),
            market_overview=dict(payload["market_overview"]),
            source_watermark=dict(payload.get("source_watermark", {})),
            capital_feature_overrides=tuple(
                dict(item) for item in list(payload.get("capital_feature_overrides", []))
            ),
            fundamental_feature_overrides=tuple(
                dict(item)
                for item in list(payload.get("fundamental_feature_overrides", []))
            ),
        )

    def _list_snapshot_paths(self) -> list[Path]:
        fixture_dir = self._settings.source_fixture_dir
        if not fixture_dir.exists():
            return []
        return sorted(
            path for path in fixture_dir.glob("*.json") if path.is_file()
        )


class AkshareMarketDataProvider:
    def __init__(self, settings: AppSettings) -> None:
        self._settings = settings
        self._ak = importlib.import_module("akshare")

    def latest_available_biz_date(self) -> str:
        if not self._settings.source_symbols:
            raise ValueError("AKShare provider requires at least one source symbol")

        probe_symbol = _to_akshare_hist_symbol(self._settings.source_symbols[0])
        end_date = datetime.now(CN_TZ).date()
        start_date = end_date - timedelta(days=30)
        frame = self._ak.stock_zh_a_hist(
            symbol=probe_symbol,
            period="daily",
            start_date=start_date.strftime("%Y%m%d"),
            end_date=end_date.strftime("%Y%m%d"),
            adjust="",
        )
        if frame.empty:
            raise RuntimeError(
                f"AKShare provider returned no rows for probe symbol {self._settings.source_symbols[0]} "
                f"between {start_date.isoformat()} and {end_date.isoformat()}"
            )
        return str(frame.iloc[-1]["日期"])

    def fetch_daily_snapshot(self, biz_date: str | None = None) -> MarketDataSnapshot:
        target_biz_date = biz_date or self.latest_available_biz_date()
        symbols = self._settings.source_symbols

        stock_basic = [
            {
                "symbol": symbol,
                "display_name": symbol,
                "exchange": symbol.split(".")[-1],
                "board": "A股",
                "industry": "未知",
                "is_active": True,
            }
            for symbol in symbols
        ]

        daily_bars: list[dict[str, object]] = []
        for symbol in symbols:
            market_symbol = _to_akshare_hist_symbol(symbol)
            frame = self._ak.stock_zh_a_hist(
                symbol=market_symbol,
                period="daily",
                start_date=target_biz_date.replace("-", ""),
                end_date=target_biz_date.replace("-", ""),
                adjust="",
            )
            if frame.empty:
                continue
            row = frame.iloc[-1]
            daily_bars.append(
                {
                    "symbol": symbol,
                    "trade_date": str(row["日期"]),
                    "open_raw": float(row["开盘"]),
                    "high_raw": float(row["最高"]),
                    "low_raw": float(row["最低"]),
                    "close_raw": float(row["收盘"]),
                    "pre_close_raw": float(row["收盘"]) - float(row["涨跌额"]),
                    "volume": float(row["成交量"]),
                    "amount": float(row["成交额"]),
                    "turnover_rate": float(row["换手率"]) if "换手率" in row else None,
                    "high_limit": None,
                    "low_limit": None,
                    "limit_rule_code": "UNKNOWN",
                    "is_suspended": False,
                }
            )

        if not daily_bars:
            raise RuntimeError(
                f"AKShare provider returned no daily bars for biz_date={target_biz_date}"
            )

        fetched_at = datetime.now(CN_TZ).isoformat(timespec="seconds")
        return MarketDataSnapshot(
            provider="akshare",
            source="akshare.stock_zh_a_hist",
            biz_date=target_biz_date,
            fetched_at=fetched_at,
            price_basis="qfq",
            stock_basic=tuple(stock_basic),
            trade_calendar={
                "trade_date": target_biz_date,
                "market_code": "CN-A",
                "is_open": True,
                "updated_at": fetched_at,
            },
            daily_bars=tuple(daily_bars),
            market_overview={
                "trade_date": target_biz_date,
                "summary": f"AKShare 同步 {len(daily_bars)} 只股票日线。",
                "regime_label": "外部同步",
                "snapshot_source": "AKShare market sync",
                "indices": [],
                "breadth": {"advancers": None, "decliners": None},
                "highlights": ["AKShare provider beta"],
            },
            source_watermark={
                "provider": "akshare",
                "fetched_at": fetched_at,
                "symbol_count": len(daily_bars),
            },
            capital_feature_overrides=(),
            fundamental_feature_overrides=(),
        )


class TushareMarketDataProvider:
    def __init__(self, settings: AppSettings) -> None:
        if not settings.tushare_token:
            raise ValueError(
                "Tushare provider requires QUANTA_TUSHARE_TOKEN to be configured"
            )
        self._settings = settings
        self._ts = importlib.import_module("tushare")
        self._pro = self._ts.pro_api(settings.tushare_token)

    def latest_available_biz_date(self) -> str:
        end_date = datetime.now(CN_TZ).date()
        start_date = end_date - timedelta(days=30)
        records = _frame_records(
            self._pro.trade_cal(
                exchange=self._settings.tushare_exchange,
                start_date=start_date.strftime("%Y%m%d"),
                end_date=end_date.strftime("%Y%m%d"),
            )
        )
        open_dates = sorted(
            _normalize_tushare_trade_date(str(item["cal_date"]))
            for item in records
            if _is_tushare_trade_open(item.get("is_open"))
        )
        if not open_dates:
            raise RuntimeError(
                "Tushare provider returned no open trade dates in the recent probe window"
            )
        return open_dates[-1]

    def fetch_daily_snapshot(self, biz_date: str | None = None) -> MarketDataSnapshot:
        target_biz_date = biz_date or self.latest_available_biz_date()
        trade_date = target_biz_date.replace("-", "")
        fetched_at = datetime.now(CN_TZ).isoformat(timespec="seconds")

        stock_basic_records = self._load_stock_basic_records()
        tracked_symbols = {item["symbol"] for item in stock_basic_records}
        if not tracked_symbols:
            raise RuntimeError("Tushare provider returned no stock_basic rows for the configured universe")

        trade_calendar = self._load_trade_calendar_row(
            target_biz_date=target_biz_date,
            fetched_at=fetched_at,
        )
        daily_rows = _index_records_by_key(
            _frame_records(self._pro.daily(trade_date=trade_date)),
            key="ts_code",
        )
        daily_basic_rows = _index_records_by_key(
            _frame_records(self._pro.daily_basic(trade_date=trade_date)),
            key="ts_code",
        )
        stk_limit_rows = _index_records_by_key(
            _frame_records(self._pro.stk_limit(trade_date=trade_date)),
            key="ts_code",
        )
        moneyflow_rows, moneyflow_warning = _load_tushare_optional_records(
            self._pro,
            dataset_name="moneyflow",
            trade_date=trade_date,
        )
        top_list_rows, top_list_warning = _load_tushare_optional_records(
            self._pro,
            dataset_name="top_list",
            trade_date=trade_date,
        )
        moneyflow_hsgt_rows, moneyflow_hsgt_warning = _load_tushare_optional_records(
            self._pro,
            dataset_name="moneyflow_hsgt",
            trade_date=trade_date,
        )
        financial_period_candidates = _candidate_tushare_financial_periods(target_biz_date)
        (
            financial_period,
            fina_indicator_rows,
            fina_indicator_warning,
        ) = _resolve_tushare_financial_period(
            self._pro,
            candidate_periods=financial_period_candidates,
        )
        income_rows, income_warning = _load_tushare_period_records(
            self._pro,
            dataset_name="income_vip",
            period=financial_period,
        )
        balancesheet_rows, balancesheet_warning = _load_tushare_period_records(
            self._pro,
            dataset_name="balancesheet_vip",
            period=financial_period,
        )
        cashflow_rows, cashflow_warning = _load_tushare_period_records(
            self._pro,
            dataset_name="cashflow_vip",
            period=financial_period,
        )

        daily_bars: list[dict[str, object]] = []
        for item in stock_basic_records:
            ts_code = _symbol_to_tushare_code(str(item["symbol"]))
            daily_row = daily_rows.get(ts_code)
            if daily_row is None:
                continue
            daily_basic_row = daily_basic_rows.get(ts_code, {})
            stk_limit_row = stk_limit_rows.get(ts_code, {})
            daily_bars.append(
                {
                    "symbol": str(item["symbol"]),
                    "trade_date": _normalize_tushare_trade_date(str(daily_row["trade_date"])),
                    "open_raw": _float_or_none(daily_row.get("open")),
                    "high_raw": _float_or_none(daily_row.get("high")),
                    "low_raw": _float_or_none(daily_row.get("low")),
                    "close_raw": _float_or_none(daily_row.get("close")),
                    "pre_close_raw": _float_or_none(daily_row.get("pre_close")),
                    "volume": _normalize_tushare_volume(daily_row.get("vol")),
                    "amount": _normalize_tushare_amount(daily_row.get("amount")),
                    "turnover_rate": _float_or_none(daily_basic_row.get("turnover_rate")),
                    "high_limit": _float_or_none(stk_limit_row.get("up_limit")),
                    "low_limit": _float_or_none(stk_limit_row.get("down_limit")),
                    "limit_rule_code": "TUSHARE_STK_LIMIT",
                    "is_suspended": False,
                }
            )

        if not daily_bars:
            raise RuntimeError(
                f"Tushare provider returned no daily bars for biz_date={target_biz_date}"
            )

        advancers = sum(
            1
            for row in daily_bars
            if (row.get("close_raw") or 0.0) > (row.get("pre_close_raw") or 0.0)
        )
        decliners = sum(
            1
            for row in daily_bars
            if (row.get("close_raw") or 0.0) < (row.get("pre_close_raw") or 0.0)
        )
        north_money_million = _extract_tushare_north_money_million(moneyflow_hsgt_rows)
        highlights = [
            "canonical structured source: tushare",
            f"tracked universe size: {len(stock_basic_records)}",
        ]
        warnings = [
            warning
            for warning in (
                moneyflow_warning,
                top_list_warning,
                moneyflow_hsgt_warning,
                fina_indicator_warning,
                income_warning,
                balancesheet_warning,
                cashflow_warning,
            )
            if warning is not None
        ]
        if north_money_million is not None:
            highlights.append(f"north_money_million: {north_money_million:.2f}")
        if financial_period is not None:
            highlights.append(
                f"financial_report_period: {_normalize_tushare_trade_date(financial_period)}"
            )
        highlights.extend(warnings)
        capital_feature_overrides = _build_tushare_capital_feature_overrides(
            daily_bars=daily_bars,
            moneyflow_rows=moneyflow_rows,
            top_list_rows=top_list_rows,
        )
        fundamental_feature_overrides = _build_tushare_fundamental_feature_overrides(
            daily_bars=daily_bars,
            financial_period=financial_period,
            fina_indicator_rows=fina_indicator_rows,
            income_rows=income_rows,
            balancesheet_rows=balancesheet_rows,
            cashflow_rows=cashflow_rows,
        )

        return MarketDataSnapshot(
            provider="tushare",
            source="tushare.pro",
            biz_date=target_biz_date,
            fetched_at=fetched_at,
            price_basis="raw",
            stock_basic=tuple(stock_basic_records),
            trade_calendar=trade_calendar,
            daily_bars=tuple(daily_bars),
            market_overview={
                "trade_date": target_biz_date,
                "summary": (
                    f"Tushare 同步 {len(daily_bars)} 只股票日线，"
                    f"上涨 {advancers} 只，下跌 {decliners} 只。"
                ),
                "regime_label": "盘后结构化同步",
                "snapshot_source": "Tushare Pro market sync",
                "indices": [],
                "breadth": {
                    "advancers": advancers,
                    "decliners": decliners,
                },
                "highlights": highlights,
            },
            source_watermark={
                "provider": "tushare",
                "fetched_at": fetched_at,
                "symbol_count": len(stock_basic_records),
                "daily_bar_count": len(daily_bars),
                "exchange": self._settings.tushare_exchange,
                "moneyflow_count": len(moneyflow_rows),
                "top_list_count": len(top_list_rows),
                "north_money_million": north_money_million,
                "financial_report_period": (
                    _normalize_tushare_trade_date(financial_period)
                    if financial_period is not None
                    else None
                ),
                "fina_indicator_count": len(fina_indicator_rows),
                "income_count": len(income_rows),
                "balancesheet_count": len(balancesheet_rows),
                "cashflow_count": len(cashflow_rows),
                "fundamental_feature_count": len(fundamental_feature_overrides),
                "warnings": warnings,
            },
            capital_feature_overrides=tuple(capital_feature_overrides),
            fundamental_feature_overrides=tuple(fundamental_feature_overrides),
        )

    def _load_stock_basic_records(self) -> list[dict[str, object]]:
        records = _frame_records(
            self._pro.stock_basic(
                exchange="",
                list_status="L",
                fields=(
                    "ts_code,symbol,name,area,industry,market,exchange,list_date"
                ),
            )
        )
        allowed_symbols = set(self._settings.source_symbols)
        filtered_records: list[dict[str, object]] = []
        for item in records:
            symbol = _normalize_tushare_symbol(str(item["ts_code"]))
            if allowed_symbols and symbol not in allowed_symbols:
                continue
            filtered_records.append(
                {
                    "symbol": symbol,
                    "display_name": str(item.get("name") or symbol),
                    "exchange": str(item.get("exchange") or symbol.split(".")[-1]),
                    "board": _map_tushare_market_to_board(item.get("market")),
                    "industry": str(item.get("industry") or "未知"),
                    "is_active": True,
                    "listed_at": _normalize_tushare_trade_date_or_none(
                        item.get("list_date")
                    ),
                }
            )
        return filtered_records

    def _load_trade_calendar_row(
        self,
        *,
        target_biz_date: str,
        fetched_at: str,
    ) -> dict[str, object]:
        records = _frame_records(
            self._pro.trade_cal(
                exchange=self._settings.tushare_exchange,
                start_date=target_biz_date.replace("-", ""),
                end_date=target_biz_date.replace("-", ""),
            )
        )
        if not records:
            raise RuntimeError(
                f"Tushare provider returned no trade calendar row for {target_biz_date}"
            )
        row = records[0]
        if not _is_tushare_trade_open(row.get("is_open")):
            raise RuntimeError(
                f"Tushare provider reports biz_date={target_biz_date} as non-trading day"
            )
        return {
            "trade_date": _normalize_tushare_trade_date(str(row["cal_date"])),
            "market_code": "CN-A",
            "is_open": True,
            "updated_at": fetched_at,
        }


def build_market_data_provider(settings: AppSettings) -> MarketDataProvider:
    provider_name = settings.source_provider
    if provider_name == "fixture_json":
        return FixtureJsonMarketDataProvider(settings)
    if provider_name == "tushare":
        return TushareMarketDataProvider(settings)
    if provider_name == "akshare":
        return AkshareMarketDataProvider(settings)
    raise ValueError(f"Unsupported source provider: {provider_name}")


def _to_akshare_hist_symbol(symbol: str) -> str:
    code, _exchange = symbol.split(".")
    return code


def _frame_records(frame: Any) -> list[dict[str, object]]:
    if frame is None:
        return []
    if getattr(frame, "empty", False):
        return []
    records = frame.to_dict(orient="records")
    return [dict(item) for item in records]


def _index_records_by_key(
    records: list[dict[str, object]],
    *,
    key: str,
) -> dict[str, dict[str, object]]:
    indexed: dict[str, dict[str, object]] = {}
    for item in records:
        raw_value = item.get(key)
        if raw_value is None:
            continue
        indexed[str(raw_value)] = item
    return indexed


def _load_tushare_optional_records(
    pro_client: Any,
    *,
    dataset_name: str,
    trade_date: str,
) -> tuple[list[dict[str, object]], str | None]:
    try:
        method = getattr(pro_client, dataset_name)
        return _frame_records(method(trade_date=trade_date)), None
    except Exception as exc:
        return [], f"{dataset_name}_unavailable:{exc.__class__.__name__}"


def _resolve_tushare_financial_period(
    pro_client: Any,
    *,
    candidate_periods: list[str],
) -> tuple[str | None, list[dict[str, object]], str | None]:
    warnings: list[str] = []
    for period in candidate_periods:
        records, warning = _load_tushare_period_records(
            pro_client,
            dataset_name="fina_indicator_vip",
            period=period,
        )
        if records:
            return period, records, None
        if warning is not None:
            warnings.append(f"{period}:{warning}")

    if warnings:
        return None, [], "fina_indicator_vip_unavailable:" + "|".join(warnings)
    return None, [], "fina_indicator_vip_unavailable:empty_recent_periods"


def _load_tushare_period_records(
    pro_client: Any,
    *,
    dataset_name: str,
    period: str | None,
) -> tuple[list[dict[str, object]], str | None]:
    if period is None:
        return [], f"{dataset_name}_unavailable:no_financial_period"
    try:
        method = getattr(pro_client, dataset_name)
        records = _frame_records(method(period=period))
        if records:
            return records, None
        return [], f"{dataset_name}_unavailable:empty_period"
    except Exception as exc:
        return [], f"{dataset_name}_unavailable:{exc.__class__.__name__}"


def _normalize_tushare_symbol(ts_code: str) -> str:
    return ts_code.strip().upper()


def _symbol_to_tushare_code(symbol: str) -> str:
    return symbol.strip().upper()


def _candidate_tushare_financial_periods(
    biz_date: str,
    *,
    count: int = 6,
) -> list[str]:
    target_date = datetime.fromisoformat(biz_date).date()
    current_period = _quarter_end_on_or_before(target_date)
    periods: list[str] = []
    cursor = current_period
    for _ in range(count):
        periods.append(cursor.strftime("%Y%m%d"))
        cursor = _previous_quarter_end(cursor)
    return periods


def _quarter_end_on_or_before(target_date: date) -> date:
    quarter_ends = [
        date(target_date.year, 3, 31),
        date(target_date.year, 6, 30),
        date(target_date.year, 9, 30),
        date(target_date.year, 12, 31),
    ]
    eligible = [quarter_end for quarter_end in quarter_ends if quarter_end <= target_date]
    if eligible:
        return eligible[-1]
    return date(target_date.year - 1, 12, 31)


def _previous_quarter_end(period_end: date) -> date:
    if period_end.month == 3:
        return date(period_end.year - 1, 12, 31)
    if period_end.month == 6:
        return date(period_end.year, 3, 31)
    if period_end.month == 9:
        return date(period_end.year, 6, 30)
    return date(period_end.year, 9, 30)


def _normalize_tushare_trade_date(raw_value: str) -> str:
    normalized = raw_value.strip()
    if len(normalized) == 8 and normalized.isdigit():
        return f"{normalized[:4]}-{normalized[4:6]}-{normalized[6:8]}"
    return normalized


def _normalize_tushare_trade_date_or_none(raw_value: object) -> str | None:
    if raw_value in (None, ""):
        return None
    return _normalize_tushare_trade_date(str(raw_value))


def _is_tushare_trade_open(raw_value: object) -> bool:
    return str(raw_value) == "1"


def _float_or_none(raw_value: object) -> float | None:
    if raw_value in (None, ""):
        return None
    return float(raw_value)


def _extract_tushare_north_money_million(
    moneyflow_hsgt_rows: list[dict[str, object]],
) -> float | None:
    if not moneyflow_hsgt_rows:
        return None
    row = moneyflow_hsgt_rows[0]
    return _float_or_none(row.get("north_money"))


def _normalize_tushare_volume(raw_value: object) -> float | None:
    value = _float_or_none(raw_value)
    if value is None:
        return None
    return value * 100.0


def _normalize_tushare_amount(raw_value: object) -> float | None:
    value = _float_or_none(raw_value)
    if value is None:
        return None
    return value * 1000.0


def _normalize_tushare_wan_amount(raw_value: object) -> float | None:
    value = _float_or_none(raw_value)
    if value is None:
        return None
    return value * 10000.0


def _map_tushare_market_to_board(raw_value: object) -> str:
    market = str(raw_value or "").strip()
    market_map = {
        "主板": "主板",
        "创业板": "创业板",
        "科创板": "科创板",
        "CDR": "CDR",
        "北交所": "北交所",
    }
    if market in market_map:
        return market_map[market]
    return market or "A股"


def _build_tushare_capital_feature_overrides(
    *,
    daily_bars: list[dict[str, object]],
    moneyflow_rows: list[dict[str, object]],
    top_list_rows: list[dict[str, object]],
) -> list[dict[str, object]]:
    amount_by_symbol = {
        str(row["symbol"]): float(row.get("amount") or 0.0)
        for row in daily_bars
    }
    trade_date_by_symbol = {
        str(row["symbol"]): str(row["trade_date"])
        for row in daily_bars
    }
    moneyflow_by_symbol = {
        _normalize_tushare_symbol(str(item["ts_code"])): item for item in moneyflow_rows
    }
    dragon_tiger_symbols = {
        _normalize_tushare_symbol(str(item["ts_code"])) for item in top_list_rows
    }

    rows: list[dict[str, object]] = []
    for symbol, trade_date in trade_date_by_symbol.items():
        moneyflow_row = moneyflow_by_symbol.get(symbol, {})
        amount = amount_by_symbol.get(symbol, 0.0)

        main_net_inflow = _normalize_tushare_wan_amount(
            moneyflow_row.get("net_mf_amount")
        )
        super_large_order_inflow = None
        if moneyflow_row:
            buy_elg = _normalize_tushare_wan_amount(moneyflow_row.get("buy_elg_amount")) or 0.0
            sell_elg = _normalize_tushare_wan_amount(moneyflow_row.get("sell_elg_amount")) or 0.0
            super_large_order_inflow = buy_elg - sell_elg

        large_order_inflow = None
        if moneyflow_row:
            buy_lg = _normalize_tushare_wan_amount(moneyflow_row.get("buy_lg_amount")) or 0.0
            sell_lg = _normalize_tushare_wan_amount(moneyflow_row.get("sell_lg_amount")) or 0.0
            large_order_inflow = buy_lg - sell_lg

        rows.append(
            {
                "symbol": symbol,
                "trade_date": trade_date,
                "main_net_inflow": main_net_inflow,
                "main_net_inflow_ratio": (
                    float(main_net_inflow / amount)
                    if main_net_inflow is not None and amount
                    else None
                ),
                "super_large_order_inflow": (
                    float(super_large_order_inflow)
                    if super_large_order_inflow is not None
                    else None
                ),
                "large_order_inflow": (
                    float(large_order_inflow)
                    if large_order_inflow is not None
                    else None
                ),
                "has_dragon_tiger": symbol in dragon_tiger_symbols,
            }
        )
    return rows


def _build_tushare_fundamental_feature_overrides(
    *,
    daily_bars: list[dict[str, object]],
    financial_period: str | None,
    fina_indicator_rows: list[dict[str, object]],
    income_rows: list[dict[str, object]],
    balancesheet_rows: list[dict[str, object]],
    cashflow_rows: list[dict[str, object]],
) -> list[dict[str, object]]:
    trade_date_by_symbol = {
        str(row["symbol"]): str(row["trade_date"])
        for row in daily_bars
    }
    fina_indicator_by_symbol = {
        _normalize_tushare_symbol(str(item["ts_code"])): item for item in fina_indicator_rows
    }
    income_by_symbol = {
        _normalize_tushare_symbol(str(item["ts_code"])): item for item in income_rows
    }
    balancesheet_by_symbol = {
        _normalize_tushare_symbol(str(item["ts_code"])): item
        for item in balancesheet_rows
    }
    cashflow_by_symbol = {
        _normalize_tushare_symbol(str(item["ts_code"])): item for item in cashflow_rows
    }

    rows: list[dict[str, object]] = []
    normalized_period = (
        _normalize_tushare_trade_date(financial_period)
        if financial_period is not None
        else None
    )
    for symbol, trade_date in trade_date_by_symbol.items():
        fina_indicator_row = fina_indicator_by_symbol.get(symbol, {})
        income_row = income_by_symbol.get(symbol, {})
        balancesheet_row = balancesheet_by_symbol.get(symbol, {})
        cashflow_row = cashflow_by_symbol.get(symbol, {})

        roe_dt = _float_or_none(fina_indicator_row.get("roe_dt"))
        grossprofit_margin = _float_or_none(
            fina_indicator_row.get("grossprofit_margin")
        )
        total_assets = _float_or_none(balancesheet_row.get("total_assets"))
        total_liab = _float_or_none(balancesheet_row.get("total_liab"))
        debt_to_assets = _float_or_none(fina_indicator_row.get("debt_to_assets"))
        if debt_to_assets is None and total_assets not in (None, 0.0) and total_liab is not None:
            debt_to_assets = float(total_liab / total_assets * 100.0)

        total_revenue = _float_or_none(
            income_row.get("total_revenue")
            if income_row.get("total_revenue") not in (None, "")
            else income_row.get("revenue")
        )
        net_profit_attr_p = _float_or_none(income_row.get("n_income_attr_p"))
        n_cashflow_act = _float_or_none(cashflow_row.get("n_cashflow_act"))
        cash_to_profit = None
        if (
            n_cashflow_act is not None
            and net_profit_attr_p not in (None, 0.0)
        ):
            cash_to_profit = float(n_cashflow_act / net_profit_attr_p)
        elif fina_indicator_row:
            cash_to_profit = _float_or_none(fina_indicator_row.get("ocf_to_profit"))

        fundamental_score = _compute_tushare_fundamental_score(
            roe_dt=roe_dt,
            grossprofit_margin=grossprofit_margin,
            debt_to_assets=debt_to_assets,
            cash_to_profit=cash_to_profit,
        )
        if all(
            value is None
            for value in (
                roe_dt,
                grossprofit_margin,
                debt_to_assets,
                total_revenue,
                net_profit_attr_p,
                n_cashflow_act,
                total_assets,
                total_liab,
                cash_to_profit,
                fundamental_score,
            )
        ):
            continue

        ann_date = _normalize_tushare_trade_date_or_none(
            fina_indicator_row.get("ann_date")
            or income_row.get("ann_date")
            or balancesheet_row.get("ann_date")
            or cashflow_row.get("ann_date")
        )
        rows.append(
            {
                "symbol": symbol,
                "trade_date": trade_date,
                "report_period": normalized_period,
                "ann_date": ann_date,
                "roe_dt": roe_dt,
                "grossprofit_margin": grossprofit_margin,
                "debt_to_assets": debt_to_assets,
                "total_revenue": total_revenue,
                "net_profit_attr_p": net_profit_attr_p,
                "n_cashflow_act": n_cashflow_act,
                "total_assets": total_assets,
                "total_liab": total_liab,
                "cash_to_profit": cash_to_profit,
                "fundamental_score": fundamental_score,
            }
        )
    return rows


def _compute_tushare_fundamental_score(
    *,
    roe_dt: float | None,
    grossprofit_margin: float | None,
    debt_to_assets: float | None,
    cash_to_profit: float | None,
) -> float | None:
    components: list[tuple[float, float]] = []
    if roe_dt is not None:
        components.append((0.35, _bounded_linear_score(roe_dt, low=0.0, high=24.0)))
    if grossprofit_margin is not None:
        components.append(
            (0.2, _bounded_linear_score(grossprofit_margin, low=10.0, high=55.0))
        )
    if debt_to_assets is not None:
        components.append(
            (0.2, _bounded_inverse_score(debt_to_assets, low=20.0, high=80.0))
        )
    if cash_to_profit is not None:
        components.append(
            (0.25, _bounded_linear_score(cash_to_profit, low=0.2, high=1.4))
        )
    if not components:
        return None

    weighted_sum = sum(weight * score for weight, score in components)
    total_weight = sum(weight for weight, _ in components)
    if total_weight <= 0:
        return None
    return round(float(weighted_sum / total_weight), 2)


def _bounded_linear_score(value: float, *, low: float, high: float) -> float:
    if high <= low:
        return 50.0
    normalized = (value - low) / (high - low)
    return max(0.0, min(100.0, normalized * 100.0))


def _bounded_inverse_score(value: float, *, low: float, high: float) -> float:
    if high <= low:
        return 50.0
    normalized = 1.0 - ((value - low) / (high - low))
    return max(0.0, min(100.0, normalized * 100.0))
