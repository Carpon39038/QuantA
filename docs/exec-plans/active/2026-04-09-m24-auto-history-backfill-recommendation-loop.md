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

## Done When

1. `target_start_biz_date=auto` 已能由 scheduler 消费最新 READY snapshot 的 `history_coverage.recommended_target_start_biz_date`。
2. recommendation 缺失时，scheduler 会退回到 `QUANTA_HISTORY_BACKFILL_TARGET_OPEN_DAYS`，不会停止历史回补。
3. runtime API 能展示已解析出的 auto target，便于盘后运维确认当前追深窗口。
4. live daemon 观察结果和旧 raw snapshot refresh 遗留问题已经写入 progress 或 tech debt。

## Verify By

1. `python3 scripts/market_data_backfill_smoke.py`
2. `python3 scripts/app_smoke.py`
3. `scripts/smoke.sh`
4. `python3 scripts/check_execution_harness.py --require-all-passing`

## Tasks

- [x] 接入 scheduler `target_start_biz_date=auto`
- [x] 接入 runtime resolved target 可见性
- [x] 补 fake Tushare smoke 覆盖 `auto` recommendation / fallback

## Notes

1. 这一步的目标是“最小自动收敛”，不是把更深历史窗口策略一次性做完。
2. `auto` 依赖最新 READY snapshot 的 `history_coverage` recommendation，因此它天然是发布态驱动的，不会越过当前 snapshot 语义直接猜未来状态。

## Status

当前状态：M24 的最小自动收敛能力已完成并通过 smoke；该计划仍留在 `active/`，用于跟踪 live daemon 后续自动追深观察，以及正式库旧 raw snapshot 缺少 `adj_factor_overrides` watermark 的可审计 refresh / reingest 口径。
