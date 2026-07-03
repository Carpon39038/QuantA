from __future__ import annotations

from datetime import datetime, timedelta, timezone
import hashlib
import json
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

from backend.app.app_wiring.settings import AppSettings


CN_TZ = timezone(timedelta(hours=8))
PROVIDER_DEGRADATION_ALERT_TYPES = {
    "intraday_preview_provider_degraded",
    "shadow_validation_provider_degraded",
}
SEVERITY_RANKS = {
    "INFO": 10,
    "WARNING": 20,
    "ERROR": 30,
    "CRITICAL": 40,
}


def notify_alert(settings: AppSettings, alert: dict[str, object]) -> None:
    if not _should_attempt_notification(settings, alert):
        return

    fingerprint = _alert_fingerprint(alert)
    now = _alert_datetime(alert)
    state = _load_notification_state(settings)
    fingerprints = state.setdefault("fingerprints", {})
    if not isinstance(fingerprints, dict):
        fingerprints = {}
        state["fingerprints"] = fingerprints
    entry = fingerprints.setdefault(fingerprint, {})
    if not isinstance(entry, dict):
        entry = {}
        fingerprints[fingerprint] = entry

    if _is_throttled(settings, entry=entry, now=now):
        entry["last_suppressed_at"] = now.isoformat(timespec="seconds")
        entry["suppressed_count"] = int(entry.get("suppressed_count", 0)) + 1
        entry["latest_alert"] = _alert_sample(alert)
        _write_notification_state(settings, state)
        return

    entry["last_attempt_at"] = now.isoformat(timespec="seconds")
    entry["latest_alert"] = _alert_sample(alert)
    result = _send_notification(settings, alert=alert, fingerprint=fingerprint, now=now)
    if result["status"] == "sent":
        entry["last_sent_at"] = now.isoformat(timespec="seconds")
        entry["sent_count"] = int(entry.get("sent_count", 0)) + 1
    else:
        entry["last_failed_at"] = now.isoformat(timespec="seconds")
        entry["failure_count"] = int(entry.get("failure_count", 0)) + 1
        _append_notification_failure(
            settings,
            {
                "failed_at": now.isoformat(timespec="seconds"),
                "channel": settings.alert_notification_channel,
                "alert_type": alert.get("alert_type"),
                "severity": alert.get("severity"),
                "fingerprint": fingerprint,
                "error_type": result.get("error_type"),
                "error": result.get("error"),
                "webhook_url_configured": bool(settings.alert_notification_webhook_url),
            },
        )
    _write_notification_state(settings, state)


def _should_attempt_notification(settings: AppSettings, alert: dict[str, object]) -> bool:
    if settings.alert_notification_muted:
        return False
    channel = settings.alert_notification_channel
    if channel in {"", "none", "off", "disabled"}:
        return False
    if channel != "webhook":
        return _is_notifiable_alert(settings, alert)
    return _is_notifiable_alert(settings, alert)


def _is_notifiable_alert(settings: AppSettings, alert: dict[str, object]) -> bool:
    alert_type = str(alert.get("alert_type") or "")
    if alert_type in PROVIDER_DEGRADATION_ALERT_TYPES:
        return True
    severity = _severity_rank(str(alert.get("severity") or ""))
    min_severity = _severity_rank(settings.alert_notification_min_severity)
    return severity >= min_severity


def _send_notification(
    settings: AppSettings,
    *,
    alert: dict[str, object],
    fingerprint: str,
    now: datetime,
) -> dict[str, object]:
    if settings.alert_notification_channel != "webhook":
        return {
            "status": "failed",
            "error_type": "unsupported_channel",
            "error": f"unsupported alert notification channel: {settings.alert_notification_channel}",
        }
    if settings.alert_notification_webhook_url is None:
        return {
            "status": "failed",
            "error_type": "missing_webhook_url",
            "error": "QUANTA_ALERT_WEBHOOK_URL is required when webhook notifications are enabled",
        }

    payload = {
        "source": "quanta",
        "event": "runtime_alert",
        "sent_at": now.isoformat(timespec="seconds"),
        "fingerprint": fingerprint,
        "alert": alert,
        "runtime": {
            "source_provider": settings.source_provider,
            "source_universe": settings.source_universe,
        },
    }
    try:
        request = Request(
            settings.alert_notification_webhook_url,
            data=json.dumps(payload, ensure_ascii=False).encode("utf-8"),
            headers={
                "Content-Type": "application/json; charset=utf-8",
                "User-Agent": "QuantA-alert-notifier/0.1",
            },
            method="POST",
        )
        with urlopen(
            request,
            timeout=max(1, settings.alert_notification_timeout_seconds),
        ) as response:
            status_code = int(response.status)
            if 200 <= status_code < 300:
                return {"status": "sent", "status_code": status_code}
            return {
                "status": "failed",
                "error_type": "http_status",
                "error": f"webhook returned HTTP {status_code}",
            }
    except HTTPError as exc:
        return {
            "status": "failed",
            "error_type": exc.__class__.__name__,
            "error": f"webhook returned HTTP {exc.code}",
        }
    except URLError as exc:
        return {
            "status": "failed",
            "error_type": exc.__class__.__name__,
            "error": _safe_delivery_error(exc.reason),
        }
    except (TimeoutError, OSError, ValueError) as exc:
        return {
            "status": "failed",
            "error_type": exc.__class__.__name__,
            "error": _safe_delivery_error(exc),
        }


