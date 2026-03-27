from __future__ import annotations

from backend.app.app_wiring.settings import AppSettings, load_settings
from backend.app.domains.analysis.bootstrap import ensure_analysis_artifacts
from backend.app.domains.backtest.bootstrap import ensure_backtest_artifacts
from backend.app.domains.market_data.bootstrap import ensure_dev_duckdb
from backend.app.domains.screener.bootstrap import ensure_screener_artifacts
from backend.app.domains.tasking.bootstrap import ensure_runtime_directories


def bootstrap_dev_runtime(
    settings: AppSettings | None = None,
) -> dict[str, dict[str, object] | dict[str, str]]:
    resolved_settings = settings or load_settings()

    return {
        "runtime": ensure_runtime_directories(resolved_settings),
        "market_data": ensure_dev_duckdb(resolved_settings),
        "analysis": ensure_analysis_artifacts(resolved_settings),
        "screener": ensure_screener_artifacts(resolved_settings),
        "backtest": ensure_backtest_artifacts(resolved_settings),
    }
