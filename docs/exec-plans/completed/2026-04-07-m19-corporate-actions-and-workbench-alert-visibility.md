# M19 Corporate Actions And Workbench Alert Visibility

## Goal

把 QuantA 从“已有更深 canonical quality checks”继续推进到“企业行为解释层落地 + 告警在 workbench 可见”，让历史可信度和日常使用感更接近可用初版。

## Scope

1. 新增 `corporate_action_item` sidecar，并绑定到 `snapshot_id`。
2. 接入 `tushare.dividend`，抽取：
   - 分红送配
   - 股权登记日
   - 除权除息日
   - 派息日
3. 在写入前按 `knowledge_date <= biz_date` 做 as-of 过滤，避免未来企业行为信息泄漏进历史 snapshot。
4. 新增 stock corporate-actions API，并把企业行为纳入 stock snapshot 的 `available_series`。
5. 让 workbench 直接展示企业行为和最近 alerts，而不是只通过 `/api/v1/system/alerts` 和 JSONL 间接可见。

## Non-Goals

1. 本里程碑不做企业行为全量长期核对和复权基准修正。
2. 本里程碑不把 alerts 接到外部通知通道。
3. 本里程碑不引入公告正文抽取。

## Acceptance

1. DuckDB 中存在 `corporate_action_item`，默认 dev seed 能提供确定性的企业行为样本。
2. `GET /api/v1/stocks/{symbol}/corporate-actions` 可用，stock snapshot 的 `available_series` 包含 `corporate_action`。
3. `scripts/smoke.sh` 通过，且 app smoke 会覆盖 corporate-actions endpoint。
4. 2026-04-07 的 live `tushare` sync 在 `core_operating_40` 上能写出非零 `corporate_action_item`。
5. workbench 会直接显示最近 alerts 和企业行为列表。

## Tasks

- [x] 新增 `corporate_action_item` schema 与 dev seed
- [x] 接入 `tushare.dividend` corporate action provider
- [x] 新增 corporate-actions read path / API
- [x] 更新 workbench 展示企业行为与最近 alerts
- [x] 用默认 smoke 与 live sync 验证结果

## Notes

1. `corporate_action_item` 当前是“解释层 sidecar”，不是新的 canonical 日线源。
2. `dividend` 数据写入时会先按 `knowledge_date <= biz_date` 过滤，保持历史 snapshot 的可回放语义。
