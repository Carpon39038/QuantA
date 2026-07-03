#!/usr/bin/env python3

from __future__ import annotations

import argparse
from datetime import datetime, timedelta, timezone
import json
import os
from pathlib import Path
import sys


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))


from backend.app.app_wiring.settings import load_settings
from backend.app.domains.market_data.repo import load_system_health
from backend.app.domains.market_data.sync import latest_source_biz_date
from backend.app.shared.telemetry.alerts import load_recent_alerts


CN_TZ = timezone(timedelta(hours=8))
DEFAULT_ALERT_HARD_GATE_WINDOW_HOURS = 24.0
DEFAULT_ALERT_LIMIT = 200
TRADING_SIGNAL_ALERT_TYPES = {
    "intraday_buy_point_triggered",
    "intraday_risk_warning",
    "intraday_stop_loss_triggered",
    "intraday_take_profit_triggered",
    "strategy_watchlist_signal",
}


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
        help="Return a non-zero exit code if any unconfirmed operational error alert is present.",
    )
    parser.add_argument(
        "--alert-window-hours",
        type=float,
        default=None,
        help=(
            "Only hard-gate operational error alerts from this rolling window. "
            "Defaults to QUANTA_ALERT_HARD_GATE_WINDOW_HOURS or 24; set 0 to disable."
        ),
    )
    parser.add_argument(
        "--alert-acknowledged-before",
        default=None,
        help=(
            "ISO timestamp; operational error alerts at or before it are treated as "
            "acknowledged history. Defaults to QUANTA_ALERT_ACKNOWLEDGED_BEFORE."
        ),
    )
    parser.add_argument(
        "--alert-limit",
        type=int,
        default=None,
        help="How many latest alerts to inspect. Defaults to QUANTA_ALERT_LIMIT or 200.",
    )
    args = parser.parse_args()

    summary = build_summary(
        live_source=args.live_source,
        fail_on_alert=args.fail_on_alert,
        alert_window_hours=args.alert_window_hours,
        alert_acknowledged_before=args.alert_acknowledged_before,
        alert_limit=args.alert_limit,
    )
    print(json.dumps(summary, ensure_ascii=False, indent=2))
    return exit_code_for_summary(summary)


def build_summary(
    *,
    live_source: bool = False,
    fail_on_alert: bool = False,
    alert_window_hours: float | None = None,
    alert_acknowledged_before: str | None = None,
    alert_limit: int | None = None,
) -> dict[str, object]:
    settings = load_settings()
    health = load_system_health(settings)
    resolved_alert_limit = _resolve_alert_limit(alert_limit)
    resolved_alert_window_hours = _resolve_alert_window_hours(alert_window_hours)
    resolved_alert_acknowledged_before = _resolve_alert_acknowledged_before(
        alert_acknowledged_before,
    )
    alerts = load_recent_alerts(settings, limit=resolved_alert_limit)
    queue_files = _queue_file_summary(settings.queue_dir)
    source_latest_biz_date = latest_source_biz_date(settings) if live_source else None
    now = datetime.now(timezone.utc)
    findings = _build_findings(
        health=health,
        alerts=alerts,
        queue_files=queue_files,
        source_latest_biz_date=source_latest_biz_date,
        fail_on_alert=fail_on_alert,
        alert_window_hours=resolved_alert_window_hours,
        alert_acknowledged_before=resolved_alert_acknowledged_before,
        now=now,
    )
    alert_hygiene = _build_alert_hygiene(
        alerts,
        alert_window_hours=resolved_alert_window_hours,
        alert_acknowledged_before=resolved_alert_acknowledged_before,
        now=now,
    )
    status = _overall_status(findings)
    return {
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
        "alert_hygiene": alert_hygiene,
        "queue_files": queue_files,
        "findings": findings,
    }


def exit_code_for_summary(summary: dict[str, object]) -> int:
    status = str(summary.get("status"))
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
    alert_window_hours: float | None,
    alert_acknowledged_before: str | None,
    now: datetime,
) -> list[dict[str, object]]:
    findings: list[dict[str, object]] = []
    _add_finding(
        findings,
        name="system_health",
        severity="pass" if health.get("status") == "ok" else "fail",
        message=f"system health status is {health.get('status')}",
    )

    alert_hygiene = _build_alert_hygiene(
        alerts,
        alert_window_hours=alert_window_hours,
        alert_acknowledged_before=alert_acknowledged_before,
        now=now,
    )
    unconfirmed_ops_errors = int(
        alert_hygiene["counts"]["unconfirmed_operational_error_alerts"]
    )
    total_error_alerts = int(alert_hygiene["counts"]["error_alerts"])
    _add_finding(
        findings,
        name="recent_error_alerts",
        severity=(
            "fail"
            if unconfirmed_ops_errors and fail_on_alert
            else ("warn" if unconfirmed_ops_errors else "pass")
        ),
        message=(
            "unconfirmed operational error alerts: "
            f"{unconfirmed_ops_errors}; total error alerts inspected: "
            f"{total_error_alerts}"
        ),
        detail=alert_hygiene,
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
    detail: dict[str, object] | None = None,
) -> None:
    finding = {
        "name": name,
        "severity": severity,
        "message": message,
    }
    if detail is not None:
        finding["detail"] = detail
    findings.append(finding)


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


