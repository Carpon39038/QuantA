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
TUSHARE_FINANCIAL_DATASETS = (
    "fina_indicator_vip",
    "income_vip",
    "balancesheet_vip",
    "cashflow_vip",
)
TUSHARE_MARKET_INDEXES = (
    ("000001.SH", "上证指数"),
    ("399001.SZ", "深证成指"),
    ("399006.SZ", "创业板指"),
)


class TushareRequestError(RuntimeError):
    def __init__(
        self,
        *,
        dataset_name: str,
        category: str,
        message: str,
    ) -> None:
        super().__init__(f"Tushare {dataset_name} failed [{category}]: {message}")
        self.dataset_name = dataset_name
        self.category = category
        self.message = message


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
    adj_factor_overrides: tuple[dict[str, object], ...] = ()


@dataclass(frozen=True)
class TushareFinancialBundle:
    report_period_by_symbol: dict[str, str]
    fina_indicator_rows: tuple[dict[str, object], ...]
    income_rows: tuple[dict[str, object], ...]
    balancesheet_rows: tuple[dict[str, object], ...]
    cashflow_rows: tuple[dict[str, object], ...]
    warnings: tuple[str, ...] = ()


class MarketDataProvider(Protocol):
    def latest_available_biz_date(self) -> str:
        ...

    def list_open_biz_dates(
        self,
        *,
        start_biz_date: str,
        end_biz_date: str,
    ) -> list[str]:
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

    def list_open_biz_dates(
        self,
        *,
        start_biz_date: str,
        end_biz_date: str,
    ) -> list[str]:
        return [
            path.stem
            for path in self._list_snapshot_paths()
            if start_biz_date <= path.stem <= end_biz_date
        ]

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

    def list_open_biz_dates(
        self,
        *,
        start_biz_date: str,
        end_biz_date: str,
    ) -> list[str]:
        if not self._settings.source_symbols:
            raise ValueError("AKShare provider requires at least one source symbol")
        probe_symbol = _to_akshare_hist_symbol(self._settings.source_symbols[0])
        frame = self._ak.stock_zh_a_hist(
            symbol=probe_symbol,
            period="daily",
            start_date=start_biz_date.replace("-", ""),
            end_date=end_biz_date.replace("-", ""),
            adjust="",
        )
        return sorted(
            {
                str(row["日期"])
                for row in _frame_records(frame)
                if row.get("日期") not in (None, "")
            }
        )

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
            _call_tushare_dataset(
                self._pro,
                dataset_name="trade_cal",
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
        tracked_tushare_codes = {
            _symbol_to_tushare_code(symbol)
            for symbol in self._settings.source_symbols
        }
        for probe_biz_date in reversed(open_dates):
            daily_rows = _index_records_by_key(
                _frame_records(
                    _call_tushare_dataset(
                        self._pro,
                        dataset_name="daily",
                        trade_date=probe_biz_date.replace("-", ""),
                    )
                ),
                key="ts_code",
            )
            if any(ts_code in daily_rows for ts_code in tracked_tushare_codes):
                return probe_biz_date

        raise RuntimeError(
            "Tushare provider found recent open trade dates, but no daily bars for the configured universe"
        )

    def list_open_biz_dates(
        self,
        *,
        start_biz_date: str,
        end_biz_date: str,
    ) -> list[str]:
        records = _frame_records(
            _call_tushare_dataset(
                self._pro,
                dataset_name="trade_cal",
                exchange=self._settings.tushare_exchange,
                start_date=start_biz_date.replace("-", ""),
                end_date=end_biz_date.replace("-", ""),
            )
        )
        return sorted(
            _normalize_tushare_trade_date(str(item["cal_date"]))
            for item in records
            if _is_tushare_trade_open(item.get("is_open"))
        )

    def fetch_daily_snapshot(self, biz_date: str | None = None) -> MarketDataSnapshot:
        target_biz_date = biz_date or self.latest_available_biz_date()
        trade_date = target_biz_date.replace("-", "")
        fetched_at = datetime.now(CN_TZ).isoformat(timespec="seconds")

        stock_basic_records = self._load_stock_basic_records()
        tracked_symbols = {item["symbol"] for item in stock_basic_records}
        if not tracked_symbols:
            raise RuntimeError("Tushare provider returned no stock_basic rows for the configured universe")
        tracked_tushare_codes = {
            _symbol_to_tushare_code(str(item["symbol"]))
            for item in stock_basic_records
        }

        trade_calendar = self._load_trade_calendar_row(
            target_biz_date=target_biz_date,
            fetched_at=fetched_at,
        )
        daily_rows = _index_records_by_key(
            _frame_records(
                _call_tushare_dataset(
                    self._pro,
                    dataset_name="daily",
                    trade_date=trade_date,
                )
            ),
            key="ts_code",
        )
        daily_basic_rows = _index_records_by_key(
            _frame_records(
                _call_tushare_dataset(
                    self._pro,
                    dataset_name="daily_basic",
                    trade_date=trade_date,
                )
            ),
            key="ts_code",
        )
        stk_limit_rows = _index_records_by_key(
            _frame_records(
                _call_tushare_dataset(
                    self._pro,
                    dataset_name="stk_limit",
                    trade_date=trade_date,
                )
            ),
            key="ts_code",
        )
        moneyflow_rows, moneyflow_warning = _load_tushare_optional_records(
            self._pro,
            dataset_name="moneyflow",
            trade_date=trade_date,
        )
        adj_factor_rows, adj_factor_warning = _load_tushare_optional_records(
            self._pro,
            dataset_name="adj_factor",
            trade_date=trade_date,
        )
        top_list_rows, top_list_warning = _load_tushare_optional_records(
            self._pro,
            dataset_name="top_list",
            trade_date=trade_date,
        )
        suspend_rows, suspend_warning = _load_tushare_optional_records(
            self._pro,
            dataset_name="suspend_d",
            trade_date=trade_date,
        )
        moneyflow_hsgt_rows, moneyflow_hsgt_warning = _load_tushare_optional_records(
            self._pro,
            dataset_name="moneyflow_hsgt",
            trade_date=trade_date,
        )
        index_daily_rows, index_daily_warning = _load_tushare_optional_records(
            self._pro,
            dataset_name="index_daily",
            trade_date=trade_date,
        )
        adj_factor_by_symbol = {
            _normalize_tushare_symbol(str(row["ts_code"])): _float_or_none(
                row.get("adj_factor")
            )
            for row in adj_factor_rows
            if row.get("ts_code") not in (None, "")
            and _normalize_tushare_symbol(str(row["ts_code"])) in tracked_symbols
        }
        suspended_symbols = {
            _normalize_tushare_symbol(str(row["ts_code"]))
            for row in suspend_rows
            if row.get("ts_code") not in (None, "")
            and str(row.get("suspend_type") or "").upper() == "S"
            and _normalize_tushare_symbol(str(row["ts_code"])) in tracked_symbols
        }
        financial_period_candidates = _candidate_tushare_financial_periods(target_biz_date)
        financial_bundle = _resolve_tushare_financial_bundle(
            self._pro,
            candidate_periods=financial_period_candidates,
            tracked_symbols=tracked_tushare_codes,
        )
        financial_period_by_symbol = {
            symbol: _normalize_tushare_trade_date(period)
            for symbol, period in sorted(financial_bundle.report_period_by_symbol.items())
        }
        financial_periods = sorted(
            set(financial_period_by_symbol.values()),
            reverse=True,
        )
        missing_financial_symbols = sorted(
            tracked_symbols.difference(set(financial_period_by_symbol))
        )

        daily_bars: list[dict[str, object]] = []
        for item in stock_basic_records:
            ts_code = _symbol_to_tushare_code(str(item["symbol"]))
            daily_row = daily_rows.get(ts_code)
            if daily_row is None:
                continue
            daily_basic_row = daily_basic_rows.get(ts_code, {})
            stk_limit_row = stk_limit_rows.get(ts_code, {})
            limit_rule_code = _limit_rule_code_for_board(str(item["board"]))
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
                    "limit_rule_code": limit_rule_code,
                    "is_suspended": str(item["symbol"]) in suspended_symbols,
                    "adj_factor": adj_factor_by_symbol.get(str(item["symbol"])),
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
        market_indices, market_index_warnings = _build_tushare_market_indices(
            index_daily_rows
        )
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
                index_daily_warning,
                adj_factor_warning,
                suspend_warning,
                *financial_bundle.warnings,
                *market_index_warnings,
            )
            if warning is not None
        ]
        if north_money_million is not None:
            highlights.append(f"north_money_million: {north_money_million:.2f}")
        highlights.append(
            f"market_index_coverage: {len(market_indices)}/{len(TUSHARE_MARKET_INDEXES)}"
        )
        highlights.append(
            f"adj_factor_coverage: {len(adj_factor_by_symbol)}/{len(stock_basic_records)}"
        )
        highlights.append(f"suspended_symbol_count: {len(suspended_symbols)}")
        if financial_periods:
            if len(financial_periods) == 1:
                highlights.append(f"financial_report_period: {financial_periods[0]}")
            else:
                highlights.append(
                    "financial_report_periods: " + ", ".join(financial_periods)
                )
            highlights.append(
                f"financial_sidecar_coverage: {len(financial_period_by_symbol)}/{len(stock_basic_records)}"
            )
        highlights.extend(warnings)
        capital_feature_overrides = _build_tushare_capital_feature_overrides(
            daily_bars=daily_bars,
            moneyflow_rows=moneyflow_rows,
            top_list_rows=top_list_rows,
        )
        adj_factor_overrides = tuple(
            {
                "symbol": symbol,
                "trade_date": target_biz_date,
                "adj_factor": adj_factor,
            }
            for symbol, adj_factor in sorted(adj_factor_by_symbol.items())
            if adj_factor is not None
        )
        fundamental_feature_overrides = _build_tushare_fundamental_feature_overrides(
            daily_bars=daily_bars,
            report_period_by_symbol=financial_bundle.report_period_by_symbol,
            fina_indicator_rows=list(financial_bundle.fina_indicator_rows),
            income_rows=list(financial_bundle.income_rows),
            balancesheet_rows=list(financial_bundle.balancesheet_rows),
            cashflow_rows=list(financial_bundle.cashflow_rows),
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
                "indices": market_indices,
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
                "market_index_count": len(market_indices),
                "market_index_symbols": [
                    str(item["code"]) for item in market_indices if item.get("code")
                ],
                "adj_factor_count": len(adj_factor_overrides),
                "adj_factor_missing_symbols": sorted(
                    tracked_symbols.difference(set(adj_factor_by_symbol))
                ),
                "top_list_count": len(top_list_rows),
                "north_money_million": north_money_million,
                "suspended_symbol_count": len(suspended_symbols),
                "suspended_symbols": sorted(suspended_symbols),
                "financial_report_period": (
                    financial_periods[0] if financial_periods else None
                ),
                "financial_report_periods": financial_periods,
                "financial_report_period_by_symbol": financial_period_by_symbol,
                "financial_missing_symbols": missing_financial_symbols,
                "fina_indicator_count": len(financial_bundle.fina_indicator_rows),
                "income_count": len(financial_bundle.income_rows),
                "balancesheet_count": len(financial_bundle.balancesheet_rows),
                "cashflow_count": len(financial_bundle.cashflow_rows),
                "fundamental_feature_count": len(fundamental_feature_overrides),
                "warnings": warnings,
            },
            capital_feature_overrides=tuple(capital_feature_overrides),
            fundamental_feature_overrides=tuple(fundamental_feature_overrides),
            adj_factor_overrides=adj_factor_overrides,
        )

    def _load_stock_basic_records(self) -> list[dict[str, object]]:
        records = _frame_records(
            _call_tushare_dataset(
                self._pro,
                dataset_name="stock_basic",
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
            _call_tushare_dataset(
                self._pro,
                dataset_name="trade_cal",
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
        return _frame_records(
            _call_tushare_dataset(
                pro_client,
                dataset_name=dataset_name,
                trade_date=trade_date,
            )
        ), None
    except TushareRequestError as exc:
        return [], f"{dataset_name}_unavailable:{exc.category}"


def _resolve_tushare_financial_bundle(
    pro_client: Any,
    *,
    candidate_periods: list[str],
    tracked_symbols: set[str],
) -> TushareFinancialBundle:
    unresolved_symbols = set(tracked_symbols)
    selected_period_by_symbol: dict[str, str] = {}
    selected_rows_by_dataset: dict[str, dict[str, dict[str, object]]] = {
        dataset_name: {}
        for dataset_name in TUSHARE_FINANCIAL_DATASETS
    }
    dataset_has_rows = {
        dataset_name: False
        for dataset_name in TUSHARE_FINANCIAL_DATASETS
    }
    dataset_request_warnings = {
        dataset_name: set()
        for dataset_name in TUSHARE_FINANCIAL_DATASETS
    }

    for period in candidate_periods:
        period_rows_by_dataset: dict[str, dict[str, dict[str, object]]] = {}
        for dataset_name in TUSHARE_FINANCIAL_DATASETS:
            records, warning = _load_tushare_period_records(
                pro_client,
                dataset_name=dataset_name,
                period=period,
            )
            if records:
                dataset_has_rows[dataset_name] = True
            if warning is not None and not warning.endswith("empty_period"):
                dataset_request_warnings[dataset_name].add(warning)
            period_rows_by_dataset[dataset_name] = _index_tushare_records_by_symbol(
                records
            )

        period_symbols = set()
        for dataset_name in TUSHARE_FINANCIAL_DATASETS:
            period_symbols.update(period_rows_by_dataset[dataset_name])
        eligible_symbols = sorted(period_symbols.intersection(unresolved_symbols))
        for symbol in eligible_symbols:
            selected_period_by_symbol[symbol] = period
            for dataset_name in TUSHARE_FINANCIAL_DATASETS:
                row = period_rows_by_dataset[dataset_name].get(symbol)
                if row is not None:
                    selected_rows_by_dataset[dataset_name][symbol] = row
            unresolved_symbols.remove(symbol)

        if not unresolved_symbols:
            break

    warnings: list[str] = []
    for dataset_name in TUSHARE_FINANCIAL_DATASETS:
        if dataset_has_rows[dataset_name]:
            continue
        if dataset_request_warnings[dataset_name]:
            warnings.append(sorted(dataset_request_warnings[dataset_name])[0])
        else:
            warnings.append(f"{dataset_name}_unavailable:empty_recent_periods")
    if unresolved_symbols:
        warnings.append("financial_sidecar_missing:" + ",".join(sorted(unresolved_symbols)))

    return TushareFinancialBundle(
        report_period_by_symbol={
            symbol: selected_period_by_symbol[symbol]
            for symbol in sorted(selected_period_by_symbol)
        },
        fina_indicator_rows=tuple(
            selected_rows_by_dataset["fina_indicator_vip"][symbol]
            for symbol in sorted(selected_rows_by_dataset["fina_indicator_vip"])
        ),
        income_rows=tuple(
            selected_rows_by_dataset["income_vip"][symbol]
            for symbol in sorted(selected_rows_by_dataset["income_vip"])
        ),
        balancesheet_rows=tuple(
            selected_rows_by_dataset["balancesheet_vip"][symbol]
            for symbol in sorted(selected_rows_by_dataset["balancesheet_vip"])
        ),
        cashflow_rows=tuple(
            selected_rows_by_dataset["cashflow_vip"][symbol]
            for symbol in sorted(selected_rows_by_dataset["cashflow_vip"])
        ),
        warnings=tuple(warnings),
    )


def _load_tushare_period_records(
    pro_client: Any,
    *,
    dataset_name: str,
    period: str | None,
) -> tuple[list[dict[str, object]], str | None]:
    if period is None:
        return [], f"{dataset_name}_unavailable:no_financial_period"
    try:
        records = _frame_records(
            _call_tushare_dataset(
                pro_client,
                dataset_name=dataset_name,
                period=period,
            )
        )
        if records:
            return records, None
        return [], f"{dataset_name}_unavailable:empty_period"
    except TushareRequestError as exc:
        return [], f"{dataset_name}_unavailable:{exc.category}"


def _index_tushare_records_by_symbol(
    records: list[dict[str, object]],
) -> dict[str, dict[str, object]]:
    indexed: dict[str, dict[str, object]] = {}
    for item in records:
        ts_code = item.get("ts_code")
        if ts_code in (None, ""):
            continue
        symbol = _normalize_tushare_symbol(str(ts_code))
        existing = indexed.get(symbol)
        if existing is None or _tushare_record_sort_key(item) >= _tushare_record_sort_key(existing):
            indexed[symbol] = item
    return indexed


def _tushare_record_sort_key(item: dict[str, object]) -> tuple[str, str, str]:
    return (
        _normalize_tushare_sortable_date(item.get("f_ann_date")),
        _normalize_tushare_sortable_date(item.get("ann_date")),
        _normalize_tushare_sortable_date(item.get("end_date")),
    )


def _normalize_tushare_sortable_date(raw_value: object) -> str:
    if raw_value in (None, ""):
        return ""
    normalized = str(raw_value).strip()
    if len(normalized) == 10 and normalized.count("-") == 2:
        return normalized.replace("-", "")
    return normalized


def _call_tushare_dataset(
    pro_client: Any,
    *,
    dataset_name: str,
    **kwargs: object,
):
    try:
        method = getattr(pro_client, dataset_name)
        return method(**kwargs)
    except Exception as exc:
        raise _wrap_tushare_request_error(dataset_name, exc) from exc


def _wrap_tushare_request_error(
    dataset_name: str,
    exc: Exception,
) -> TushareRequestError:
    message = str(exc).strip() or exc.__class__.__name__
    normalized_message = message.lower()
    category = "request_failed"

    if "没有接口访问权限" in message:
        category = "permission_denied"
    elif "积分" in message or "权限" in message:
        category = "permission_denied"
    elif "proxy" in normalized_message:
        category = "proxy_error"
    elif "nameresolutionerror" in normalized_message or "nodename nor servname" in normalized_message:
        category = "dns_error"
    elif "connection" in normalized_message:
        category = "connection_error"

    return TushareRequestError(
        dataset_name=dataset_name,
        category=category,
        message=message,
    )


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


def _build_tushare_market_indices(
    index_daily_rows: list[dict[str, object]],
) -> tuple[list[dict[str, object]], list[str]]:
    indexed_rows = _index_records_by_key(index_daily_rows, key="ts_code")
    items: list[dict[str, object]] = []
    missing_codes: list[str] = []
    for code, name in TUSHARE_MARKET_INDEXES:
        row = indexed_rows.get(code)
        if row is None:
            missing_codes.append(code)
            continue
        close = _float_or_none(row.get("close"))
        change_pct = _resolve_tushare_index_change_pct(row)
        if close is None or change_pct is None:
            missing_codes.append(code)
            continue
        items.append(
            {
                "code": code,
                "name": name,
                "close": close,
                "change_pct": change_pct,
                "commentary": _build_tushare_index_commentary(change_pct),
            }
        )

    warnings: list[str] = []
    if missing_codes:
        warnings.append("index_daily_missing:" + ",".join(missing_codes))
    return items, warnings


def _resolve_tushare_index_change_pct(row: dict[str, object]) -> float | None:
    pct_chg = _float_or_none(row.get("pct_chg"))
    if pct_chg is not None:
        return pct_chg
    close = _float_or_none(row.get("close"))
    pre_close = _float_or_none(row.get("pre_close"))
    if close is None or pre_close in (None, 0.0):
        return None
    return (close - pre_close) / pre_close * 100.0


def _build_tushare_index_commentary(change_pct: float) -> str:
    if change_pct >= 1.0:
        return "日内走强，盘后环境偏积极。"
    if change_pct >= 0.0:
        return "小幅收红，修复节奏仍在。"
    if change_pct > -1.0:
        return "窄幅整理，情绪仍偏谨慎。"
    return "回撤偏明显，次日承接需观察。"


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


def _limit_rule_code_for_board(board: str) -> str:
    normalized = board.strip()
    if normalized in {"创业板", "科创板"}:
        return "20pct"
    if normalized == "北交所":
        return "30pct"
    return "10pct"


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
    report_period_by_symbol: dict[str, str],
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
    normalized_period_by_symbol = {
        symbol: _normalize_tushare_trade_date(period)
        for symbol, period in report_period_by_symbol.items()
    }
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
                "report_period": normalized_period_by_symbol.get(symbol),
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
