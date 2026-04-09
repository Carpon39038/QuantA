# M24 Auto History Backfill Recommendation Loop

## Goal

把 QuantA 从“会给出下一次建议补到哪天”推进到“scheduler 能直接消费这条建议”，让 `target_start_biz_date=auto` 成为最小可运行的自动补数策略，而不是只停留在 operator 手工照着点。

## Scope

1. 支持 `QUANTA_HISTORY_BACKFILL_TARGET_START_BIZ_DATE=auto`。
2. scheduler 在 `auto` 模式下优先消费最新 `history_coverage.recommended_target_start_biz_date`。
3. 当 `auto` recommendation 缺失时，scheduler 回退到 `QUANTA_HISTORY_BACKFILL_TARGET_OPEN_DAYS`。
4. `/api/v1/runtime` 暴露 `resolved_history_backfill_target_start_biz_date`，便于确认 `auto` 当前解析到了哪一天。
5. 补最小 smoke，验证 `auto` recommendation 的解析与 fallback 语义。

## Non-Goals

1. 本里程碑不接远端告警通知。
2. 本里程碑不保证自动补数一次性吃掉全部企业行为历史缺口。
3. 本里程碑不改变 canonical 数据口径。

## Acceptance

1. `QUANTA_HISTORY_BACKFILL_TARGET_START_BIZ_DATE=auto` 时，scheduler 会优先使用 recommendation，而不是继续把 `target_open_days` 当成唯一依据。
2. 如果 recommendation 为空，scheduler 会回退到 `QUANTA_HISTORY_BACKFILL_TARGET_OPEN_DAYS`。
3. `/api/v1/runtime` 会返回 `resolved_history_backfill_target_start_biz_date`。
4. `scripts/market_data_backfill_smoke.py` 会覆盖 `auto` recommendation 与 fallback 语义。

## Tasks

- [x] 接入 scheduler `target_start_biz_date=auto`
- [x] 接入 runtime resolved target 可见性
- [x] 补 fake Tushare smoke 覆盖 `auto` recommendation / fallback

## Notes

1. 这一步的目标是“最小自动收敛”，不是把更深历史窗口策略一次性做完。
2. `auto` 依赖最新 READY snapshot 的 `history_coverage` recommendation，因此它天然是发布态驱动的，不会越过当前 snapshot 语义直接猜未来状态。
