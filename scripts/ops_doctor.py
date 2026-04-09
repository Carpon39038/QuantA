#!/usr/bin/env python3

from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))


from backend.app.app_wiring.settings import load_settings
from backend.app.domains.market_data.repo import load_system_health
from backend.app.domains.market_data.sync import latest_source_biz_date
from backend.app.shared.telemetry.alerts import load_recent_alerts


def main() -> int:
    parser = argparse.ArgumentParser(description="Run a small QuantA ops health diagnosis.")
    parser.add_argument(
        "--live-source",
        action="store_true",
        help="Call the configured source provider and compare latest READY biz_date to the source latest biz_date.",
    )
    parser.add_argument(
        "--fail-on-alert",
        action="store_true",
        help="Return a non-zero exit code if any recent error-level alert is present.",
    )
    args = parser.parse_args()

    settings = load_settings()
    health = load_system_health(settings)
    alerts = load_recent_alerts(settings, limit=50)
    queue_files = _queue_file_summary(settings.queue_dir)
    source_latest_biz_date = latest_source_biz_date(settings) if args.live_source else None
    findings = _build_findings(
        health=health,
        alerts=alerts,
        queue_files=queue_files,
        source_latest_biz_date=source_latest_biz_date,
        fail_on_alert=args.fail_on_alert,
    )
    status = _overall_status(findings)
    summary = {
        "status": status,
        "duckdb_path": str(settings.duckdb_path),
        "alerts_path": str(settings.alerts_path),
        "source_provider": settings.source_provider,
        "source_universe": settings.source_universe,
        "source_latest_biz_date": source_latest_biz_date,
        "snapshot_id": health.get("snapshot_id"),
        "snapshot_biz_date": _snapshot_biz_date(health),
        "history_coverage": health.get("history_coverage"),
        "alert_count": health.get("alert_count"),
        "queue_files": queue_files,
        "findings": findings,
    }
    print(json.dumps(summary, ensure_ascii=False, indent=2))
    return 0 if status in {"pass", "warn"} else 1


def _queue_file_summary(queue_dir: Path) -> dict[str, int]:
    summary = {}
    for queue_name in ("service", "backtest"):
        for state in ("pending", "processing", "completed", "failed"):
            state_dir = queue_dir / queue_name / state
            summary[f"{queue_name}_{state}"] = (
                len(list(state_dir.glob("*.json"))) if state_dir.exists() else 0
            )
    return summary


def _build_findings(
    *,
    health: dict[str, object],
    alerts: list[dict[str, object]],
    queue_files: dict[str, int],
    source_latest_biz_date: str | None,
    fail_on_alert: bool,
) -> list[dict[str, object]]:
    findings: list[dict[str, object]] = []
    _add_finding(
        findings,
        name="system_health",
        severity="pass" if health.get("status") == "ok" else "fail",
        message=f"system health status is {health.get('status')}",
    )

    error_alerts = [alert for alert in alerts if alert.get("severity") == "error"]
    _add_finding(
        findings,
        name="recent_error_alerts",
        severity="fail" if error_alerts and fail_on_alert else ("warn" if error_alerts else "pass"),
        message=f"recent error alerts: {len(error_alerts)}",
    )

    open_queue_count = sum(
        queue_files[key]
        for key in (
            "service_pending",
            "service_processing",
            "backtest_pending",
            "backtest_processing",
        )
    )
    _add_finding(
        findings,
        name="open_queue",
        severity="warn" if open_queue_count else "pass",
        message=f"open queue files: {open_queue_count}",
    )

    snapshot_biz_date = _snapshot_biz_date(health)
    if source_latest_biz_date is not None:
        if snapshot_biz_date is None:
            source_freshness_status = "fail"
            source_freshness_message = "latest READY snapshot has no biz_date"
        elif source_latest_biz_date > snapshot_biz_date:
            source_freshness_status = "warn"
            source_freshness_message = (
                f"source latest {source_latest_biz_date} is newer than snapshot {snapshot_biz_date}"
            )
        else:
            source_freshness_status = "pass"
            source_freshness_message = (
                f"snapshot {snapshot_biz_date} is caught up to source {source_latest_biz_date}"
            )
        _add_finding(
            findings,
            name="source_freshness",
            severity=source_freshness_status,
            message=source_freshness_message,
        )

    coverage = health.get("history_coverage")
    coverage_count = (
        int(coverage.get("open_day_count", 0))
        if isinstance(coverage, dict)
        else 0
    )
    _add_finding(
        findings,
        name="history_coverage",
        severity="pass" if coverage_count > 0 else "warn",
        message=f"price history open days in latest snapshot: {coverage_count}",
    )
    return findings


def _add_finding(
    findings: list[dict[str, object]],
    *,
    name: str,
    severity: str,
    message: str,
) -> None:
    findings.append(
        {
            "name": name,
            "severity": severity,
            "message": message,
        }
    )


def _snapshot_biz_date(health: dict[str, object]) -> str | None:
    coverage = health.get("history_coverage")
    if not isinstance(coverage, dict):
        return None
    end_biz_date = coverage.get("end_biz_date")
    return str(end_biz_date) if end_biz_date is not None else None


def _overall_status(findings: list[dict[str, object]]) -> str:
    severities = {str(item.get("severity")) for item in findings}
    if "fail" in severities:
        return "fail"
    if "warn" in severities:
        return "warn"
    return "pass"


if __name__ == "__main__":
    raise SystemExit(main())
