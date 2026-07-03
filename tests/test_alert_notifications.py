from __future__ import annotations

from http.server import BaseHTTPRequestHandler, HTTPServer
import json
from pathlib import Path
from threading import Thread
from typing import Any

from backend.app.app_wiring.settings import AppSettings, load_settings
from backend.app.shared.telemetry.alerts import emit_alert
from scripts.after_close_check import _emit_after_close_failure_alert


class _WebhookHandler(BaseHTTPRequestHandler):
    def do_POST(self) -> None:
        body = self.rfile.read(int(self.headers.get("Content-Length", "0")))
        self.server.payloads.append(json.loads(body.decode("utf-8")))  # type: ignore[attr-defined]
        self.send_response(204)
        self.end_headers()

    def log_message(self, format: str, *args: Any) -> None:
        return


def test_provider_degradation_webhook_is_sent_once_with_throttle(
    tmp_path: Path,
    monkeypatch,
) -> None:
    server, thread, webhook_url = _start_webhook_server()
    try:
        settings = _notification_settings(
            tmp_path,
            monkeypatch,
            webhook_url=webhook_url,
            throttle_seconds=3600,
        )

        for _ in range(2):
            emit_alert(
                settings,
                alert_type="shadow_validation_provider_degraded",
                severity="warning",
                message="Shadow validation provider akshare is UNAVAILABLE",
                detail={
                    "provider": "akshare",
                    "status": "UNAVAILABLE",
                    "degradation_category": "akshare_upstream_connectivity",
                    "snapshot_id": "snapshot_1",
                    "biz_date": "2026-07-03",
                },
            )

        assert len(server.payloads) == 1  # type: ignore[attr-defined]
        payload = server.payloads[0]  # type: ignore[attr-defined]
        assert payload["event"] == "runtime_alert"
        assert payload["alert"]["alert_type"] == "shadow_validation_provider_degraded"
        assert payload["alert"]["severity"] == "warning"

        alert_lines = settings.alerts_path.read_text(encoding="utf-8").splitlines()
        assert len(alert_lines) == 2
        state = json.loads(settings.alert_notification_state_path.read_text(encoding="utf-8"))
        entries = list(state["fingerprints"].values())
        assert len(entries) == 1
        assert entries[0]["sent_count"] == 1
        assert entries[0]["suppressed_count"] == 1
    finally:
        server.shutdown()
        thread.join(timeout=2)


def test_notification_failure_is_logged_without_leaking_webhook_secret(
    tmp_path: Path,
    monkeypatch,
) -> None:
    settings = _notification_settings(
        tmp_path,
        monkeypatch,
        webhook_url="http://127.0.0.1:1/secret-token",
        timeout_seconds=1,
    )

    emit_alert(
        settings,
        alert_type="service_queue_failure",
        severity="error",
        message="Service task T-1 exhausted retries",
        detail={
            "task_id": "T-1",
            "task_name": "daily_sync",
            "snapshot_id": "snapshot_1",
            "error": "boom",
        },
    )

    alert_lines = settings.alerts_path.read_text(encoding="utf-8").splitlines()
    assert len(alert_lines) == 1
    failure_lines = settings.alert_notification_failures_path.read_text(
        encoding="utf-8"
    ).splitlines()
    assert len(failure_lines) == 1
    assert "secret-token" not in failure_lines[0]
    failure = json.loads(failure_lines[0])
    assert failure["alert_type"] == "service_queue_failure"
    assert failure["webhook_url_configured"] is True


def test_after_close_hard_gate_failure_uses_alert_notification_bridge(
    tmp_path: Path,
    monkeypatch,
) -> None:
    server, thread, webhook_url = _start_webhook_server()
    try:
        settings = _notification_settings(
            tmp_path,
            monkeypatch,
            webhook_url=webhook_url,
            throttle_seconds=0,
        )
        emitted = _emit_after_close_failure_alert(
            settings,
            {
                "status": "fail",
                "doctor": {
                    "status": "fail",
                    "snapshot_id": "snapshot_1",
                    "snapshot_biz_date": "2026-07-03",
                    "source_provider": "tushare",
                    "source_universe": "core_operating_40",
                    "findings": [
                        {
                            "name": "recent_error_alerts",
                            "severity": "fail",
                            "message": "unconfirmed operational error alerts: 1",
                        }
                    ],
                },
                "after_close_findings": [
                    {
                        "name": "pipeline_jsonl_log",
                        "severity": "pass",
                        "message": "fresh",
                    }
                ],
            },
        )

        assert emitted is True
        assert len(server.payloads) == 1  # type: ignore[attr-defined]
        alert = server.payloads[0]["alert"]  # type: ignore[attr-defined]
        assert alert["alert_type"] == "after_close_hard_gate_failure"
        assert alert["detail"]["failed_findings"] == [
            {
                "name": "recent_error_alerts",
                "severity": "fail",
                "message": "unconfirmed operational error alerts: 1",
            }
        ]
    finally:
        server.shutdown()
        thread.join(timeout=2)


def _notification_settings(
    tmp_path: Path,
    monkeypatch,
    *,
    webhook_url: str,
    throttle_seconds: int = 900,
    timeout_seconds: int = 5,
) -> AppSettings:
    monkeypatch.setenv("QUANTA_RUNTIME_DATA_DIR", str(tmp_path))
    monkeypatch.setenv("QUANTA_DUCKDB_PATH", str(tmp_path / "duckdb" / "quanta.duckdb"))
    monkeypatch.setenv("QUANTA_ALERT_NOTIFICATION_CHANNEL", "webhook")
    monkeypatch.setenv("QUANTA_ALERT_WEBHOOK_URL", webhook_url)
    monkeypatch.setenv("QUANTA_ALERT_NOTIFICATION_THROTTLE_SECONDS", str(throttle_seconds))
    monkeypatch.setenv("QUANTA_ALERT_NOTIFICATION_TIMEOUT_SECONDS", str(timeout_seconds))
    return load_settings()


def _start_webhook_server() -> tuple[HTTPServer, Thread, str]:
    server = HTTPServer(("127.0.0.1", 0), _WebhookHandler)
    server.payloads = []  # type: ignore[attr-defined]
    thread = Thread(target=server.serve_forever, daemon=True)
    thread.start()
    return server, thread, f"http://127.0.0.1:{server.server_port}/hook"
