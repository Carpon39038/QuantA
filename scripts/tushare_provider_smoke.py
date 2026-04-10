#!/usr/bin/env python3

from __future__ import annotations

import os
from pathlib import Path
import sys
import types


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))


from backend.app.app_wiring.settings import load_settings
from backend.app.shared.providers.market_data_source import build_market_data_provider


class FakeFrame:
    def __init__(self, records: list[dict[str, object]]) -> None:
        self._records = [dict(item) for item in records]

    @property
    def empty(self) -> bool:
        return not self._records

    def to_dict(self, orient: str = "records") -> list[dict[str, object]]:
        if orient != "records":
            raise ValueError(f"unsupported orient: {orient}")
        return [dict(item) for item in self._records]


class FakeTusharePro:
    def trade_cal(self, **kwargs) -> FakeFrame:
        start_date = kwargs.get("start_date")
        end_date = kwargs.get("end_date")
        if start_date == "20260401" and end_date == "20260401":
            return FakeFrame(
                [
                    {
                        "exchange": "SSE",
                        "cal_date": "20260401",
                        "is_open": "1",
                        "pretrade_date": "20260331",
                    }
                ]
            )
        return FakeFrame(
            [
                {
                    "exchange": "SSE",
                    "cal_date": "20260331",
                    "is_open": "1",
                    "pretrade_date": "20260328",
                },
                {
                    "exchange": "SSE",
                    "cal_date": "20260401",
                    "is_open": "1",
                    "pretrade_date": "20260331",
                },
            ]
        )

    def stock_basic(self, **kwargs) -> FakeFrame:
        return FakeFrame(
            [
                {
                    "ts_code": "300750.SZ",
                    "symbol": "300750",
                    "name": "宁德时代",
                    "area": "福建",
                    "industry": "电池",
                    "market": "创业板",
                    "exchange": "SZ",
                    "list_date": "20180611",
                },
                {
                    "ts_code": "002475.SZ",
                    "symbol": "002475",
                    "name": "立讯精密",
                    "area": "广东",
                    "industry": "消费电子",
                    "market": "主板",
                    "exchange": "SZ",
                    "list_date": "20100915",
                },
                {
                    "ts_code": "600519.SH",
                    "symbol": "600519",
                    "name": "贵州茅台",
                    "area": "贵州",
                    "industry": "白酒",
                    "market": "主板",
                    "exchange": "SH",
                    "list_date": "20010827",
                },
            ]
        )

    def daily(self, **kwargs) -> FakeFrame:
        assert kwargs.get("trade_date") == "20260401"
        return FakeFrame(
            [
                {
                    "ts_code": "300750.SZ",
                    "trade_date": "20260401",
                    "open": 262.1,
                    "high": 266.8,
                    "low": 260.3,
                    "close": 265.7,
                    "pre_close": 260.1,
                    "vol": 182345.67,
                    "amount": 4912356.0,
                },
                {
                    "ts_code": "002475.SZ",
                    "trade_date": "20260401",
                    "open": 34.91,
                    "high": 35.66,
                    "low": 34.52,
                    "close": 35.22,
                    "pre_close": 34.87,
                    "vol": 256789.01,
                    "amount": 892341.2,
                },
            ]
        )

    def daily_basic(self, **kwargs) -> FakeFrame:
        assert kwargs.get("trade_date") == "20260401"
        return FakeFrame(
            [
                {
                    "ts_code": "300750.SZ",
                    "trade_date": "20260401",
                    "turnover_rate": 3.46,
                },
                {
                    "ts_code": "002475.SZ",
                    "trade_date": "20260401",
                    "turnover_rate": 1.82,
                },
            ]
        )

    def stk_limit(self, **kwargs) -> FakeFrame:
        assert kwargs.get("trade_date") == "20260401"
        return FakeFrame(
            [
                {
                    "ts_code": "300750.SZ",
                    "trade_date": "20260401",
                    "up_limit": 286.11,
                    "down_limit": 234.09,
                },
                {
                    "ts_code": "002475.SZ",
                    "trade_date": "20260401",
                    "up_limit": 38.36,
                    "down_limit": 31.38,
                },
            ]
        )

    def moneyflow(self, **kwargs) -> FakeFrame:
        assert kwargs.get("trade_date") == "20260401"
        return FakeFrame(
            [
                {
                    "ts_code": "300750.SZ",
                    "trade_date": "20260401",
                    "buy_lg_amount": 8200.5,
                    "sell_lg_amount": 2100.2,
                    "buy_elg_amount": 5100.8,
                    "sell_elg_amount": 900.3,
                    "net_mf_amount": 9600.6,
                },
                {
                    "ts_code": "002475.SZ",
                    "trade_date": "20260401",
                    "buy_lg_amount": 2100.0,
                    "sell_lg_amount": 1800.0,
                    "buy_elg_amount": 1200.0,
                    "sell_elg_amount": 950.0,
                    "net_mf_amount": 450.5,
                },
            ]
        )

    def top_list(self, **kwargs) -> FakeFrame:
        assert kwargs.get("trade_date") == "20260401"
        return FakeFrame(
            [
                {
                    "ts_code": "300750.SZ",
                    "trade_date": "20260401",
                    "name": "宁德时代",
                    "reason": "日涨幅偏离值达7%",
                }
            ]
        )

    def moneyflow_hsgt(self, **kwargs) -> FakeFrame:
        assert kwargs.get("trade_date") == "20260401"
        return FakeFrame(
            [
                {
                    "trade_date": "20260401",
                    "north_money": 128.6,
                    "south_money": -17.2,
                    "hgt": 76.1,
                    "sgt": 52.5,
                }
            ]
        )

    def index_daily(self, **kwargs) -> FakeFrame:
        assert kwargs.get("trade_date") == "20260401"
        records = {
            "000001.SH": {
                "ts_code": "000001.SH",
                "trade_date": "20260401",
                "close": 3348.72,
                "pre_close": 3361.49,
                "pct_chg": -0.38,
            },
            "399001.SZ": {
                "ts_code": "399001.SZ",
                "trade_date": "20260401",
                "close": 10492.15,
                "pre_close": 10466.99,
                "pct_chg": 0.24,
            },
            "399006.SZ": {
                "ts_code": "399006.SZ",
                "trade_date": "20260401",
                "close": 2198.44,
                "pre_close": 2178.62,
                "pct_chg": 0.91,
            },
        }
        ts_code = kwargs.get("ts_code")
        if ts_code is None:
            return FakeFrame(list(records.values()))
        return FakeFrame([records[str(ts_code)]])

    def fina_indicator_vip(self, **kwargs) -> FakeFrame:
        period = kwargs.get("period")
        if period == "20260331":
            return FakeFrame([])
        if period == "20251231":
            return FakeFrame(
                [
                    {
                        "ts_code": "300750.SZ",
                        "ann_date": "20260327",
                        "end_date": "20251231",
                        "roe_dt": 23.4,
                        "grossprofit_margin": 24.8,
                        "debt_to_assets": 42.1,
                        "ocf_to_profit": 1.24,
                    }
                ]
            )
        assert period == "20250930"
        return FakeFrame(
            [
                {
                    "ts_code": "002475.SZ",
                    "ann_date": "20251105",
                    "end_date": "20250930",
                    "roe_dt": 14.2,
                    "grossprofit_margin": 12.1,
                    "debt_to_assets": 61.0,
                    "ocf_to_profit": 0.65,
                }
            ]
        )

    def income_vip(self, **kwargs) -> FakeFrame:
        period = kwargs.get("period")
        if period == "20251231":
            return FakeFrame(
                [
                    {
                        "ts_code": "300750.SZ",
                        "ann_date": "20260327",
                        "end_date": "20251231",
                        "total_revenue": 362_013_000_000.0,
                        "n_income_attr_p": 45_210_000_000.0,
                    }
                ]
            )
        assert period == "20250930"
        return FakeFrame(
            [
                {
                    "ts_code": "002475.SZ",
                    "ann_date": "20251105",
                    "end_date": "20250930",
                    "total_revenue": 248_330_000_000.0,
                    "n_income_attr_p": 12_500_000_000.0,
                },
            ]
        )

    def balancesheet_vip(self, **kwargs) -> FakeFrame:
        period = kwargs.get("period")
        if period == "20251231":
            return FakeFrame(
                [
                    {
                        "ts_code": "300750.SZ",
                        "ann_date": "20260327",
                        "end_date": "20251231",
                        "total_assets": 812_450_000_000.0,
                        "total_liab": 342_000_000_000.0,
                    },
                ]
            )
        assert period == "20250930"
        return FakeFrame(
            [
                {
                    "ts_code": "002475.SZ",
                    "ann_date": "20251105",
                    "end_date": "20250930",
                    "total_assets": 229_700_000_000.0,
                    "total_liab": 140_100_000_000.0,
                },
            ]
        )

    def cashflow_vip(self, **kwargs) -> FakeFrame:
        period = kwargs.get("period")
        if period == "20251231":
            return FakeFrame(
                [
                    {
                        "ts_code": "300750.SZ",
                        "ann_date": "20260327",
                        "end_date": "20251231",
                        "n_cashflow_act": 56_220_000_000.0,
                    },
                ]
            )
        assert period == "20250930"
        return FakeFrame(
            [
                {
                    "ts_code": "002475.SZ",
                    "ann_date": "20251105",
                    "end_date": "20250930",
                    "n_cashflow_act": 8_120_000_000.0,
                },
            ]
        )


