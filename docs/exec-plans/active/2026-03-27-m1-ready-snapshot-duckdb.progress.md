# M1 Ready Snapshot DuckDB Progress

## Current State

QuantA 已经从“runtime 直接读取 JSON fixture”推进到“fixture 只负责 deterministic seed，backend/frontend latest snapshot 链路读取 DuckDB”。这让 harness 可以继续托住真正的数据底座开发，而不只是 demo 页面。

## Last Completed

1. 定义并版本化第一版 DuckDB schema。
2. 增加本地 dev bootstrap，把现有 published snapshot fixture 导入 DuckDB。
3. 让 backend latest snapshot payload 从 `artifact_publish`、`market_regime_daily`、`screener_run/result`、`backtest_run`、`task_run_log` 组装。
4. 把 DuckDB foundation 状态接进 `init_dev.sh`、`smoke.sh` 和 app smoke。

## Verification

1. `python3 -m backend.app.domains.market_data.bootstrap --print-summary`
2. `python3 scripts/render_db_schema.py`
3. `scripts/init_dev.sh`
4. `scripts/smoke.sh`
5. `pnpm run backend:dev`
6. `pnpm run frontend:dev`

## Next Step

把 `daily_bar`、`price_series_daily` 和最小 as-of 查询真正接进这套 DuckDB foundation，让最新 READY snapshot 不只是可读，还能逐步承接真实盘后数据更新与历史回放。
