# M14 History Backfill Tasking

## Goal

把已经落地的最小历史回补能力接入 QuantA 的正式 service queue / worker / scheduler / API，让 backfill 不再只是 CLI 操作。

## Scope

本计划聚焦：

1. 为 service task 增加 `history_backfill`。
2. 为 API 增加 `POST /api/v1/tasks/history-backfill/run`。
3. 让 scheduler 在 source 领先于最新 READY snapshot 时优先 enqueue `history_backfill`。
4. 确保 `history_backfill` 不会留下悬空 `BUILDING` snapshot，而是把回补出的 snapshot 继续推进到 `READY`。

## Non-Goals

本计划不包含：

1. 设计完整的长期回补窗口策略。
2. 接官方披露源或分钟级历史。
3. 引入独立的 backfill 专用数据库表。

## Done When

1. `history_backfill` 已加入 `SUPPORTED_SERVICE_TASKS` 并能通过 durable queue / worker 执行。
2. API 可接受 backfill 请求并返回 `202 accepted`。
3. scheduler 在需要 catch-up 时会优先 enqueue `history_backfill`。
4. app smoke 与 pipeline smoke 都通过。

## Verify By

1. `python3 scripts/pipeline_smoke.py`
2. `scripts/smoke.sh`
3. `python3 scripts/check_harness_docs.py`

## Tasks

- [x] 为 service runner / queue / worker 增加 `history_backfill`
- [x] 为 backend API 增加 `POST /api/v1/tasks/history-backfill/run`
- [x] 让 scheduler 默认优先走 `history_backfill` catch-up
- [x] 让 `history_backfill` 把新增 snapshot 推进到 `READY`
- [x] 把这条链接进 app smoke / 系统记录

## Decisions

1. `history_backfill` 复用现有 `daily_sync -> daily_screener -> daily_backtest` 能力，不单独引入新的历史产物物化器。
2. queue 层允许显式传入 `start_biz_date/end_biz_date`；若未传，则按“最新 READY snapshot 之后到 source 最新日期”的最小 catch-up 区间自动推导。
3. scheduler 发现 source 更新领先时，优先走 `history_backfill` 而不是单日 `daily_sync`，以统一 catch-up 语义。

## Status

当前状态：M14 已完成。历史回补已成为正式 service task，并通过 API、queue、worker、scheduler 和 app smoke 验证。下一步进入官方披露源与更完整的长期 backfill 策略。