def main() -> int:
    previous_env = {key: os.environ.get(key) for key in _env_keys()}
    previous_module = sys.modules.get("tushare")
    try:
        os.environ["QUANTA_SOURCE_PROVIDER"] = "tushare"
        os.environ["QUANTA_TUSHARE_TOKEN"] = "demo-token"
        os.environ["QUANTA_TUSHARE_EXCHANGE"] = "SSE"
        os.environ["QUANTA_SOURCE_SYMBOLS"] = "300750.SZ,002475.SZ"

        sys.modules["tushare"] = types.SimpleNamespace(
            pro_api=lambda token: _build_fake_client(token)
        )

        settings = load_settings()
        provider = build_market_data_provider(settings)

        latest_biz_date = provider.latest_available_biz_date()
        assert latest_biz_date == "2026-04-01"
        assert provider.list_open_biz_dates(
            start_biz_date="2026-03-31",
            end_biz_date="2026-04-01",
        ) == ["2026-03-31", "2026-04-01"]

        snapshot = provider.fetch_daily_snapshot()
        assert snapshot.provider == "tushare"
        assert snapshot.source == "tushare.pro"
        assert snapshot.biz_date == "2026-04-01"
        assert snapshot.price_basis == "raw"
        assert len(snapshot.stock_basic) == 2
        assert len(snapshot.daily_bars) == 2
        assert snapshot.trade_calendar["market_code"] == "CN-A"
        assert snapshot.market_overview["trade_date"] == "2026-04-01"
        assert snapshot.market_overview["breadth"]["advancers"] == 2
        assert snapshot.market_overview["breadth"]["decliners"] == 0
        assert len(snapshot.market_overview["indices"]) == 3
        assert snapshot.market_overview["indices"][0]["name"] == "上证指数"
        assert snapshot.market_overview["indices"][0]["close"] == 3348.72
        assert snapshot.market_overview["indices"][0]["change_pct"] == -0.38
        assert snapshot.market_overview["indices"][0]["commentary"] == "窄幅整理，情绪仍偏谨慎。"
        assert "north_money_million: 128.60" in snapshot.market_overview["highlights"]
        assert "market_index_coverage: 3/3" in snapshot.market_overview["highlights"]
        assert snapshot.source_watermark["moneyflow_count"] == 2
        assert snapshot.source_watermark["market_index_count"] == 3
        assert snapshot.source_watermark["market_index_symbols"] == [
            "000001.SH",
            "399001.SZ",
            "399006.SZ",
        ]
        assert snapshot.source_watermark["top_list_count"] == 1
        assert snapshot.source_watermark["north_money_million"] == 128.6
        assert snapshot.source_watermark["financial_report_period"] == "2025-12-31"
        assert snapshot.source_watermark["financial_report_periods"] == [
            "2025-12-31",
            "2025-09-30",
        ]
        assert snapshot.source_watermark["financial_report_period_by_symbol"] == {
            "002475.SZ": "2025-09-30",
            "300750.SZ": "2025-12-31",
        }
        assert snapshot.source_watermark["fina_indicator_count"] == 2
        assert snapshot.source_watermark["income_count"] == 2
        assert snapshot.source_watermark["balancesheet_count"] == 2
        assert snapshot.source_watermark["cashflow_count"] == 2
        assert (
            "financial_report_periods: 2025-12-31, 2025-09-30"
            in snapshot.market_overview["highlights"]
        )
        assert "financial_sidecar_coverage: 2/2" in snapshot.market_overview["highlights"]

        bar_by_symbol = {item["symbol"]: item for item in snapshot.daily_bars}
        assert bar_by_symbol["300750.SZ"]["volume"] == 18234567.0
        assert bar_by_symbol["300750.SZ"]["amount"] == 4912356000.0
        assert bar_by_symbol["300750.SZ"]["turnover_rate"] == 3.46
        assert bar_by_symbol["300750.SZ"]["high_limit"] == 286.11
        assert bar_by_symbol["002475.SZ"]["low_limit"] == 31.38

        stock_basic_by_symbol = {item["symbol"]: item for item in snapshot.stock_basic}
        assert stock_basic_by_symbol["300750.SZ"]["board"] == "创业板"
        assert stock_basic_by_symbol["300750.SZ"]["listed_at"] == "2018-06-11"
        assert stock_basic_by_symbol["002475.SZ"]["display_name"] == "立讯精密"

        capital_by_symbol = {
            item["symbol"]: item for item in snapshot.capital_feature_overrides
        }
        assert round(float(capital_by_symbol["300750.SZ"]["main_net_inflow"]), 1) == 96006000.0
        assert round(float(capital_by_symbol["300750.SZ"]["super_large_order_inflow"]), 1) == 42005000.0
        assert round(float(capital_by_symbol["300750.SZ"]["large_order_inflow"]), 1) == 61003000.0
        assert capital_by_symbol["300750.SZ"]["has_dragon_tiger"] is True
        assert capital_by_symbol["002475.SZ"]["has_dragon_tiger"] is False

        fundamental_by_symbol = {
            item["symbol"]: item for item in snapshot.fundamental_feature_overrides
        }
        assert fundamental_by_symbol["300750.SZ"]["report_period"] == "2025-12-31"
        assert fundamental_by_symbol["300750.SZ"]["ann_date"] == "2026-03-27"
        assert fundamental_by_symbol["300750.SZ"]["roe_dt"] == 23.4
        assert fundamental_by_symbol["300750.SZ"]["total_revenue"] == 362_013_000_000.0
        assert round(float(fundamental_by_symbol["300750.SZ"]["cash_to_profit"]), 4) == 1.2435
        assert round(float(fundamental_by_symbol["300750.SZ"]["fundamental_score"]), 2) == 75.08
        assert fundamental_by_symbol["002475.SZ"]["report_period"] == "2025-09-30"
        assert fundamental_by_symbol["002475.SZ"]["ann_date"] == "2025-11-05"
        assert round(float(fundamental_by_symbol["002475.SZ"]["fundamental_score"]), 2) == 37.34

        print("[tushare-provider-smoke] tushare provider mapping is healthy")
        return 0
    finally:
        if previous_module is None:
            sys.modules.pop("tushare", None)
        else:
            sys.modules["tushare"] = previous_module
        for key, value in previous_env.items():
            if value is None:
                os.environ.pop(key, None)
            else:
                os.environ[key] = value


def _build_fake_client(token: str) -> FakeTusharePro:
    if token != "demo-token":
        raise AssertionError(f"unexpected token: {token}")
    return FakeTusharePro()


def _env_keys() -> tuple[str, ...]:
    return (
        "QUANTA_SOURCE_PROVIDER",
        "QUANTA_TUSHARE_TOKEN",
        "QUANTA_TUSHARE_EXCHANGE",
        "QUANTA_SOURCE_SYMBOLS",
    )


if __name__ == "__main__":
    raise SystemExit(main())
