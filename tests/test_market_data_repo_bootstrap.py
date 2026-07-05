from __future__ import annotations

from pathlib import Path

from backend.app.app_wiring.settings import AppSettings, load_settings
from backend.app.domains.analysis.bootstrap import ensure_analysis_artifacts
from backend.app.domains.backtest.bootstrap import ensure_backtest_artifacts
from backend.app.domains.market_data.bootstrap import ensure_dev_duckdb
from backend.app.domains.market_data.repo import (
    load_latest_published_snapshot,
    load_stock_kline_asof,
    load_stock_snapshot,
    load_system_health,
)
from backend.app.domains.screener.bootstrap import ensure_screener_artifacts


def test_dev_duckdb_bootstrap_exposes_snapshot_and_asof_reads(
    tmp_path: Path,
    monkeypatch,
) -> None:
    settings = _isolated_settings(tmp_path, monkeypatch)

    summary = ensure_dev_duckdb(settings)

    assert settings.duckdb_path.exists()
    assert summary["table_counts"]["raw_snapshot"] >= 2
    assert summary["table_counts"]["artifact_publish"] >= 2
    ensure_analysis_artifacts(settings)
    ensure_screener_artifacts(settings)
    ensure_backtest_artifacts(settings)

    snapshot = load_latest_published_snapshot(settings)
    assert snapshot["snapshot_id"] == "snapshot_2026-03-27_ready_001"
    assert snapshot["status"] == "READY"
    assert snapshot["market_overview"]["trade_date"] == "2026-03-27"
    assert snapshot["screener"]["top_candidates"][0]["symbol"] == "300750.SZ"

    stock = load_stock_snapshot(settings, symbol="300750.SZ")
    assert stock["display_name"] == "宁德时代"
    assert stock["available_series"]["daily_bar"]["row_count"] == 3
    assert stock["available_series"]["price_series"]["row_count"] == 3
    assert stock["latest_daily_bar"]["effective_raw_snapshot_id"] == (
        "raw_snapshot_2026-03-27_close_001"
    )
    assert stock["latest_price_bar"]["effective_snapshot_id"] == (
        "snapshot_2026-03-27_ready_001"
    )

    previous_raw_kline = load_stock_kline_asof(
        settings,
        symbol="300750.SZ",
        dataset="daily_bar",
        raw_snapshot_id="raw_snapshot_2026-03-26_close_001",
    )
    latest_raw_kline = load_stock_kline_asof(
        settings,
        symbol="300750.SZ",
        dataset="daily_bar",
        raw_snapshot_id="raw_snapshot_2026-03-27_close_001",
    )
    assert previous_raw_kline["range"]["row_count"] == 2
    assert latest_raw_kline["range"]["row_count"] == 3
    assert previous_raw_kline["items"][-1]["trade_date"] == "2026-03-26"
    assert latest_raw_kline["items"][-1]["trade_date"] == "2026-03-27"

    price_kline = load_stock_kline_asof(
        settings,
        symbol="300750.SZ",
        dataset="price_series",
    )
    assert price_kline["range"]["row_count"] == 3
    assert price_kline["items"][-1]["effective_snapshot_id"] == (
        "snapshot_2026-03-27_ready_001"
    )

    health = load_system_health(settings)
    assert health["snapshot_id"] == snapshot["snapshot_id"]
    assert health["history_coverage"]["open_day_count"] == 2
    assert health["history_coverage"]["start_biz_date"] == "2026-03-26"
    assert health["history_coverage"]["end_biz_date"] == "2026-03-27"


def _isolated_settings(tmp_path: Path, monkeypatch) -> AppSettings:
    runtime_dir = tmp_path / "runtime"
    monkeypatch.setenv("QUANTA_RUNTIME_DATA_DIR", str(runtime_dir))
    monkeypatch.setenv("QUANTA_DUCKDB_PATH", str(runtime_dir / "duckdb" / "quanta.duckdb"))
    monkeypatch.setenv("QUANTA_SOURCE_PROVIDER", "fixture_json")
    monkeypatch.setenv("QUANTA_SOURCE_VALIDATION_PROVIDERS", "none")
    return load_settings()
