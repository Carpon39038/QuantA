#!/usr/bin/env python3

from __future__ import annotations

import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import time

import duckdb


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))


from backend.app.app_wiring.settings import load_settings
from backend.app.domains.market_data.sync import (
    resolve_source_backfill_window,
    resolve_source_backfill_window_to_start_date,
)


def _log(message: str) -> None:
    print(f"[tushare_live_backfill_smoke] {message}", file=sys.stderr, flush=True)


def main() -> int:
    required_keys = ("QUANTA_SOURCE_PROVIDER", "QUANTA_TUSHARE_TOKEN")
    missing = [key for key in required_keys if not os.environ.get(key)]
    if missing:
        raise ValueError(
            "tushare_live_backfill_smoke requires env vars: " + ", ".join(missing)
        )
    if os.environ.get("QUANTA_SOURCE_PROVIDER") != "tushare":
        raise ValueError(
            "tushare_live_backfill_smoke requires QUANTA_SOURCE_PROVIDER=tushare"
        )

    settings = load_settings()
    lookback_open_days = int(os.environ.get("QUANTA_LIVE_BACKFILL_OPEN_DAYS", "20"))
    target_start_biz_date = os.environ.get("QUANTA_LIVE_BACKFILL_TARGET_START_BIZ_DATE")
    target_end_biz_date = os.environ.get("QUANTA_LIVE_BACKFILL_END_BIZ_DATE")
    skip_rerun = os.environ.get("QUANTA_LIVE_BACKFILL_SKIP_RERUN", "0") == "1"
    _log(
        "resolving window "
        f"target_start={target_start_biz_date or 'auto-lookback'} "
        f"target_end={target_end_biz_date or 'latest-source'}"
    )
    window_started_at = time.perf_counter()
    if target_start_biz_date:
        target_window = resolve_source_backfill_window_to_start_date(
            settings,
            target_start_biz_date=target_start_biz_date,
            end_biz_date=target_end_biz_date,
        )
    else:
        target_window = resolve_source_backfill_window(
            settings,
            lookback_open_days=lookback_open_days,
            end_biz_date=target_end_biz_date,
        )
    window_resolution_elapsed_seconds = time.perf_counter() - window_started_at
    target_biz_dates = list(target_window["target_open_biz_dates"])
    latest_biz_date = str(target_window["end_biz_date"])
    sync_window_args = [
        "--start-biz-date",
        str(target_window["start_biz_date"]),
        "--end-biz-date",
        str(target_window["end_biz_date"]),
    ]
    _log(
        "resolved window "
        f"start={target_window['start_biz_date']} "
        f"end={target_window['end_biz_date']} "
        f"open_days={len(target_biz_dates)} "
        f"elapsed={window_resolution_elapsed_seconds:.3f}s"
    )

    with tempfile.TemporaryDirectory(prefix="quanta-live-backfill-") as temp_dir:
        runtime_dir = Path(temp_dir)
        env = os.environ.copy()
        env.update(
            {
                "QUANTA_RUNTIME_DATA_DIR": str(runtime_dir),
                "QUANTA_DUCKDB_PATH": str(runtime_dir / "duckdb" / "quanta.duckdb"),
                "QUANTA_SOURCE_VALIDATION_PROVIDERS": "none",
                "QUANTA_DISCLOSURE_PROVIDER": "none",
            }
        )

        total_started_at = time.perf_counter()
        first_run_started_at = time.perf_counter()
        _log("starting first latest-artifact backfill run")
        first_run = subprocess.run(
            [
                "python3",
                "-m",
                "backend.app.domains.market_data.sync",
                *sync_window_args,
                "--artifact-mode",
                "latest",
                "--print-summary",
            ],
            cwd=ROOT,
            env=env,
            check=True,
            capture_output=True,
            text=True,
        )
        first_run_elapsed_seconds = time.perf_counter() - first_run_started_at
        _log(f"first run finished elapsed={first_run_elapsed_seconds:.3f}s")
        second_run = None
        second_run_elapsed_seconds = None
        if not skip_rerun:
            second_run_started_at = time.perf_counter()
            _log("starting second latest-artifact no-op rerun")
            second_run = subprocess.run(
                [
                    "python3",
                    "-m",
                    "backend.app.domains.market_data.sync",
                    *sync_window_args,
                    "--artifact-mode",
                    "latest",
                    "--print-summary",
                ],
                cwd=ROOT,
                env=env,
                check=True,
                capture_output=True,
                text=True,
            )
            second_run_elapsed_seconds = time.perf_counter() - second_run_started_at
            _log(f"second run finished elapsed={second_run_elapsed_seconds:.3f}s")
        total_elapsed_seconds = time.perf_counter() - total_started_at

        _log("reading isolated DuckDB summary")
        connection = duckdb.connect(str(runtime_dir / "duckdb" / "quanta.duckdb"), read_only=True)
        try:
            raw_snapshot_count = int(
                connection.execute("SELECT COUNT(*) FROM raw_snapshot").fetchone()[0]
            )
            artifact_publish_count = int(
                connection.execute("SELECT COUNT(*) FROM artifact_publish").fetchone()[0]
            )
            daily_bar_count = int(
                connection.execute("SELECT COUNT(*) FROM daily_bar").fetchone()[0]
            )
            fundamental_feature_count = int(
                connection.execute(
                    "SELECT COUNT(*) FROM fundamental_feature_daily"
                ).fetchone()[0]
            )
            corporate_action_count = int(
                connection.execute(
                    "SELECT COUNT(*) FROM corporate_action_item"
                ).fetchone()[0]
            )
            latest_raw_snapshot_id, latest_source_watermark_json = connection.execute(
                """
                SELECT raw_snapshot_id, source_watermark_json
                FROM raw_snapshot
                ORDER BY snapshot_seq DESC
                LIMIT 1
                """
            ).fetchone()
            latest_snapshot_id = str(
                connection.execute(
                    """
                    SELECT snapshot_id
                    FROM artifact_publish
                    ORDER BY publish_seq DESC
                    LIMIT 1
                    """
                ).fetchone()[0]
            )
            history_coverage = connection.execute(
                """
                SELECT
                  MIN(trade_date),
                  MAX(trade_date),
                  COUNT(DISTINCT trade_date)
                FROM price_series_daily
                WHERE snapshot_id = ?
                  AND price_basis = 'raw'
                """,
                [latest_snapshot_id],
            ).fetchone()
        finally:
            connection.close()

        latest_shadow_validation = json.loads(latest_source_watermark_json).get(
            "shadow_validation",
            {},
        )
        corporate_action_check = latest_shadow_validation.get("canonical_checks", {}).get(
            "corporate_action",
            {},
        )

        summary = {
            "ok": True,
            "source_universe": os.environ.get("QUANTA_SOURCE_UNIVERSE", "core_operating_40"),
            "source_validation_providers": ["none"],
            "disclosure_provider": "none",
            "latest_biz_date": latest_biz_date,
            "lookback_open_days": lookback_open_days,
            "target_start_biz_date": target_start_biz_date,
            "target_end_biz_date": target_end_biz_date,
            "skip_rerun": skip_rerun,
            "target_open_biz_date_count": len(target_biz_dates),
            "target_biz_dates": target_biz_dates,
            "window_resolution_elapsed_seconds": round(
                window_resolution_elapsed_seconds,
                3,
            ),
            "first_run_elapsed_seconds": round(first_run_elapsed_seconds, 3),
            "second_run_elapsed_seconds": (
                round(second_run_elapsed_seconds, 3)
                if second_run_elapsed_seconds is not None
                else None
            ),
            "total_elapsed_seconds": round(total_elapsed_seconds, 3),
            "first_run_stdout": first_run.stdout.strip().splitlines(),
            "second_run_stdout": (
                second_run.stdout.strip().splitlines() if second_run is not None else []
            ),
            "raw_snapshot_count": raw_snapshot_count,
            "artifact_publish_count": artifact_publish_count,
            "daily_bar_count": daily_bar_count,
            "fundamental_feature_count": fundamental_feature_count,
            "corporate_action_count": corporate_action_count,
            "latest_raw_snapshot_id": latest_raw_snapshot_id,
            "history_coverage": {
                "start_biz_date": str(history_coverage[0]) if history_coverage[0] is not None else None,
                "end_biz_date": str(history_coverage[1]) if history_coverage[1] is not None else None,
                "open_day_count": int(history_coverage[2] or 0),
            },
            "corporate_action_check": corporate_action_check,
        }
        print(json.dumps(summary, ensure_ascii=False, indent=2))

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
