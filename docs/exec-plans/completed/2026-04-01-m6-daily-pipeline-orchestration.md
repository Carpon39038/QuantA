# M6 Daily Pipeline Orchestration

## Goal

把 QuantA 的最小日终链路从“手动逐个触发 task”推进成“有明确阶段边界的可编排流水线”：`daily_sync -> daily_screener -> daily_backtest`。

## Scope

本计划聚焦：

1. 把 service task 执行语义拆成明确阶段，而不是让 `daily_sync` 隐式完成全链路 bootstrap。
2. 增加 `daily_backtest` 作为最小服务级任务，与 `daily_sync`、`daily_screener` 并列。
3. 增加最小 `scheduler` CLI，支持按顺序 enqueue 并执行三段式日终流水线。
4. 把新的阶段化 service task 与 `daily_backtest` 接进 app smoke。
5. 把当前 M6 已落状态写回执行记录与技术债。

## Non-Goals

本计划不包含：

1. 真正的 cron daemon 或常驻 scheduler 进程。
2. 自动失败重试、回退、告警和通知。
3. 真实外部数据源同步。
4. 浏览器级任务面板和实时进度流。

## Done When

1. `daily_sync` 只负责 runtime、market data 与 analysis，不再隐式重建 screener/backtest。
2. `daily_backtest` 能作为 queue-backed service task 被 worker 消费。
3. `domains.tasking.scheduler` 能顺序 enqueue 并跑完 `daily_sync -> daily_screener -> daily_backtest`。
4. `scripts/smoke.sh` 会验证三段式 service task 路径，且清理后基线不漂移。

## Verify By

1. `scripts/init_dev.sh`
2. `scripts/smoke.sh`
3. `python3 -m backend.app.domains.tasking.scheduler`
4. `python3 scripts/check_execution_harness.py --require-all-passing`

## Tasks

- [x] 拆出显式 `service_runner` 阶段执行层
- [x] 增加 `daily_backtest` queue-backed service task 与 API 入口
- [x] 增加顺序执行的 `scheduler` CLI
- [x] 把三段式 service task 路径接进 app smoke
- [x] 把自动重试、告警和常驻调度移交到 M7 独立里程碑

## Decisions

1. `bootstrap_dev_runtime` 继续保留给 dev server startup；任务编排语义则迁移到 `service_runner`。
2. `daily_backtest` 先复用 deterministic backtest bootstrap，优先把阶段边界和调度接口固定下来。
3. service queue 的任务顺序依赖文件名排序，因此 `task_id` 必须以时间戳为前缀，避免按任务名字母序误排。

## Status

当前状态：M6 已完成，最小日终流水线已稳定落地，并成为后续 M7 真实同步与可靠性增强的基础编排层。
