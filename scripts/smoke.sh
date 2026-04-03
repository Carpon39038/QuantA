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

echo "[smoke] analysis artifacts"
python3 -m backend.app.domains.analysis.bootstrap --print-summary

echo "[smoke] screener artifacts"
python3 -m backend.app.domains.screener.bootstrap --print-summary

echo "[smoke] backtest artifacts"
python3 -m backend.app.domains.backtest.bootstrap --print-summary

echo "[smoke] tushare provider mapping"
python3 "$ROOT/scripts/tushare_provider_smoke.py"

echo "[smoke] market data backfill"
python3 "$ROOT/scripts/market_data_backfill_smoke.py"

echo "[smoke] scheduler and retry paths"
python3 "$ROOT/scripts/pipeline_smoke.py"

echo "[smoke] backend/frontend startup"
python3 "$ROOT/scripts/app_smoke.py"

echo "[smoke] complete"
