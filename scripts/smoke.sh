#!/usr/bin/env bash

set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"

echo "[smoke] shell syntax"
bash -n "$ROOT/scripts/init_dev.sh" "$ROOT/scripts/smoke.sh"

echo "[smoke] repo harness docs"
python3 "$ROOT/scripts/check_harness_docs.py"

echo "[smoke] execution harness"
python3 "$ROOT/scripts/check_execution_harness.py" --print-summary

echo "[smoke] duckdb snapshot foundation"
python3 -m backend.app.domains.market_data.bootstrap --print-summary

echo "[smoke] backend/frontend startup"
python3 "$ROOT/scripts/app_smoke.py"

echo "[smoke] complete"
