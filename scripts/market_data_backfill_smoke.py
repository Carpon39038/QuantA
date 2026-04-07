#!/usr/bin/env python3

from __future__ import annotations

import os
from pathlib import Path
import sys
import tempfile
import types

import duckdb


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))


from backend.app.app_wiring.settings import load_settings
from backend.app.domains.market_data.sync import backfill_market_data


OPEN_DATES = ("20260331", "20260401", "20260402")


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
        start_date = str(kwargs.get("start_date"))
        end_date = str(kwargs.get("end_date"))
        records = [
            {
                "exchange": "SSE",
                "cal_date": date_value,
                "is_open": "1",
                "pretrade_date": OPEN_DATES[max(index - 1, 0)],
            }
            for index, date_value in enumerate(OPEN_DATES)
            if start_date <= date_value <= end_date
        ]
        return FakeFrame(records)

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
            ]
        )

    def daily(self, **kwargs) -> FakeFrame:
        trade_date = str(kwargs.get("trade_date"))
        if trade_date not in OPEN_DATES:
            return FakeFrame([])
        day_offset = OPEN_DATES.index(trade_date)
        return FakeFrame(
            [
                {
                    "ts_code": "300750.SZ",
                    "trade_date": trade_date,
                    "open": 258.0 + day_offset,
                    "high": 263.0 + day_offset,
                    "low": 255.0 + day_offset,
                    "close": 261.0 + day_offset,
                    "pre_close": 257.5 + day_offset,
                    "vol": 170000.0 + day_offset * 5000.0,
                    "amount": 4800000.0 + day_offset * 100000.0,
                },
                {
                    "ts_code": "002475.SZ",
                    "trade_date": trade_date,
                    "open": 34.1 + day_offset * 0.2,
                    "high": 34.9 + day_offset * 0.2,
                    "low": 33.8 + day_offset * 0.2,
                    "close": 34.6 + day_offset * 0.2,
                    "pre_close": 34.0 + day_offset * 0.2,
                    "vol": 250000.0 + day_offset * 6000.0,
                    "amount": 870000.0 + day_offset * 15000.0,
                },
            ]
        )

    def daily_basic(self, **kwargs) -> FakeFrame:
        trade_date = str(kwargs.get("trade_date"))
        if trade_date not in OPEN_DATES:
            return FakeFrame([])
        day_offset = OPEN_DATES.index(trade_date)
        return FakeFrame(
            [
                {
                    "ts_code": "300750.SZ",
                    "trade_date": trade_date,
                    "turnover_rate": 3.0 + day_offset * 0.1,
                },
                {
                    "ts_code": "002475.SZ",
                    "trade_date": trade_date,
                    "turnover_rate": 1.6 + day_offset * 0.05,
                },
            ]
        )

    def stk_limit(self, **kwargs) -> FakeFrame:
        trade_date = str(kwargs.get("trade_date"))
        if trade_date not in OPEN_DATES:
            return FakeFrame([])
        day_offset = OPEN_DATES.index(trade_date)
        return FakeFrame(
            [
                {
                    "ts_code": "300750.SZ",
                    "trade_date": trade_date,
                    "up_limit": 282.0 + day_offset,
                    "down_limit": 231.0 + day_offset,
                },
                {
                    "ts_code": "002475.SZ",
                    "trade_date": trade_date,
                    "up_limit": 37.5 + day_offset * 0.2,
                    "down_limit": 30.7 + day_offset * 0.2,
                },
            ]
        )

    def moneyflow(self, **kwargs) -> FakeFrame:
        trade_date = str(kwargs.get("trade_date"))
        if trade_date not in OPEN_DATES:
            return FakeFrame([])
        day_offset = OPEN_DATES.index(trade_date)
        return FakeFrame(
            [
                {
                    "ts_code": "300750.SZ",
                    "trade_date": trade_date,
                    "buy_lg_amount": 8000.0 + day_offset * 100.0,
                    "sell_lg_amount": 2100.0,
                    "buy_elg_amount": 5200.0,
                    "sell_elg_amount": 900.0,
                    "net_mf_amount": 9500.0 + day_offset * 50.0,
                },
                {
                    "ts_code": "002475.SZ",
                    "trade_date": trade_date,
                    "buy_lg_amount": 2100.0,
                    "sell_lg_amount": 1700.0,
                    "buy_elg_amount": 1250.0,
                    "sell_elg_amount": 900.0,
                    "net_mf_amount": 420.0 + day_offset * 20.0,
                },
            ]
        )

    def top_list(self, **kwargs) -> FakeFrame:
        trade_date = str(kwargs.get("trade_date"))
        if trade_date == "20260402":
            return FakeFrame(
                [
                    {
                        "ts_code": "300750.SZ",
                        "trade_date": trade_date,
                        "name": "宁德时代",
                        "reason": "日涨幅偏离值达7%",
                    }
                ]
            )
        return FakeFrame([])

    def moneyflow_hsgt(self, **kwargs) -> FakeFrame:
        trade_date = str(kwargs.get("trade_date"))
        if trade_date not in OPEN_DATES:
            return FakeFrame([])
        day_offset = OPEN_DATES.index(trade_date)
        return FakeFrame(
            [
                {
                    "trade_date": trade_date,
                    "north_money": 100.0 + day_offset * 10.0,
                    "south_money": -20.0,
                    "hgt": 60.0,
                    "sgt": 40.0,
                }
            ]
        )

    def fina_indicator_vip(self, **kwargs) -> FakeFrame:
        period = str(kwargs.get("period"))
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
        if period == "20250930":
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
        return FakeFrame([])

    def income_vip(self, **kwargs) -> FakeFrame:
        period = str(kwargs.get("period"))
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
        if period == "20250930":
            return FakeFrame(
                [
                    {
                        "ts_code": "002475.SZ",
                        "ann_date": "20251105",
                        "end_date": "20250930",
                        "total_revenue": 248_330_000_000.0,
                        "n_income_attr_p": 12_500_000_000.0,
                    }
                ]
            )
        return FakeFrame([])

    def balancesheet_vip(self, **kwargs) -> FakeFrame:
        period = str(kwargs.get("period"))
        if period == "20251231":
            return FakeFrame(
                [
                    {
                        "ts_code": "300750.SZ",
                        "ann_date": "20260327",
                        "end_date": "20251231",
                        "total_assets": 812_450_000_000.0,
                        "total_liab": 342_000_000_000.0,
                    }
                ]
            )
        if period == "20250930":
            return FakeFrame(
                [
                    {
                        "ts_code": "002475.SZ",
                        "ann_date": "20251105",
                        "end_date": "20250930",
                        "total_assets": 229_700_000_000.0,
                        "total_liab": 140_100_000_000.0,
                    }
                ]
            )
        return FakeFrame([])

    def cashflow_vip(self, **kwargs) -> FakeFrame:
        period = str(kwargs.get("period"))
        if period == "20251231":
            return FakeFrame(
                [
                    {
                        "ts_code": "300750.SZ",
                        "ann_date": "20260327",
                        "end_date": "20251231",
                        "n_cashflow_act": 56_220_000_000.0,
                    }
                ]
            )
        if period == "20250930":
            return FakeFrame(
                [
                    {
                        "ts_code": "002475.SZ",
                        "ann_date": "20251105",
                        "end_date": "20250930",
                        "n_cashflow_act": 8_120_000_000.0,
                    }
                ]
            )
        return FakeFrame([])


