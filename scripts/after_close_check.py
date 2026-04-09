#!/usr/bin/env python3

from __future__ import annotations

import argparse
from datetime import datetime, timezone
import json
from pathlib import Path
import sys
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))


from backend.app.app_wiring.settings import load_settings
from scripts.ops_doctor import build_summary


def main() -> int:
    settings = load_settings()
    parser = argparse.ArgumentParser(description="Run QuantA after-close operations checks.")
    parser.add_argument(
        "--live-source",
        action="store_true",
        help="Call the configured source provider and warn when latest READY is behind it.",
    )
    parser.add_argument(
        "--fail-on-alert",
        action="store_true",
        help="Fail if recent error alerts are present.",
    )
    parser.add_argument(
        "--backend-url",
        default=settings.backend_origin,
        help="Backend origin used for HTTP health checks.",
    )
    parser.add_argument(
        "--skip-http",
        action="store_true",
        help="Skip backend HTTP health check.",
    )
    parser.add_argument(
        "--require-http",
        action="store_true",
        help="Fail, instead of warn, when backend HTTP health check is unavailable.",
    )
    parser.add_argument(
        "--pipeline-log-path",
        default=str(settings.logs_dir / "pipeline-daemon.jsonl"),
        help="Resident scheduler JSONL log to inspect.",
    )
    parser.add_argument(
        "--max-pipeline-log-age-seconds",
        type=int,
        default=900,
        help="Warn if the pipeline JSONL log has not been updated within this many seconds.",
    )
    parser.add_argument(
        "--require-fresh-pipeline-log",
        action="store_true",
        help="Fail, instead of warn, when pipeline JSONL log is missing or stale.",
    )
    args = parser.parse_args()

    doctor_summary = build_summary(
        live_source=args.live_source,
        fail_on_alert=args.fail_on_alert,
    )
    after_close_findings = []
    if not args.skip_http:
        after_close_findings.append(
            _backend_health_finding(
                backend_url=args.backend_url,
                require_http=args.require_http,
            )
        )
    after_close_findings.append(
        _pipeline_log_finding(
            log_path=Path(args.pipeline_log_path),
            max_age_seconds=args.max_pipeline_log_age_seconds,
            require_fresh_log=args.require_fresh_pipeline_log,
        )
    )

    status = _overall_status(
        [str(doctor_summary.get("status"))]
        + [str(finding.get("severity")) for finding in after_close_findings]
    )
    summary = {
        "status": status,
        "doctor": doctor_summary,
        "after_close_findings": after_close_findings,
    }
    print(json.dumps(summary, ensure_ascii=False, indent=2))
    return 1 if status == "fail" else 0


def _backend_health_finding(*, backend_url: str, require_http: bool) -> dict[str, object]:
    health_url = f"{backend_url.rstrip('/')}/health"
    try:
        payload = _fetch_json(health_url, timeout_seconds=5)
    except (HTTPError, URLError, TimeoutError, OSError, json.JSONDecodeError) as exc:
        return {
            "name": "backend_http",
            "severity": "fail" if require_http else "warn",
            "message": f"backend health unavailable: {exc}",
            "url": health_url,
        }

    is_ok = payload.get("status") == "ok"
    return {
        "name": "backend_http",
        "severity": "pass" if is_ok else ("fail" if require_http else "warn"),
        "message": f"backend health status is {payload.get('status')}",
        "url": health_url,
        "snapshot_id": payload.get("snapshot_id"),
    }


def _pipeline_log_finding(
    *,
    log_path: Path,
    max_age_seconds: int,
    require_fresh_log: bool,
) -> dict[str, object]:
    if not log_path.exists():
        return {
            "name": "pipeline_jsonl_log",
            "severity": "fail" if require_fresh_log else "warn",
            "message": f"pipeline log does not exist: {log_path}",
            "log_path": str(log_path),
        }

    last_event = _load_last_json_event(log_path)
    modified_at = datetime.fromtimestamp(log_path.stat().st_mtime, tz=timezone.utc)
    age_seconds = max(0, int((datetime.now(tz=timezone.utc) - modified_at).total_seconds()))
    stale = age_seconds > max_age_seconds
    error_event = (
        isinstance(last_event, dict)
        and (
            last_event.get("event") in {"scheduler_stream_log_error"}
            or last_event.get("error") is not None
        )
    )
    severity = "pass"
    if stale or last_event is None or error_event:
        severity = "fail" if require_fresh_log else "warn"
    return {
        "name": "pipeline_jsonl_log",
        "severity": severity,
        "message": f"pipeline log age is {age_seconds}s; last_event={_event_name(last_event)}",
        "log_path": str(log_path),
        "age_seconds": age_seconds,
        "last_event": last_event,
    }


def _load_last_json_event(log_path: Path) -> dict[str, object] | None:
    last_event = None
    with log_path.open(encoding="utf-8") as handle:
        for line in handle:
            stripped = line.strip()
            if not stripped:
                continue
            last_event = json.loads(stripped)
    return last_event


def _fetch_json(url: str, *, timeout_seconds: int) -> dict[str, object]:
    request = Request(url, headers={"Accept": "application/json"})
    with urlopen(request, timeout=timeout_seconds) as response:
        return json.loads(response.read().decode("utf-8"))


def _event_name(event: dict[str, object] | None) -> str | None:
    return str(event.get("event")) if isinstance(event, dict) else None


def _overall_status(statuses: list[str]) -> str:
    if "fail" in statuses:
        return "fail"
    if "warn" in statuses:
        return "warn"
    return "pass"


if __name__ == "__main__":
    raise SystemExit(main())
