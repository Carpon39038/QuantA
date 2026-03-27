#!/usr/bin/env bash

set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"

echo "[init] QuantA execution harness bootstrap"
echo "[init] workspace: $ROOT"

required_commands=(bash git python3)
missing_commands=()

for command_name in "${required_commands[@]}"; do
  if ! command -v "$command_name" >/dev/null 2>&1; then
    missing_commands+=("$command_name")
  fi
done

if (( ${#missing_commands[@]} > 0 )); then
  echo "[init] missing required commands: ${missing_commands[*]}" >&2
  exit 1
fi

for command_name in node pnpm; do
  if command -v "$command_name" >/dev/null 2>&1; then
    echo "[init] optional tool available: $command_name"
  else
    echo "[init] optional tool missing: $command_name"
  fi
done

if python3 -c "import duckdb" >/dev/null 2>&1; then
  echo "[init] python module available: duckdb"
else
  echo "[init] missing required python module: duckdb" >&2
  echo "[init] install it with: python3 -m pip install --user duckdb" >&2
  exit 1
fi

python3 -m backend.app.domains.tasking.bootstrap
python3 -m backend.app.domains.market_data.bootstrap --print-summary
python3 "$ROOT/scripts/check_harness_docs.py"
python3 "$ROOT/scripts/check_execution_harness.py" --print-summary

echo "[init] operator loop:"
echo "[init] 1. Read the active plan, acceptance file, and progress handoff."
echo "[init] 2. Run scripts/smoke.sh before changing code."
echo "[init] 3. Use pnpm run backend:dev / pnpm run frontend:dev when you need live services."
echo "[init] 4. Implement one scoped task, verify it, then update progress and acceptance."
echo "[init] 5. Before declaring a milestone complete, run:"
echo "[init]    python3 scripts/check_execution_harness.py --require-all-passing"