def main() -> int:
    previous_env = {key: os.environ.get(key) for key in _env_keys()}
    previous_module = sys.modules.get("tushare")
    try:
        with tempfile.TemporaryDirectory(prefix="quanta-backfill-smoke-") as temp_dir:
            os.environ["QUANTA_RUNTIME_DATA_DIR"] = temp_dir
            os.environ["QUANTA_DUCKDB_PATH"] = str(Path(temp_dir) / "duckdb" / "quanta.duckdb")
            os.environ["QUANTA_SOURCE_PROVIDER"] = "tushare"
            os.environ["QUANTA_SOURCE_UNIVERSE"] = "core_research_12"
            os.environ["QUANTA_DISCLOSURE_PROVIDER"] = "none"
            os.environ["QUANTA_SOURCE_VALIDATION_PROVIDERS"] = "none"
            os.environ["QUANTA_TUSHARE_TOKEN"] = "demo-token"
            os.environ["QUANTA_TUSHARE_EXCHANGE"] = "SSE"
            os.environ["QUANTA_SOURCE_SYMBOLS"] = "300750.SZ,002475.SZ"

            sys.modules["tushare"] = types.SimpleNamespace(
                pro_api=lambda token: _build_fake_client(token)
            )

            settings = load_settings()
            summary = backfill_market_data(
                settings,
                start_biz_date="2026-03-31",
                end_biz_date="2026-04-02",
            )
            assert summary["open_biz_dates"] == [
                "2026-03-31",
                "2026-04-01",
                "2026-04-02",
            ]
            assert summary["synced_biz_dates"] == summary["open_biz_dates"]
            assert summary["skipped_existing_biz_dates"] == []
            assert summary["snapshot_count"] == 3

            rerun_summary = backfill_market_data(
                settings,
                start_biz_date="2026-03-31",
                end_biz_date="2026-04-02",
            )
            assert rerun_summary["snapshot_count"] == 0
            assert rerun_summary["synced_biz_dates"] == []
            assert rerun_summary["skipped_existing_biz_dates"] == summary["open_biz_dates"]

            connection = duckdb.connect(str(settings.duckdb_path), read_only=True)
            try:
                raw_snapshot_count = int(
                    connection.execute("SELECT COUNT(*) FROM raw_snapshot").fetchone()[0]
                )
                artifact_publish_count = int(
                    connection.execute("SELECT COUNT(*) FROM artifact_publish").fetchone()[0]
                )
                daily_bar_count = int(
                    connection.execute("SELECT COUNT(*) FROM daily_bar").fetchone()[0]
                )
                fundamental_feature_count = int(
                    connection.execute(
                        "SELECT COUNT(*) FROM fundamental_feature_daily"
                    ).fetchone()[0]
                )
            finally:
                connection.close()

            assert raw_snapshot_count == 5
            assert artifact_publish_count == 5
            assert daily_bar_count == 16
            assert fundamental_feature_count == 6

        print("[market-data-backfill-smoke] backfill path is healthy")
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
        "QUANTA_RUNTIME_DATA_DIR",
        "QUANTA_DUCKDB_PATH",
        "QUANTA_SOURCE_PROVIDER",
        "QUANTA_SOURCE_UNIVERSE",
        "QUANTA_DISCLOSURE_PROVIDER",
        "QUANTA_SOURCE_VALIDATION_PROVIDERS",
        "QUANTA_TUSHARE_TOKEN",
        "QUANTA_TUSHARE_EXCHANGE",
        "QUANTA_SOURCE_SYMBOLS",
    )


if __name__ == "__main__":
    raise SystemExit(main())
