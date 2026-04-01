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
