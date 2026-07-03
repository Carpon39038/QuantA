#!/usr/bin/env bash
set -euo pipefail

cd "$(dirname "$0")/.."

export PATH="/opt/homebrew/bin:/usr/local/bin:/usr/bin:/bin:/usr/sbin:/sbin:${PATH:-}"

ENV_FILE="${QUANTA_ENV_FILE:-data/env/live.env}"
if [[ -f "$ENV_FILE" ]]; then
  set -a
  # shellcheck disable=SC1090
  source "$ENV_FILE"
  set +a
fi

find_python_bin() {
  if [[ -n "${QUANTA_PYTHON_BIN:-}" ]]; then
    if [[ -x "$QUANTA_PYTHON_BIN" ]] && "$QUANTA_PYTHON_BIN" -c "import duckdb" >/dev/null 2>&1; then
      printf '%s\n' "$QUANTA_PYTHON_BIN"
      return 0
    fi
    echo "QUANTA_PYTHON_BIN does not point to a Python with duckdb: $QUANTA_PYTHON_BIN" >&2
    return 1
  fi

  local candidates=()
  local command_python
  if command_python="$(command -v python3 2>/dev/null)"; then
    candidates+=("$command_python")
  fi
  candidates+=(
    "/Applications/Xcode.app/Contents/Developer/usr/bin/python3"
    "/usr/bin/python3"
    "/opt/homebrew/bin/python3"
    "/usr/local/bin/python3"
  )

  local candidate
  local seen=":"
  for candidate in "${candidates[@]}"; do
    [[ -x "$candidate" ]] || continue
    case "$seen" in
      *":$candidate:"*) continue ;;
    esac
    seen="${seen}${candidate}:"
    if "$candidate" -c "import duckdb" >/dev/null 2>&1; then
      printf '%s\n' "$candidate"
      return 0
    fi
  done

  echo "No usable python3 found. Set QUANTA_PYTHON_BIN to a Python that can import duckdb." >&2
  return 1
}

PYTHON_BIN="$(find_python_bin)"
export QUANTA_PYTHON_BIN="$PYTHON_BIN"

mkdir -p data/logs

run_bootstrap_module() {
  local module="$1"
  local attempts="${QUANTA_OPS_BOOTSTRAP_ATTEMPTS:-3}"
  local retry_seconds="${QUANTA_OPS_BOOTSTRAP_RETRY_SECONDS:-2}"
  local attempt
  local output_file

  output_file="$(mktemp -t quanta-bootstrap.XXXXXX)"
  for ((attempt = 1; attempt <= attempts; attempt += 1)); do
    if "$PYTHON_BIN" -m "$module" >"$output_file" 2>&1; then
      rm -f "$output_file"
      return 0
    fi

    if grep -q "Could not set lock on file" "$output_file"; then
      if ((attempt < attempts)); then
        echo "bootstrap warning: $module hit a DuckDB lock; retrying in ${retry_seconds}s (${attempt}/${attempts})" >&2
        sleep "$retry_seconds"
        continue
      fi

      echo "bootstrap warning: $module skipped after DuckDB lock retries; resident daemon will report health/alerts" >&2
      sed 's/^/[bootstrap] /' "$output_file" >&2
      rm -f "$output_file"
      return 0
    fi

    sed 's/^/[bootstrap] /' "$output_file" >&2
    rm -f "$output_file"
    return 1
  done

  rm -f "$output_file"
  return 1
}

case "${1:-}" in
  backend)
    export QUANTA_BACKEND_SKIP_BOOTSTRAP="${QUANTA_BACKEND_SKIP_BOOTSTRAP:-1}"
    exec "$PYTHON_BIN" -m backend.app.api.dev_server
    ;;
  frontend)
    exec "$PYTHON_BIN" scripts/run_frontend.py
    ;;
  pipeline)
    run_bootstrap_module backend.app.domains.tasking.bootstrap
    run_bootstrap_module backend.app.domains.market_data.bootstrap
    run_bootstrap_module backend.app.domains.analysis.bootstrap
    run_bootstrap_module backend.app.domains.screener.bootstrap
    run_bootstrap_module backend.app.domains.backtest.bootstrap
    exec "$PYTHON_BIN" -m backend.app.domains.tasking.scheduler --daemon --auto-pipeline --stream-ticks
    ;;
  doctor)
    exec "$PYTHON_BIN" scripts/after_close_check.py \
      --live-source \
      --require-http \
      --require-fresh-pipeline-log \
      --fail-on-alert
    ;;
  *)
    echo "Usage: bash scripts/ops_entrypoint.sh {backend|frontend|pipeline|doctor}" >&2
    exit 64
    ;;
esac
