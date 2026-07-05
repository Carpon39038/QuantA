from __future__ import annotations

from dataclasses import replace
from pathlib import Path

from backend.app.app_wiring.settings import AppSettings, load_settings
from backend.app.domains.market_data.sync import backfill_market_data, load_latest_building_snapshot
from backend.app.domains.tasking import scheduler


def test_fixture_latest_backfill_builds_latest_artifact_then_skips_rerun(
    tmp_path: Path,
    monkeypatch,
) -> None:
    settings = _isolated_settings(tmp_path, monkeypatch)

    summary = backfill_market_data(
        settings,
        start_biz_date="2026-03-31",
        end_biz_date="2026-03-31",
        artifact_mode="latest",
    )

    assert summary["provider"] == "fixture_json"
    assert summary["artifact_mode"] == "latest"
    assert summary["synced_biz_dates"] == ["2026-03-31"]
    assert summary["source_only_biz_dates"] == []
    assert summary["artifact_biz_dates"] == ["2026-03-31"]
    assert summary["raw_snapshot_count"] == 1
    assert summary["artifact_snapshot_count"] == 1

    building_snapshot = load_latest_building_snapshot(settings)
    assert building_snapshot is not None
    assert building_snapshot["biz_date"] == "2026-03-31"
    assert building_snapshot["snapshot_id"] == summary["snapshots"][0]["snapshot_id"]

    rerun_summary = backfill_market_data(
        settings,
        start_biz_date="2026-03-31",
        end_biz_date="2026-03-31",
        artifact_mode="latest",
    )

    assert rerun_summary["synced_biz_dates"] == []
    assert rerun_summary["artifact_snapshot_count"] == 0
    assert rerun_summary["skipped_existing_biz_dates"] == ["2026-03-31"]


def test_scheduler_auto_target_uses_recommendation_and_falls_back(
    tmp_path: Path,
    monkeypatch,
) -> None:
    settings = replace(
        _isolated_settings(tmp_path, monkeypatch),
        history_backfill_target_open_days=7,
        history_backfill_target_start_biz_date="auto",
    )
    latest_ready_snapshot = {
        "snapshot_id": "snapshot_2026-03-27_ready_001",
        "biz_date": "2026-03-27",
        "raw_snapshot_id": "raw_snapshot_2026-03-27_close_001",
    }

    monkeypatch.setattr(
        scheduler,
        "load_system_health",
        lambda _settings: {
            "history_coverage": {
                "recommended_target_start_biz_date": "2026-03-20",
            },
        },
    )
    resolved_target = scheduler._resolve_history_backfill_target_start_biz_date(
        settings,
        latest_ready_snapshot=latest_ready_snapshot,
    )
    assert resolved_target == "2026-03-20"
    assert scheduler._history_backfill_target_open_days(
        settings,
        resolved_target_start_biz_date=resolved_target,
    ) is None

    monkeypatch.setattr(
        scheduler,
        "load_system_health",
        lambda _settings: {
            "history_coverage": {
                "recommended_target_start_biz_date": None,
            },
        },
    )
    fallback_target = scheduler._resolve_history_backfill_target_start_biz_date(
        settings,
        latest_ready_snapshot=latest_ready_snapshot,
    )
    assert fallback_target is None
    assert scheduler._history_backfill_target_open_days(
        settings,
        resolved_target_start_biz_date=fallback_target,
    ) == 7


def _isolated_settings(tmp_path: Path, monkeypatch) -> AppSettings:
    runtime_dir = tmp_path / "runtime"
    monkeypatch.setenv("QUANTA_RUNTIME_DATA_DIR", str(runtime_dir))
    monkeypatch.setenv("QUANTA_DUCKDB_PATH", str(runtime_dir / "duckdb" / "quanta.duckdb"))
    monkeypatch.setenv("QUANTA_SOURCE_PROVIDER", "fixture_json")
    monkeypatch.setenv("QUANTA_SOURCE_VALIDATION_PROVIDERS", "none")
    return load_settings()
