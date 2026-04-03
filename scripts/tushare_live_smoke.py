#!/usr/bin/env python3

from __future__ import annotations

import json
from pathlib import Path
import sys


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))


from backend.app.app_wiring.settings import load_settings
from backend.app.shared.providers.market_data_source import (
    TushareRequestError,
    build_market_data_provider,
)


def main() -> int:
    settings = load_settings()
    if settings.source_provider != "tushare":
        raise ValueError(
            "tushare_live_smoke requires QUANTA_SOURCE_PROVIDER=tushare"
        )
    if not settings.tushare_token:
        raise ValueError(
            "tushare_live_smoke requires QUANTA_TUSHARE_TOKEN to be configured"
        )

    provider = build_market_data_provider(settings)
    try:
        latest_biz_date = provider.latest_available_biz_date()
        snapshot = provider.fetch_daily_snapshot()
    except TushareRequestError as exc:
        print(
            json.dumps(
                {
                    "ok": False,
                    "dataset": exc.dataset_name,
                    "category": exc.category,
                    "message": exc.message,
                },
                ensure_ascii=False,
                indent=2,
            )
        )
        raise SystemExit(2) from exc

    if snapshot.provider != "tushare":
        raise AssertionError(f"unexpected provider: {snapshot.provider}")
    if not snapshot.daily_bars:
        raise AssertionError("tushare live snapshot returned no daily bars")
    if snapshot.biz_date > latest_biz_date:
        raise AssertionError(
            f"snapshot biz_date {snapshot.biz_date} is after latest available {latest_biz_date}"
        )
    tracked_symbols = [item["symbol"] for item in snapshot.stock_basic]
    covered_financial_symbols = sorted(
        item["symbol"] for item in snapshot.fundamental_feature_overrides
    )
    missing_financial_symbols = [
        symbol for symbol in tracked_symbols if symbol not in covered_financial_symbols
    ]

    summary = {
        "ok": True,
        "provider": snapshot.provider,
        "source": snapshot.source,
        "latest_biz_date": latest_biz_date,
        "snapshot_biz_date": snapshot.biz_date,
        "tracked_symbols": tracked_symbols,
        "daily_bar_count": len(snapshot.daily_bars),
        "capital_feature_override_count": len(snapshot.capital_feature_overrides),
        "fundamental_feature_override_count": len(snapshot.fundamental_feature_overrides),
        "covered_financial_symbols": covered_financial_symbols,
        "missing_financial_symbols": missing_financial_symbols,
        "vip_financials_ready": bool(covered_financial_symbols)
        and not missing_financial_symbols,
        "source_watermark": snapshot.source_watermark,
        "market_highlights": snapshot.market_overview.get("highlights", []),
    }

    print(json.dumps(summary, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
