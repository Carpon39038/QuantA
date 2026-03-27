from __future__ import annotations

from dataclasses import dataclass

from backend.app.app_wiring.settings import AppSettings, load_settings
from backend.app.domains.analysis.service import build_market_overview
from backend.app.domains.backtest.service import build_backtest_summary
from backend.app.domains.market_data.repo import load_latest_published_snapshot
from backend.app.domains.screener.service import build_screener_summary


@dataclass
class QuantAContainer:
    settings: AppSettings

    def latest_snapshot_payload(self) -> dict[str, object]:
        snapshot = load_latest_published_snapshot(self.settings)

        return {
            "api_contract_version": "0.1",
            "snapshot_id": snapshot["snapshot_id"],
            "raw_snapshot_id": snapshot["raw_snapshot_id"],
            "status": snapshot["status"],
            "generated_at": snapshot["generated_at"],
            "price_basis": snapshot["price_basis"],
            "market_overview": build_market_overview(snapshot),
            "screener": build_screener_summary(snapshot),
            "backtest": build_backtest_summary(snapshot),
            "task_status": snapshot["task_status"],
            "runtime": {
                "backend_origin": self.settings.backend_origin,
                "frontend_origin": self.settings.frontend_origin,
                "data_dir": str(self.settings.data_dir),
                "fixture_path": str(self.settings.fixture_path),
            },
        }


def build_container(settings: AppSettings | None = None) -> QuantAContainer:
    return QuantAContainer(settings=settings or load_settings())
