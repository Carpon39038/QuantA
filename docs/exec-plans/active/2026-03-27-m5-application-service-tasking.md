# M5 Application Service And Tasking

## Goal

把 QuantA 的数据、分析、选股、回测链路通过最小应用服务面串起来，让开发环境不只“能读结果”，还可以显式查询任务状态、提交 durable request，并由 worker 异步消费 deterministic 重跑。

## Scope

本计划聚焦：

1. 增加 `GET /api/v1/tasks/runs` 与 `GET /api/v1/system/health`
2. 增加 `POST /api/v1/tasks/daily-sync/run`、`POST /api/v1/tasks/daily-screener/run`
3. 增加 `POST /api/v1/backtests/runs` 作为最小手动回测触发入口
4. 增加最小 `queue + worker` 消费链，覆盖 service task 与 backtest request
5. 把这些服务面接进 app smoke
6. 把当前 M5 已落状态写回质量与执行记录

## Non-Goals

本计划不包含：

1. cron/scheduler 驱动的自动盘后编排
2. 用户级参数化回测提交与权限控制
3. 浏览器级任务面板和实时进度流
4. 完整的失败重试、告警和恢复机制

## Done When

1. 前后端可读取最新 snapshot 对应的 task runs 和 system health。
2. 开发者可通过 POST 入口显式提交 daily sync、screener 和 deterministic backtest request。
3. `domains.tasking.worker` 能消费 service/backtest durable queue，并把状态写回 `task_run_log` / `backtest_request`。
4. `scripts/smoke.sh` 会验证新的 GET/POST 服务面与 queue/worker 路径。
5. `backtest_request` 不再只是静态表结构，而是被服务入口实际复用。

## Verify By

1. `scripts/init_dev.sh`
2. `scripts/smoke.sh`
3. `pnpm run backend:dev`
4. `pnpm run frontend:dev`

## Tasks

- [x] 提供 tasks runs 与 system health GET 接口
- [x] 提供 queue-backed daily-sync / daily-screener POST 触发接口
- [x] 提供 queue-backed backtest POST 触发接口
- [x] 落地最小 durable queue 与 worker 消费链
- [x] 把新的 GET/POST 服务面与 worker 路径接进 app smoke
- [ ] 落地自动调度、失败重试和告警链

## Decisions

1. M5 允许先用 deterministic dev seed，但 POST 入口本身必须先升级为 durable request，而不是继续同步改库。
2. `daily-sync` 和 `daily-screener` 复用现有 bootstrap 逻辑，但执行责任从 API 进程移到 worker。
3. query GET 继续保持 DuckDB 只读连接；显式写操作只放到 queue/worker 路径。
4. `backtest_request` 作为最小 durable request object，被手动 POST 触发链与 worker 实际复用。

## Status

当前状态：M5 最小应用服务面已落到 queue-backed manual trigger。`daily-sync`、`daily-screener`、`backtests` POST 都会先写 durable request，再由 `domains.tasking.worker` 异步消费；下一步要补自动调度、失败重试、告警和更完整的任务传播。
