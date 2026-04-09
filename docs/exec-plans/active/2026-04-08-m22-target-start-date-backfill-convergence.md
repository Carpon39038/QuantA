# M22 Target Start Date Backfill Convergence

## Goal

把 QuantA 从“会按窗口向前补历史”继续推进到“能按具体起始日期精确推进历史覆盖”，让 `corporate_action` reconciliation 可以围绕最近未覆盖事件日持续收敛，而不再只靠猜 `open_day_count`。

## Scope

1. 为 `market_data.sync` 增加 `--target-start-biz-date YYYY-MM-DD`。
2. 为 `history_backfill` 的 API / queue / worker / service path 增加 `target_start_biz_date` 语义。
3. 为 scheduler 增加 `QUANTA_HISTORY_BACKFILL_TARGET_START_BIZ_DATE`，并定义其优先级高于 `QUANTA_HISTORY_BACKFILL_TARGET_OPEN_DAYS`。
4. 让 live backfill smoke 支持 `QUANTA_LIVE_BACKFILL_TARGET_START_BIZ_DATE`，并输出 target-date 收敛结果。
5. 用真实 Tushare live 回补验证：先把覆盖精确推进到 `2026-01-29`，再继续推进到 `2026-01-20`，观察 `corporate_action` 的 `boundary_gap` 是否被消掉。

## Non-Goals

1. 本里程碑不把默认开发链改成固定深历史。
2. 本里程碑不一次性吃掉全部 `out_of_coverage` 企业行为事件。
3. 本里程碑不新增远端通知渠道。

## Acceptance

1. `python3 -m backend.app.domains.market_data.sync --target-start-biz-date YYYY-MM-DD --print-summary` 可用。
2. `POST /api/v1/tasks/history-backfill/run`、queue / worker / scheduler 支持 `target_start_biz_date`。
3. 当 `QUANTA_HISTORY_BACKFILL_TARGET_START_BIZ_DATE` 被设置时，scheduler 会优先按目标起始日扩展历史覆盖，而不是只看 `target_open_days`。
4. live `QUANTA_LIVE_BACKFILL_TARGET_START_BIZ_DATE=2026-01-29 python3 scripts/tushare_live_backfill_smoke.py` 会把 `corporate_action` 推进到 `checked=4`，并显式暴露边界缺口。
5. live `QUANTA_LIVE_BACKFILL_TARGET_START_BIZ_DATE=2026-01-20 python3 scripts/tushare_live_backfill_smoke.py` 会把 `corporate_action` 推进到 `checked=5/aligned=5/boundary_gap=0`。

## Tasks

- [x] 增加 target-start-date resolver 与 sync CLI
- [x] 接入 history_backfill queue / worker / API / service path 的 `target_start_biz_date`
- [x] 让 scheduler 支持 `QUANTA_HISTORY_BACKFILL_TARGET_START_BIZ_DATE`
- [x] 升级 live backfill smoke 输出 target-date 结果
- [x] 用真实 Tushare live 回补验证 `2026-01-29` 与 `2026-01-20` 两个收敛点

## Notes

1. `target_start_biz_date` 解决的是“已知最近缺口在哪一天，就直接补到那一天”的问题；它不是 `lookback_open_days` 的替代，而是更精确的 follow-up 工具。
2. 当企业行为事件正好落在覆盖起点上时，系统会明确报 `boundary_gap`，提醒需要再往前补至少一个交易日，而不是把它误记为 canonical mismatch。
