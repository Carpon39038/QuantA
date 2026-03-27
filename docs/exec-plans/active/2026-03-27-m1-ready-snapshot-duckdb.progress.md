# M1 Ready Snapshot DuckDB Progress

## Current State

QuantA 已经从“runtime 直接读取 JSON fixture”推进到“fixture 只负责 deterministic seed，backend/frontend latest snapshot 链路读取 DuckDB”，并补上了 `daily_bar`、`price_series_daily` 的两期 seed 与最小 stock as-of 查询。这让 harness 不只托住最新发布快照，也能开始托住最小历史读取能力。

## Last Completed

1. 定义并版本化第一版 DuckDB schema。
2. 增加本地 dev bootstrap，把现有 published snapshot fixture 导入 DuckDB。
3. 让 backend latest snapshot payload 从 `artifact_publish`、`market_regime_daily`、`screener_run/result`、`backtest_run`、`task_run_log` 组装。
4. 把 DuckDB foundation 状态接进 `init_dev.sh`、`smoke.sh` 和 app smoke。
5. 为 `daily_bar`、`price_series_daily` 增加“两期快照 + 局部修订”的 dev seed。
6. 提供 `/api/v1/stocks/{symbol}/snapshot` 与 `/api/v1/stocks/{symbol}/kline` 两个最小 as-of 查询入口。

## Verification

1. `python3 -m backend.app.domains.market_data.bootstrap --print-summary`
2. `python3 scripts/render_db_schema.py`
3. `scripts/init_dev.sh`
4. `scripts/smoke.sh`
5. `pnpm run backend:dev`
6. `pnpm run frontend:dev`

## Next Step

继续沿 [2026-03-27-m2-analysis-artifacts.md](/Users/carpon/web/QuantA/docs/exec-plans/active/2026-03-27-m2-analysis-artifacts.md) 推进分析产物层，并在其基础上进入真实选股和回测链路。