def _build_alert_hygiene(
    alerts: list[dict[str, object]],
    *,
    alert_window_hours: float | None,
    alert_acknowledged_before: str | None,
    now: datetime,
) -> dict[str, object]:
    now_utc = _normalize_datetime(now)
    window_start = (
        now_utc - timedelta(hours=alert_window_hours)
        if alert_window_hours is not None and alert_window_hours > 0
        else None
    )
    acknowledged_before = _parse_alert_timestamp(alert_acknowledged_before)
    counts = {
        "loaded_alerts": len(alerts),
        "error_alerts": 0,
        "trading_signal_error_alerts": 0,
        "operational_error_alerts": 0,
        "outside_window_operational_error_alerts": 0,
        "acknowledged_operational_error_alerts": 0,
        "unconfirmed_operational_error_alerts": 0,
    }
    unconfirmed_samples: list[dict[str, object]] = []

    for alert in alerts:
        if _alert_severity(alert) != "ERROR":
            continue
        counts["error_alerts"] += 1

        if _alert_is_trading_signal(alert):
            counts["trading_signal_error_alerts"] += 1
            continue

        counts["operational_error_alerts"] += 1
        triggered_at = _parse_alert_timestamp(alert.get("triggered_at"))
        if (
            window_start is not None
            and triggered_at is not None
            and triggered_at < window_start
        ):
            counts["outside_window_operational_error_alerts"] += 1
            continue
        if (
            acknowledged_before is not None
            and triggered_at is not None
            and triggered_at <= acknowledged_before
        ):
            counts["acknowledged_operational_error_alerts"] += 1
            continue

        counts["unconfirmed_operational_error_alerts"] += 1
        if len(unconfirmed_samples) < 5:
            unconfirmed_samples.append(_alert_sample(alert))

    return {
        "alert_window_hours": alert_window_hours,
        "window_start": window_start.isoformat() if window_start is not None else None,
        "acknowledged_before": (
            acknowledged_before.isoformat() if acknowledged_before is not None else None
        ),
        "counts": counts,
        "unconfirmed_operational_error_samples": unconfirmed_samples,
    }


def _alert_is_trading_signal(alert: dict[str, object]) -> bool:
    return str(alert.get("alert_type") or "") in TRADING_SIGNAL_ALERT_TYPES


def _alert_severity(alert: dict[str, object]) -> str:
    raw = str(alert.get("severity") or "unknown").strip().upper()
    return "WARNING" if raw == "WARN" else raw


def _alert_sample(alert: dict[str, object]) -> dict[str, object]:
    return {
        "triggered_at": alert.get("triggered_at"),
        "alert_type": alert.get("alert_type"),
        "severity": alert.get("severity"),
        "message": alert.get("message"),
    }


def _parse_alert_timestamp(value: object) -> datetime | None:
    if value is None:
        return None
    raw_value = str(value).strip()
    if not raw_value:
        return None
    try:
        parsed = datetime.fromisoformat(raw_value.replace("Z", "+00:00"))
    except ValueError:
        return None
    return _normalize_datetime(parsed)


def _normalize_datetime(value: datetime) -> datetime:
    if value.tzinfo is None:
        value = value.replace(tzinfo=CN_TZ)
    return value.astimezone(timezone.utc)


def _resolve_alert_window_hours(raw_value: float | None) -> float | None:
    if raw_value is not None:
        return raw_value if raw_value > 0 else None
    env_value = os.environ.get("QUANTA_ALERT_HARD_GATE_WINDOW_HOURS")
    if env_value is None or not env_value.strip():
        return DEFAULT_ALERT_HARD_GATE_WINDOW_HOURS
    parsed = float(env_value)
    return parsed if parsed > 0 else None


def _resolve_alert_acknowledged_before(raw_value: str | None) -> str | None:
    if raw_value is not None:
        return raw_value
    env_value = os.environ.get("QUANTA_ALERT_ACKNOWLEDGED_BEFORE")
    return env_value.strip() if env_value and env_value.strip() else None


def _resolve_alert_limit(raw_value: int | None) -> int:
    if raw_value is not None:
        return max(1, raw_value)
    env_value = os.environ.get("QUANTA_ALERT_LIMIT")
    if env_value is None or not env_value.strip():
        return DEFAULT_ALERT_LIMIT
    return max(1, int(env_value))


if __name__ == "__main__":
    raise SystemExit(main())
