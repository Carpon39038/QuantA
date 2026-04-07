#!/usr/bin/env python3

from __future__ import annotations

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


def main() -> int:
    required_keys = ("QUANTA_SOURCE_PROVIDER", "QUANTA_TUSHARE_TOKEN")
    missing = [key for key in required_keys if not os.environ.get(key)]
    if missing:
        raise ValueError(
            "tushare_live_sync_smoke requires env vars: " + ", ".join(missing)
        )
    if os.environ.get("QUANTA_SOURCE_PROVIDER") != "tushare":
        raise ValueError(
            "tushare_live_sync_smoke requires QUANTA_SOURCE_PROVIDER=tushare"
        )

    with tempfile.TemporaryDirectory(prefix="quanta-live-sync-") as temp_dir:
        runtime_dir = Path(temp_dir)
        env = os.environ.copy()
        env.update(
            {
                "QUANTA_RUNTIME_DATA_DIR": str(runtime_dir),
                "QUANTA_DUCKDB_PATH": str(runtime_dir / "duckdb" / "quanta.duckdb"),
            }
        )

        completed = subprocess.run(
            ["python3", "-m", "backend.app.domains.market_data.sync", "--print-summary"],
            cwd=ROOT,
            env=env,
            check=True,
            capture_output=True,
            text=True,
        )

        connection = duckdb.connect(str(runtime_dir / "duckdb" / "quanta.duckdb"), read_only=True)
        try:
            raw_snapshot_id, source_watermark_json = connection.execute(
                """
                SELECT raw_snapshot_id, source_watermark_json
                FROM raw_snapshot
                ORDER BY snapshot_seq DESC
                LIMIT 1
                """
            ).fetchone()
            snapshot_id, artifact_status_json = connection.execute(
                """
                SELECT snapshot_id, artifact_status_json
                FROM artifact_publish
                ORDER BY publish_seq DESC
                LIMIT 1
                """
            ).fetchone()
            fundamental_feature_count = int(
                connection.execute(
                    "SELECT COUNT(*) FROM fundamental_feature_daily WHERE snapshot_id = ?",
                    [snapshot_id],
                ).fetchone()[0]
            )
            corporate_action_count = int(
                connection.execute(
                    "SELECT COUNT(*) FROM corporate_action_item WHERE snapshot_id = ?",
                    [snapshot_id],
                ).fetchone()[0]
            )
        finally:
            connection.close()

        alerts_path = runtime_dir / "logs" / "alerts.jsonl"
        alerts = []
        if alerts_path.exists():
            alerts = [
                json.loads(line)
                for line in alerts_path.read_text(encoding="utf-8").splitlines()
                if line.strip()
            ]

        summary = {
            "ok": True,
            "source_universe": env.get("QUANTA_SOURCE_UNIVERSE", "core_operating_40"),
            "source_validation_providers": env.get(
                "QUANTA_SOURCE_VALIDATION_PROVIDERS",
                "akshare,baostock",
            ).split(","),
            "disclosure_provider": env.get("QUANTA_DISCLOSURE_PROVIDER", "auto"),
            "sync_stdout": completed.stdout.strip().splitlines(),
            "raw_snapshot_id": raw_snapshot_id,
            "snapshot_id": snapshot_id,
            "source_watermark": json.loads(source_watermark_json),
            "artifact_status": json.loads(artifact_status_json),
            "fundamental_feature_count": fundamental_feature_count,
            "corporate_action_count": corporate_action_count,
            "shadow_validation": json.loads(source_watermark_json).get(
                "shadow_validation"
            ),
            "alert_count": len(alerts),
            "alerts": alerts[-10:],
        }
        print(json.dumps(summary, ensure_ascii=False, indent=2))

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
