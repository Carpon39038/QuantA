#!/usr/bin/env python3

from __future__ import annotations

from datetime import datetime, timedelta
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile

import duckdb


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))


from backend.app.app_wiring.settings import load_settings
from backend.app.shared.providers.market_data_source import build_market_data_provider


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
    provider = build_market_data_provider(settings)
    latest_biz_date = provider.latest_available_biz_date()
    probe_start_date = (
        datetime.fromisoformat(latest_biz_date).date() - timedelta(days=10)
    ).isoformat()
    open_biz_dates = provider.list_open_biz_dates(
        start_biz_date=probe_start_date,
        end_biz_date=latest_biz_date,
    )
    target_biz_dates = open_biz_dates[-5:]
    if len(target_biz_dates) < 2:
        raise AssertionError(
            "tushare_live_backfill_smoke requires at least two recent open biz dates"
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

        first_run = subprocess.run(
            [
                "python3",
                "-m",
                "backend.app.domains.market_data.sync",
                "--start-biz-date",
                target_biz_dates[0],
                "--end-biz-date",
                target_biz_dates[-1],
                "--print-summary",
            ],
            cwd=ROOT,
            env=env,
            check=True,
            capture_output=True,
            text=True,
        )
        second_run = subprocess.run(
            [
                "python3",
                "-m",
                "backend.app.domains.market_data.sync",
                "--start-biz-date",
                target_biz_dates[0],
                "--end-biz-date",
                target_biz_dates[-1],
                "--print-summary",
            ],
            cwd=ROOT,
            env=env,
            check=True,
            capture_output=True,
            text=True,
        )

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
        finally:
            connection.close()

        summary = {
            "ok": True,
            "source_universe": os.environ.get("QUANTA_SOURCE_UNIVERSE", "core_operating_40"),
            "source_validation_providers": ["none"],
            "disclosure_provider": "none",
            "latest_biz_date": latest_biz_date,
            "target_biz_dates": target_biz_dates,
            "first_run_stdout": first_run.stdout.strip().splitlines(),
            "second_run_stdout": second_run.stdout.strip().splitlines(),
            "raw_snapshot_count": raw_snapshot_count,
            "artifact_publish_count": artifact_publish_count,
            "daily_bar_count": daily_bar_count,
            "fundamental_feature_count": fundamental_feature_count,
        }
        print(json.dumps(summary, ensure_ascii=False, indent=2))

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
