# M4 Backtest Replay

## Goal

在 QuantA 的 READY snapshot 与 screener 结果之上落地最小 v1.0 回测回放层，让 `backtest_request`、`backtest_run`、`backtest_trade`、`backtest_equity_curve` 都可以被生成、读取并展示。

## Scope

本计划聚焦：

1. 为回测补齐 `backtest_request`、`backtest_trade`、`backtest_equity_curve` schema
2. 增加 deterministic backtest bootstrap，从 latest screener Top N 生成最小等权回放
3. 提供 `GET /api/v1/backtests/runs/latest`、`GET /api/v1/backtests/runs/{backtest_id}`、`/trades`、`/equity-curve`
4. 让 `latest snapshot` 回测摘要改读真实 `backtest_run`
5. 把 stock detail / screener / backtest 详情接进前端 workbench

## Non-Goals

本计划不包含：

1. 提供真正的异步 worker、手动回测 POST 和 durable queue 消费器
2. 完整实现涨跌停、停牌拒单和撮合细节
3. 增加 benchmark 历史曲线和参数优化
4. 完成独立多页面路由与浏览器级 UI regression

## Done When

1. 每个 READY snapshot 都有可重复生成的 `backtest_request` / `run` / `trade` / `equity_curve`。
2. latest snapshot 回测摘要来自回测表而不是 seed。
3. dedicated backtest API 可返回请求、指标、交易记录和资金曲线。
4. 前端 workbench 可展示 focus stock、screener 结果和 backtest 详情。
5. `scripts/smoke.sh` 会验证 dedicated screener/backtest API 与前端详情壳子。

## Verify By

1. `python3 -m backend.app.domains.backtest.bootstrap --print-summary`
2. `node --check frontend/src/app/main.js`
3. `scripts/init_dev.sh`
4. `scripts/smoke.sh`
5. `pnpm run backend:dev`
6. `pnpm run frontend:dev`

## Tasks

- [x] 为回测补齐 request / trade / equity curve schema
- [x] 增加 deterministic backtest bootstrap
- [x] 提供 dedicated backtest latest/detail/trades/equity API
- [x] 让 latest snapshot 回测摘要改读真实 `backtest_run`
- [x] 把 focus stock、backtest detail 和 equity curve 接进前端 workbench
- [x] 把 backtest 状态接进 init/smoke 和 app smoke
- [ ] 落地真正的 POST/queue/worker 手动触发链

## Decisions

1. M4 先用 `Top N 等权窗口回放` 作为 deterministic replay，先验证数据绑定、成交明细和曲线结构。
2. 成交价格口径固定为 `raw`，并保留 `signal_price_basis` 与 `execution_price_basis` 分离。
3. `backtest_request` 先作为本地 durable queue 的最小持久化对象，不强行提前做异步 worker。
4. 前端先做单页 workbench 深化，先把详情链打通，再按页面能力拆出独立路由。

## Status

当前状态：M4 最小回测回放层已落地，包含 request/run/trade/equity 表、dedicated backtest API，以及读取详情 API 的 workbench 页面；下一步进入 M5，把手动触发、任务编排和更真实的运行状态链补齐。
