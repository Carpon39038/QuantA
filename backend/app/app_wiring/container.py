from __future__ import annotations

from dataclasses import dataclass

from backend.app.app_wiring.settings import AppSettings, load_settings
from backend.app.domains.analysis.service import build_market_overview
from backend.app.domains.backtest.service import build_backtest_summary
from backend.app.domains.market_data.repo import (
    load_backtest_run,
    load_latest_published_snapshot,
    load_screener_run,
    load_stock_capital_flow,
    load_stock_fundamentals,
    load_stock_indicators,
    load_stock_kline_asof,
    load_stock_snapshot,
    load_system_health,
    load_task_runs,
)
from backend.app.shared.telemetry.alerts import load_recent_alerts
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
                "duckdb_path": str(self.settings.duckdb_path),
                "seed_fixture_path": str(self.settings.fixture_path),
                "alerts_path": str(self.settings.alerts_path),
                "source_provider": self.settings.source_provider,
            },
        }

    def stock_snapshot_payload(
        self,
        *,
        symbol: str,
        snapshot_id: str | None = None,
        raw_snapshot_id: str | None = None,
        price_basis: str | None = None,
    ) -> dict[str, object]:
        payload = load_stock_snapshot(
            self.settings,
            symbol=symbol,
            snapshot_id=snapshot_id,
            raw_snapshot_id=raw_snapshot_id,
            price_basis=price_basis,
        )
        return {
            "api_contract_version": "0.1",
            **payload,
        }

    def stock_kline_payload(
        self,
        *,
        symbol: str,
        dataset: str,
        snapshot_id: str | None = None,
        raw_snapshot_id: str | None = None,
        price_basis: str | None = None,
        date_from: str | None = None,
        date_to: str | None = None,
    ) -> dict[str, object]:
        payload = load_stock_kline_asof(
            self.settings,
            symbol=symbol,
            dataset=dataset,
            snapshot_id=snapshot_id,
            raw_snapshot_id=raw_snapshot_id,
            price_basis=price_basis,
            date_from=date_from,
            date_to=date_to,
        )
        return {
            "api_contract_version": "0.1",
            **payload,
        }

    def stock_indicators_payload(
        self,
        *,
        symbol: str,
        snapshot_id: str | None = None,
        price_basis: str | None = None,
        date_from: str | None = None,
        date_to: str | None = None,
    ) -> dict[str, object]:
        payload = load_stock_indicators(
            self.settings,
            symbol=symbol,
            snapshot_id=snapshot_id,
            price_basis=price_basis,
            date_from=date_from,
            date_to=date_to,
        )
        return {
            "api_contract_version": "0.1",
            **payload,
        }

    def stock_capital_flow_payload(
        self,
        *,
        symbol: str,
        snapshot_id: str | None = None,
        date_from: str | None = None,
        date_to: str | None = None,
    ) -> dict[str, object]:
        payload = load_stock_capital_flow(
            self.settings,
            symbol=symbol,
            snapshot_id=snapshot_id,
            date_from=date_from,
            date_to=date_to,
        )
        return {
            "api_contract_version": "0.1",
            **payload,
        }

    def stock_fundamentals_payload(
        self,
        *,
        symbol: str,
        snapshot_id: str | None = None,
        date_from: str | None = None,
        date_to: str | None = None,
    ) -> dict[str, object]:
        payload = load_stock_fundamentals(
            self.settings,
            symbol=symbol,
            snapshot_id=snapshot_id,
            date_from=date_from,
            date_to=date_to,
        )
        return {
            "api_contract_version": "0.1",
            **payload,
        }

    def screener_run_payload(
        self,
        *,
        run_id: str | None = None,
        snapshot_id: str | None = None,
    ) -> dict[str, object]:
        payload = load_screener_run(
            self.settings,
            run_id=run_id,
            snapshot_id=snapshot_id,
        )
        return {
            "api_contract_version": "0.1",
            **payload,
        }

    def backtest_run_payload(
        self,
        *,
        backtest_id: str | None = None,
        snapshot_id: str | None = None,
    ) -> dict[str, object]:
        payload = load_backtest_run(
            self.settings,
            backtest_id=backtest_id,
            snapshot_id=snapshot_id,
        )
        return {
            "api_contract_version": "0.1",
            **payload,
        }

    def task_runs_payload(
        self,
        *,
        snapshot_id: str | None = None,
    ) -> dict[str, object]:
        payload = load_task_runs(
            self.settings,
            snapshot_id=snapshot_id,
        )
        return {
            "api_contract_version": "0.1",
            **payload,
        }

    def system_health_payload(self) -> dict[str, object]:
        payload = load_system_health(self.settings)
        return {
            "api_contract_version": "0.1",
            **payload,
            "backend_origin": self.settings.backend_origin,
            "frontend_origin": self.settings.frontend_origin,
        }

    def recent_alerts_payload(self, *, limit: int = 20) -> dict[str, object]:
        return {
            "api_contract_version": "0.1",
            "items": load_recent_alerts(self.settings, limit=limit),
            "alerts_path": str(self.settings.alerts_path),
        }


def build_container(settings: AppSettings | None = None) -> QuantAContainer:
    return QuantAContainer(settings=settings or load_settings())
