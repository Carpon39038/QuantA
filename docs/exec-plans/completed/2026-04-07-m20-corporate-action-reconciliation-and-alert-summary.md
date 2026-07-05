# M20 Corporate Action Reconciliation And Alert Summary

## Goal

把 QuantA 从“企业行为 sidecar 已可读、alerts 已可见”继续推进到“企业行为会做长期一致性自检，alerts 有摘要可消费”，让可用初版更接近日常值守状态。

## Scope

1. 在 sync 发布链里新增 `corporate_action` reconciliation check，并合并进 `shadow_validation.canonical_checks`。
2. reconciliation 需要基于 `price_series_daily` 历史 `adj_factor` 与 `corporate_action_item` 的 `ex_date/trade_date` 做覆盖内对齐判断。
3. 对超出当前价格历史覆盖范围的企业行为，明确标成 `SKIPPED/out_of_coverage`，不要误报成 canonical 数据错误。
4. 为 `/api/v1/system/health` 与 `/api/v1/system/alerts` 增加 alert summary，聚合 severity、type 和 provider incidents。
5. workbench 直接消费 alert summary，显示 provider incidents 与告警摘要。
6. 把 fake backfill smoke 补到会覆盖 corporate action reconciliation 的程度。

## Non-Goals

1. 本里程碑不做外部通知通道。
2. 本里程碑不做全量长期企业行为回补或跨源企业行为对账。
3. 本里程碑不强制当前 live 研究池历史窗口就覆盖到企业行为实施日。

## Acceptance

1. `shadow_validation.canonical_checks` 包含 `corporate_action`，且 fixture/tushare 两条路径都不会把覆盖外企业行为误判成坏数据。
2. `scripts/market_data_backfill_smoke.py` 会显式覆盖一条 in-coverage corporate action reconciliation 成功路径。
3. `/api/v1/system/health` 与 `/api/v1/system/alerts` 会返回 `alert_summary`。
4. workbench 会在最近 alerts 区块展示 provider incident 摘要，而不只是原始 alerts 列表。
5. 2026-04-07 的 live `tushare` sync 会暴露 `corporate_action` canonical check 与 alert summary。

## Tasks

- [x] 在 sync 中补 corporate action reconciliation check
- [x] 把 corporate action check 合并回 raw snapshot `source_watermark_json`
- [x] 为 health / alerts 增加 alert summary
- [x] 更新 workbench 呈现 provider incident 摘要
- [x] 扩充 fake backfill smoke 覆盖 reconciliation
- [x] 通过默认 smoke 与 live Tushare 验证

## Notes

1. 当前 `corporate_action` reconciliation 的判断边界是“事件日落在当前 `price_series_daily` 覆盖范围内时，前后 `adj_factor` 应发生变化”；超出覆盖范围的企业行为只记为 `out_of_coverage`。
2. 这一步解决的是“不要无声失真”，不是“企业行为历史已经全量补完”。
