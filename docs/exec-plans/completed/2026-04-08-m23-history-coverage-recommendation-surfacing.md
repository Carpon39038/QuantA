# M23 History Coverage Recommendation Surfacing

## Goal

把 QuantA 从“能在终端里看出下一次该补到哪天”继续推进到“系统自己也能把建议的下一次历史回补起点暴露给 operator”，让 `/api/v1/system/health` 与 workbench 都能直接给出 actionable next step。

## Scope

1. 从最新 READY snapshot 的 `corporate_action` reconciliation 结果里推导 `recommended_target_start_biz_date`。
2. 区分两类推荐原因：
   - `resolve_boundary_gap`
   - `extend_to_next_out_of_coverage`
3. 在 `/api/v1/system/health` 的 `history_coverage` 中暴露：
   - `recommended_target_start_biz_date`
   - `recommendation_reason`
   - `recommendation_anchor_biz_date`
4. 在 workbench 状态区与告警摘要里展示该建议，让 operator 不必再手工读 raw JSON 或终端输出。

## Non-Goals

1. 本里程碑不自动执行下一次深历史回补。
2. 本里程碑不引入新的通知渠道。
3. 本里程碑不改变 canonical 数据口径。

## Acceptance

1. `/api/v1/system/health` 会返回推荐的下一次 `target_start_biz_date`。
2. 当 `corporate_action` 存在 `boundary_gap` 时，推荐会回退到当前 coverage 起点之前的上一个 open day。
3. 当 `corporate_action` 只剩 `out_of_coverage` 时，推荐会回退到最近未覆盖事件日之前的上一个 open day。
4. workbench 会显示当前历史覆盖和建议的下一次回补起点。

## Tasks

- [x] 在 repo health 读路径里增加 history coverage recommendation
- [x] 在前端状态区与告警摘要中显示 recommendation
- [x] 补系统记录，说明 next target recommendation 的语义与限制

## Notes

1. 这一步的目标是把“下一步建议”从人工推断变成系统显式输出，而不是立即做自动化闭环。
2. recommendation 依赖最新 READY snapshot 中的 `corporate_action` reconciliation 结果，因此它本身也是 snapshot-bound 的，只反映当前发布态的已知缺口。