def _load_notification_state(settings: AppSettings) -> dict[str, object]:
    path = settings.alert_notification_state_path
    if not path.exists():
        return {"version": 1, "fingerprints": {}}
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {"version": 1, "fingerprints": {}}
    return payload if isinstance(payload, dict) else {"version": 1, "fingerprints": {}}


def _write_notification_state(
    settings: AppSettings,
    state: dict[str, object],
) -> None:
    path = settings.alert_notification_state_path
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(state, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )


def _append_notification_failure(
    settings: AppSettings,
    record: dict[str, object],
) -> None:
    path = settings.alert_notification_failures_path
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(record, ensure_ascii=False, sort_keys=True) + "\n")


def _safe_delivery_error(exc: object) -> str:
    message = str(exc).strip()
    if "://" in message:
        return "webhook delivery failed; error details omitted because they may contain the webhook URL"
    return message or "webhook delivery failed"


def _is_throttled(
    settings: AppSettings,
    *,
    entry: dict[str, object],
    now: datetime,
) -> bool:
    throttle_seconds = max(0, settings.alert_notification_throttle_seconds)
    if throttle_seconds == 0:
        return False
    last_attempt = _parse_alert_timestamp(entry.get("last_attempt_at"))
    if last_attempt is None:
        return False
    elapsed_seconds = (now.astimezone(timezone.utc) - last_attempt).total_seconds()
    return elapsed_seconds < throttle_seconds


def _alert_fingerprint(alert: dict[str, object]) -> str:
    payload = {
        "alert_type": str(alert.get("alert_type") or ""),
        "severity": _normalize_severity(str(alert.get("severity") or "")),
        "message": str(alert.get("message") or ""),
        "scope": _alert_scope(alert),
    }
    serialized = json.dumps(payload, ensure_ascii=False, sort_keys=True)
    return hashlib.sha256(serialized.encode("utf-8")).hexdigest()[:24]


def _alert_scope(alert: dict[str, object]) -> dict[str, object]:
    detail = alert.get("detail")
    if not isinstance(detail, dict):
        return {}
    scope: dict[str, object] = {}
    for key in (
        "provider",
        "status",
        "degradation_category",
        "task_id",
        "task_name",
        "backtest_id",
        "snapshot_id",
        "raw_snapshot_id",
        "biz_date",
        "check_name",
        "type",
        "message",
    ):
        value = detail.get(key)
        if value not in (None, ""):
            scope[key] = value
    failed_findings = detail.get("failed_findings")
    if isinstance(failed_findings, list):
        scope["failed_findings"] = [
            {
                "name": item.get("name"),
                "severity": item.get("severity"),
            }
            for item in failed_findings
            if isinstance(item, dict)
        ][:8]
    return scope


def _alert_sample(alert: dict[str, object]) -> dict[str, object]:
    return {
        "triggered_at": alert.get("triggered_at"),
        "alert_type": alert.get("alert_type"),
        "severity": alert.get("severity"),
        "message": alert.get("message"),
    }


def _alert_datetime(alert: dict[str, object]) -> datetime:
    return _parse_alert_timestamp(alert.get("triggered_at")) or datetime.now(CN_TZ)


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
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=CN_TZ)
    return parsed.astimezone(timezone.utc)


def _severity_rank(raw_value: str) -> int:
    return SEVERITY_RANKS.get(_normalize_severity(raw_value), 0)


def _normalize_severity(raw_value: str) -> str:
    normalized = raw_value.strip().upper()
    if normalized == "WARN":
        return "WARNING"
    return normalized
