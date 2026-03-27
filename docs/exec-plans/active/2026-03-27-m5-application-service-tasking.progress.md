# M5 Application Service And Tasking Progress

## Current State

QuantA 已经不只是“可读 latest snapshot 的开发支架”了。当前后端具备最小 queue-backed 应用服务面：可以读 task runs、system health，也可以通过 POST 提交 deterministic daily sync、screener 和 backtest request，并由 worker 异步消费。

## Last Completed

1. 落地 `GET /api/v1/tasks/runs` 与 `GET /api/v1/system/health`。
2. 把 `POST /api/v1/tasks/daily-sync/run` 与 `POST /api/v1/tasks/daily-screener/run` 从同步重跑改成 durable request enqueue。
3. 落地 `POST /api/v1/backtests/runs` 的 durable request + worker 消费路径。
4. 落地 `domains.tasking.worker --task service|backtest`，把 service task 与 backtest request 都接进异步消费。
5. 把新的 GET/POST/worker 服务面接进 app smoke，验证读写分离后仍能稳定启动且 smoke 结束后保持 deterministic baseline。

## Verification

1. `scripts/init_dev.sh`
2. `scripts/smoke.sh`
3. `pnpm run backend:dev`
4. `pnpm run frontend:dev`

## Next Step

继续推进真正的盘后编排能力：补自动调度、失败重试、告警、浏览器级任务面板，以及更真实的数据同步来源。
