# M4 Backtest Replay Progress

## Current State

QuantA 现在已经从“首页里有一个回测摘要卡片”推进到“DuckDB 中有最小回测 request/run/trade/equity 产物，且前后端都能独立读取这些详情”。前端 workbench 也已经开始直接消费 screener/backtest/stock detail API。

## Last Completed

1. 为回测补齐 `backtest_request`、`backtest_trade`、`backtest_equity_curve` schema。
2. 增加 deterministic backtest bootstrap，从 READY snapshot 的 Top N 候选生成等权窗口回放。
3. 落地 `GET /api/v1/backtests/runs/latest`、`GET /api/v1/backtests/runs/{backtest_id}`、`/trades`、`/equity-curve`。
4. 让 latest snapshot 回测摘要改读真实 `backtest_run`。
5. 把 focus stock、价格轨迹、指标/信号、资金特征、回测交易记录和资金曲线接进 workbench 页面。

## Verification

1. `python3 -m backend.app.domains.backtest.bootstrap --print-summary`
2. `node --check frontend/src/app/main.js`
3. `scripts/init_dev.sh`
4. `scripts/smoke.sh`
5. `pnpm run backend:dev`
6. `pnpm run frontend:dev`

## Next Step

继续推进 M5：补 `GET /api/v1/tasks/runs`、手动触发 backtest/screener 的 POST 入口、本地 durable request queue 的消费动作，以及更真实的任务状态与健康检查链路。
