from __future__ import annotations

from copy import deepcopy

from backend.app.app_wiring.settings import AppSettings
from backend.app.shared.providers.local_fixture import load_json_fixture


def load_latest_published_snapshot(settings: AppSettings) -> dict[str, object]:
    snapshot = deepcopy(load_json_fixture(settings.fixture_path))
    snapshot.setdefault("market_overview", {})
    snapshot.setdefault("screener", {})
    snapshot.setdefault("backtest", {})
    snapshot.setdefault("task_status", {})
    return snapshot
