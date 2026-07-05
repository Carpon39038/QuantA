# M6 Daily Pipeline Orchestration Progress

## Current State

QuantA 已经不只拥有 queue-backed 手动 task 入口，现在还具备最小阶段化日终流水线：`daily_sync -> daily_screener -> daily_backtest`。`daily_sync` 的执行语义已经收窄到数据与分析层，`daily_backtest` 也成为独立 service task。M6 本身已完成，后续可靠性增强转入 M7。

## Last Completed

1. 新增 `backend/app/domains/tasking/service_runner.py`，把 service task 执行语义拆成 `daily_sync`、`daily_screener`、`daily_backtest`。
2. 新增 `POST /api/v1/tasks/daily-backtest/run`，让 backtest 也能走 queue-backed service task。
3. 新增 `backend/app/domains/tasking/scheduler.py`，支持按顺序 enqueue 并运行最小日终流水线。
4. 修正 service queue `task_id` 生成规则，避免 worker 因文件名字母序先跑 `daily_backtest`。
5. 更新 app smoke，验证三段式 service task、manual backtest queue 和清理后的 deterministic baseline。

## Verification

1. `scripts/init_dev.sh`
2. `scripts/smoke.sh`
3. `python3 -m backend.app.domains.tasking.scheduler`
4. `python3 scripts/check_execution_harness.py --require-all-passing`

## Next Step

进入 M7：把 source-backed sync、retry/backoff、alerts 和 resident scheduler 接到这条阶段化流水线，并补 smoke 验证。
