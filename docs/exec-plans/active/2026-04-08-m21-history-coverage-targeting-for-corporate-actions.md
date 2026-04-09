# M21 History Coverage Targeting For Corporate Actions

## Goal

把 QuantA 从“支持手工历史回补”继续推进到“可以明确维护更长历史覆盖窗口”，让 `corporate_action` reconciliation 不再长期停留在 `SKIPPED/out_of_coverage`。

## Scope

1. 为 `market_data.sync` 增加 `--lookback-open-days`，按最新 source biz date 自动解析滚动回补窗口。
2. 为 `history_backfill` tasking / API / queue / worker 增加 `lookback_open_days` 语义。
3. 为 scheduler 增加可选的 `history_backfill_target_open_days`，在 source 已追平后仍可继续向更早历史扩覆盖。
4. 让 `/api/v1/system/health` 暴露最新 READY snapshot 的 `history_coverage`。
5. 强化 live backfill smoke，直接输出：
   - `lookback_open_days`
   - `history_coverage`
   - `corporate_action_check`
6. 补 `corporate_action` check 的 coverage 诊断字段，至少能看见最近仍未覆盖到的事件日期。

## Non-Goals

1. 本里程碑不强制默认开发环境总是开启深历史回补。
2. 本里程碑不承诺一次性把全部企业行为事件都拉进 coverage。
3. 本里程碑不做外部通知通道。

## Acceptance

1. `python3 -m backend.app.domains.market_data.sync --lookback-open-days N --print-summary` 可用。
2. `POST /api/v1/tasks/history-backfill/run` 支持 `lookback_open_days`。
3. scheduler 在 `QUANTA_HISTORY_BACKFILL_TARGET_OPEN_DAYS > 0` 时，会把“历史覆盖不足”当成未 settled 状态。
4. `/api/v1/system/health` 返回 `history_coverage`。
5. `scripts/tushare_live_backfill_smoke.py` 会输出 `corporate_action_check`，用于观察 `checked/aligned` 是否随窗口变长而提升。

## Tasks

- [x] 增加 source lookback window resolver
- [x] 接入 sync CLI lookback mode
- [x] 接入 history_backfill queue / worker / API lookback mode
- [x] 接入 scheduler coverage target
- [x] 暴露 history coverage 与 richer corporate_action diagnostics
- [x] 升级 live backfill smoke

## Notes

1. 默认 `QUANTA_HISTORY_BACKFILL_TARGET_OPEN_DAYS=0`，避免 fixture 开发链被强制拉长历史。
2. 这一步先解决“覆盖窗口怎么正式维护”，再继续解决“目标窗口应该设到多深”。 
