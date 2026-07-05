# M3 Screener Engine Progress

## Current State

QuantA 已经具备最小可用的 DuckDB-backed 选股引擎：analysis artifacts 会驱动三策略候选池，`screener_run` / `screener_result` 通过 dedicated API 暴露，读取链路也已切到显式只读连接。

## Last Completed

1. 为 `screener_result` 补齐趋势、量价、资金、过滤等分项得分字段。
2. 增加 screener bootstrap，从 READY snapshot 和分析产物重建 `screener_run` / `screener_result`。
3. 落地 `GET /api/v1/screener/runs/latest`、`GET /api/v1/screener/runs/{run_id}`、`GET /api/v1/screener/runs/{run_id}/results`。
4. 把 startup/bootstrap 和 DuckDB 只读查询路径分离，消除读取时重算与锁冲突。
5. 把 screener 状态接进 `init_dev.sh`、`scripts/smoke.sh` 与 app smoke。

## Verification

1. `python3 -m backend.app.domains.screener.bootstrap --print-summary`
2. `scripts/init_dev.sh`
3. `scripts/smoke.sh`
4. `pnpm run backend:dev`
5. `pnpm run frontend:dev`

## Next Step

继续沿 [2026-03-27-m4-backtest-replay.md](2026-03-27-m4-backtest-replay.md) 推进最小回测请求、成交明细、资金曲线和 dedicated backtest API，再把这些结果接进前端工作台。
