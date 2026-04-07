from __future__ import annotations

from datetime import datetime, timedelta, timezone
import json

from backend.app.app_wiring.settings import AppSettings


CN_TZ = timezone(timedelta(hours=8))


def emit_alert(
    settings: AppSettings,
    *,
    alert_type: str,
    severity: str,
    message: str,
    detail: dict[str, object],
) -> None:
    settings.logs_dir.mkdir(parents=True, exist_ok=True)
    record = {
        "triggered_at": datetime.now(CN_TZ).isoformat(timespec="seconds"),
        "alert_type": alert_type,
        "severity": severity,
        "message": message,
        "detail": detail,
    }
    settings.alerts_path.parent.mkdir(parents=True, exist_ok=True)
    with settings.alerts_path.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(record, ensure_ascii=False) + "\n")


def load_recent_alerts(
    settings: AppSettings,
    *,
    limit: int = 20,
) -> list[dict[str, object]]:
    if not settings.alerts_path.exists():
        return []

    lines = settings.alerts_path.read_text(encoding="utf-8").splitlines()
    alerts: list[dict[str, object]] = []
    for line in lines[-limit:]:
        if not line.strip():
            continue
        alerts.append(json.loads(line))
    return alerts


def summarize_recent_alerts(
    settings: AppSettings,
    *,
    limit: int = 200,
) -> dict[str, object]:
    alerts = load_recent_alerts(settings, limit=limit)
    severity_counts: dict[str, int] = {}
    alert_type_counts: dict[str, int] = {}
    provider_counts: dict[str, dict[str, object]] = {}

    for alert in alerts:
        severity = str(alert.get("severity") or "unknown")
        alert_type = str(alert.get("alert_type") or "unknown")
        severity_counts[severity] = severity_counts.get(severity, 0) + 1
        alert_type_counts[alert_type] = alert_type_counts.get(alert_type, 0) + 1

        detail = alert.get("detail")
        if not isinstance(detail, dict):
            continue
        provider = detail.get("provider")
        if provider is None:
            continue
        provider_name = str(provider)
        provider_summary = provider_counts.setdefault(
            provider_name,
            {
                "provider": provider_name,
                "alert_count": 0,
                "latest_triggered_at": None,
                "latest_status": None,
                "latest_category": None,
                "latest_message": None,
            },
        )
        provider_summary["alert_count"] = int(provider_summary["alert_count"]) + 1
        provider_summary["latest_triggered_at"] = alert.get("triggered_at")
        provider_summary["latest_status"] = detail.get("status")
        provider_summary["latest_category"] = detail.get("degradation_category")
        provider_summary["latest_message"] = alert.get("message")

    return {
        "window_count": len(alerts),
        "severity_counts": severity_counts,
        "alert_type_counts": dict(
            sorted(
                alert_type_counts.items(),
                key=lambda item: (-item[1], item[0]),
            )
        ),
        "latest_alert": alerts[-1] if alerts else None,
        "provider_alerts": sorted(
            provider_counts.values(),
            key=lambda item: (
                -int(item["alert_count"]),
                str(item["provider"]),
            ),
        )[:5],
    }
