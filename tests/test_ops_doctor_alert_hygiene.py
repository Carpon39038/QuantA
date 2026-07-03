from __future__ import annotations

from datetime import datetime, timedelta, timezone

from scripts.ops_doctor import _build_findings


CN_TZ = timezone(timedelta(hours=8))


def test_alert_hygiene_passes_when_errors_are_trading_old_or_acknowledged() -> None:
    alerts = [
        {
            "triggered_at": "2026-07-01T22:55:05+08:00",
            "alert_type": "scheduler_loop_failure",
            "severity": "error",
            "message": "old scheduler failure",
        },
        {
            "triggered_at": "2026-07-03T15:00:47+08:00",
            "alert_type": "scheduler_loop_failure",
            "severity": "ERROR",
            "message": "confirmed scheduler failure",
        },
        {
            "triggered_at": "2026-07-03T09:30:11+08:00",
            "alert_type": "intraday_stop_loss_triggered",
            "severity": "ERROR",
            "message": "trading stop loss trigger",
        },
    ]

    findings = _build_findings(
        health=_healthy_payload(),
        alerts=alerts,
        queue_files=_empty_queue_files(),
        source_latest_biz_date=None,
        fail_on_alert=True,
        alert_window_hours=24,
        alert_acknowledged_before="2026-07-03T16:04:00+08:00",
        now=datetime(2026, 7, 3, 17, 0, tzinfo=CN_TZ),
    )

    finding = _finding(findings, "recent_error_alerts")
    counts = finding["detail"]["counts"]
    assert finding["severity"] == "pass"
    assert counts["error_alerts"] == 3
    assert counts["outside_window_operational_error_alerts"] == 1
    assert counts["acknowledged_operational_error_alerts"] == 1
    assert counts["trading_signal_error_alerts"] == 1
    assert counts["unconfirmed_operational_error_alerts"] == 0


def test_alert_hygiene_fails_on_unconfirmed_operational_error() -> None:
    alerts = [
        {
            "triggered_at": "2026-07-03T16:30:00+08:00",
            "alert_type": "service_queue_failure",
            "severity": "error",
            "message": "worker retry exhausted",
        },
        {
            "triggered_at": "2026-07-03T16:31:00+08:00",
            "alert_type": "intraday_stop_loss_triggered",
            "severity": "ERROR",
            "message": "trading stop loss trigger",
        },
    ]

    findings = _build_findings(
        health=_healthy_payload(),
        alerts=alerts,
        queue_files=_empty_queue_files(),
        source_latest_biz_date=None,
        fail_on_alert=True,
        alert_window_hours=24,
        alert_acknowledged_before="2026-07-03T16:04:00+08:00",
        now=datetime(2026, 7, 3, 17, 0, tzinfo=CN_TZ),
    )

    finding = _finding(findings, "recent_error_alerts")
    counts = finding["detail"]["counts"]
    assert finding["severity"] == "fail"
    assert counts["error_alerts"] == 2
    assert counts["trading_signal_error_alerts"] == 1
    assert counts["unconfirmed_operational_error_alerts"] == 1
    assert finding["detail"]["unconfirmed_operational_error_samples"] == [
        {
            "triggered_at": "2026-07-03T16:30:00+08:00",
            "alert_type": "service_queue_failure",
            "severity": "error",
            "message": "worker retry exhausted",
        }
    ]


def _healthy_payload() -> dict[str, object]:
    return {
        "status": "ok",
        "history_coverage": {
            "open_day_count": 1,
            "end_biz_date": "2026-07-03",
        },
    }


def _empty_queue_files() -> dict[str, int]:
    return {
        "service_pending": 0,
        "service_processing": 0,
        "service_completed": 0,
        "service_failed": 0,
        "backtest_pending": 0,
        "backtest_processing": 0,
        "backtest_completed": 0,
        "backtest_failed": 0,
    }


def _finding(
    findings: list[dict[str, object]],
    name: str,
) -> dict[str, object]:
    return next(item for item in findings if item.get("name") == name)
