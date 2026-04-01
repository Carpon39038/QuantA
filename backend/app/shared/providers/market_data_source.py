from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
import importlib
import json
from pathlib import Path
from typing import Protocol

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
        )


def build_market_data_provider(settings: AppSettings) -> MarketDataProvider:
    provider_name = settings.source_provider
    if provider_name == "fixture_json":
        return FixtureJsonMarketDataProvider(settings)
    if provider_name == "akshare":
        return AkshareMarketDataProvider(settings)
    raise ValueError(f"Unsupported source provider: {provider_name}")


def _to_akshare_hist_symbol(symbol: str) -> str:
    code, _exchange = symbol.split(".")
    return code
