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

mkdir -p data/logs

case "${1:-}" in
  backend)
    exec pnpm run backend:dev
    ;;
  frontend)
    exec pnpm run frontend:dev
    ;;
  pipeline)
    python3 -m backend.app.domains.tasking.bootstrap >/dev/null
    python3 -m backend.app.domains.market_data.bootstrap >/dev/null
    python3 -m backend.app.domains.analysis.bootstrap >/dev/null
    python3 -m backend.app.domains.screener.bootstrap >/dev/null
    python3 -m backend.app.domains.backtest.bootstrap >/dev/null
    exec pnpm run pipeline:daemon
    ;;
  doctor)
    exec python3 scripts/after_close_check.py \
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
