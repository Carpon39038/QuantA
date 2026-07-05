# M3 Screener Engine

## Goal

在 QuantA 的分析产物层之上落地最小 v1.0 选股引擎，让 `screener_run`、`screener_result` 和独立 screener API 由 DuckDB 真数据驱动，而不是继续消费 seed 出来的静态结果。

## Scope

本计划聚焦：

1. 基于 `indicator_daily`、`pattern_signal_daily`、`capital_feature_daily` 实现 hard filter、候选策略池和排序分数
2. 把 `screener_result` 扩成可解释的分数字段
3. 增加 screener bootstrap，为每个 READY snapshot 生成 `screener_run` / `screener_result`
4. 提供 `GET /api/v1/screener/runs/latest`、`GET /api/v1/screener/runs/{run_id}` 与 `GET /api/v1/screener/runs/{run_id}/results`
5. 把 screener 状态接进 init/smoke，并把查询侧连接改成显式只读

## Non-Goals

本计划不包含：

1. 接入真实财务质量、ST/退市过滤等完整基本面规则
2. 提供 `POST /api/v1/screener/runs` 手动触发接口
3. 引入多策略并行调度或行业中性约束
4. 完成浏览器级 UI 录制和比对

## Done When

1. 至少 3 个基础候选策略可在 READY snapshot 上生成结果。
2. 每条候选结果都包含命中规则、风险标签和分项得分。
3. `latest snapshot` 不再读取 seed 出来的 screener rows，而是读取 M3 bootstrap 生成的结果。
4. 前后端都能通过 dedicated screener API 读取最新 run 与结果列表。
5. query repo 使用 DuckDB 只读连接，不再在读取时重算 analysis/screener 产物。

## Verify By

1. `python3 -m backend.app.domains.screener.bootstrap --print-summary`
2. `scripts/init_dev.sh`
3. `scripts/smoke.sh`
4. `pnpm run backend:dev`
5. `pnpm run frontend:dev`

## Tasks

- [x] 扩展 `screener_result` schema，补齐趋势/量价/资金/过滤分
- [x] 增加 deterministic screener bootstrap
- [x] 落地 `趋势突破`、`放量启动`、`资金共振` 三类最小候选策略
- [x] 提供 dedicated screener run/results API
- [x] 把 screener 状态接进 init/smoke 和 app smoke
- [x] 把 query-side DuckDB 读路径切到显式只读连接
- [ ] 接真实财务过滤、行业约束和手动触发入口

## Decisions

1. M3 先用 deterministic analysis artifacts 驱动选股，不等待真实财务源。
2. 候选策略先做“可验证的三策略骨架”，把复杂策略搜索留到后续迭代。
3. 选股解释先落在 `matched_rules_json`、`risk_flags_json` 和分项得分，不提前设计复杂 explainability DSL。
4. 为避免 DuckDB 锁冲突和查询副作用，bootstrap 前移到 init/dev server startup，repo 查询改成只读连接。

## Status

当前状态：M3 最小选股引擎已落地，含三策略候选池、分项得分、可解释结果和 dedicated screener API；下一步进入 M4/M5，继续把回测请求、回测明细与最小任务/手动触发链补齐。
