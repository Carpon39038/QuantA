# M2 Analysis Artifacts

## Goal

在 QuantA 的 DuckDB foundation 上落地第一版分析产物层，让 `indicator_daily`、`pattern_signal_daily`、`capital_feature_daily` 可以被生成、存储并通过 as-of API 读取。

## Scope

本计划聚焦：

1. 落地 `indicator_daily`、`pattern_signal_daily`、`capital_feature_daily` schema
2. 增加分析产物 bootstrap，从 `price_series_daily` 生成日级指标、形态信号和资金特征
3. 增加 per-stock 分析读取 API
4. 把分析产物状态接进 init/smoke 和执行记录

## Non-Goals

本计划不包含：

1. 接入真实北向、龙虎榜或主力资金原始数据源
2. 完成全部 v1.0 指标体系或行业/基本面过滤
3. 实现批量全市场分析调度
4. 完成选股打分和回测请求编排

## Done When

1. `indicator_daily`、`pattern_signal_daily`、`capital_feature_daily` 已写入 DuckDB。
2. 任意股票可在指定 `snapshot_id` 下读到指标与资金特征结果。
3. `pattern_signal_daily` 支持同日多信号并存，并可通过 as-of 读取。
4. `scripts/init_dev.sh` 与 `scripts/smoke.sh` 会展示分析产物层状态。

## Verify By

1. `python3 -m backend.app.domains.analysis.bootstrap --print-summary`
2. `scripts/init_dev.sh`
3. `scripts/smoke.sh`
4. `pnpm run backend:dev`
5. `pnpm run frontend:dev`

## Tasks

- [x] 落地分析产物相关表结构
- [x] 增加分析产物 bootstrap
- [x] 增加 indicator / pattern / capital as-of 查询
- [x] 把分析产物状态接进 init/smoke 和 app smoke
- [ ] 接真实资金面原始数据与更完整的基本面过滤

## Decisions

1. M2 先从 `price_series_daily` 推导出 deterministic analysis artifacts，不等待真实资金面原始源接入。
2. `pattern_signal_daily` 先覆盖 `breakout_up`、`volume_expansion`、`pullback_low_volume` 三类基础信号。
3. 分析产物采用“重算并写入最小增量行”的 dev bootstrap 方式，先验证 schema 和 as-of 语义，再接真实任务调度。

## Status

当前状态：M2 最小分析产物层已落地，包含日级指标、同日多信号和资金特征的 DuckDB 写入与 as-of API；下一步进入 M3，把这些结果接成真实选股引擎与排序结果。
