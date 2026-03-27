# M2 Analysis Artifacts Progress

## Current State

QuantA 已在 DuckDB foundation 上落地最小分析产物层：`indicator_daily`、`pattern_signal_daily`、`capital_feature_daily` 都可以由 seeded `price_series_daily` 生成，并通过 per-stock as-of API 读取。

## Last Completed

1. 为 `indicator_daily`、`pattern_signal_daily`、`capital_feature_daily` 增加 schema。
2. 增加分析产物 bootstrap，从 `price_series_daily` 生成指标、形态信号和资金特征。
3. 增加 `/api/v1/stocks/{symbol}/indicators` 与 `/api/v1/stocks/{symbol}/capital-flow`。
4. 把分析产物状态和 API 校验接进 `init_dev.sh`、`scripts/smoke.sh` 和 app smoke。

## Verification

1. `python3 -m backend.app.domains.analysis.bootstrap --print-summary`
2. `scripts/init_dev.sh`
3. `scripts/smoke.sh`
4. `pnpm run backend:dev`
5. `pnpm run frontend:dev`

## Next Step

基于当前 analysis artifacts 推进 M3：实现真实的 hard filter、候选策略池、打分排序和 `screener_run/screener_result` 生成，让 dashboard 不再消费 seed 出来的选股结果。
