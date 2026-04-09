# Quality Score

当前分数采用 `0-4`：

1. `0`
   尚未建立。
2. `1`
   有方向或文档，但无实现。
3. `2`
   有最小实现，可演示。
4. `3`
   稳定可用，有验证。
5. `4`
   可持续扩展，有自动化护栏。

## Current Baseline

| Area | Score | Notes |
| --- | --- | --- |
| 产品范围定义 | 3 | `mydoc/` 已有较完整的范围文档 |
| 数据模型设计 | 3 | 快照语义明确，且已落最小 v1.0 DuckDB DDL、生成态 schema 快照、as-of、选股/回测表结构，以及 `fundamental_feature_daily` 财务 sidecar |
| 仓库级 harness | 2 | 已建立入口、计划与约束，但缺 CI 和自动清理 |
| 执行 harness | 3 | 已有 acceptance、progress、init、smoke、pipeline smoke，且能稳定跑 source-backed sync、retry/backoff 和 backend/frontend app smoke |
| 后端代码骨架 | 3 | 已有最小 dev server、DuckDB/bootstrap、source-backed sync、Tushare canonical provider、只读查询路径、stock as-of API、screener/backtest detail API、更大 source universe manifest、canonical quality checks、企业行为 sidecar / reconciliation、history coverage targeting 与多字段 shadow validation 暴露 |
| 前端代码骨架 | 3 | workbench 已读取 latest snapshot、stock detail、screener 和 backtest detail API，并开始展示研究池、补充校验、企业行为、provider incident 摘要、最近 alerts 与建议的下一次历史回补起点，但还未拆成独立页面路由 |
| 任务编排 | 4 | 已有 queue-backed GET/POST tasking/service 面、阶段化 `daily_sync -> daily_screener -> daily_backtest`、retry/backoff、resident scheduler、worker 消费、lookback 与 target-start-date 双语义的 history_backfill，以及 pipeline smoke 覆盖 |
| 可观测性 | 3 | 已有 health、runtime、task runs、task status、alert_count、`/api/v1/system/alerts`、`alert_summary`、`history_coverage`、推荐的 next target start date 与 runtime-local alerts JSONL，且 source sync 会把 provider degradation / canonical quality warning 写入告警，前端也会展示 provider incidents、最近 alerts 和下一次建议补数起点，但还没有远端通知与结构化 tracing |
| 测试与结构校验 | 3 | 已有 repo/execution harness 校验、pipeline smoke、Tushare provider/live smoke 与 backend/frontend smoke，覆盖 latest snapshot、stock detail、screener、backtest、retry 路径、更大研究池配置、字段级 shadow validation、企业行为 reconciliation、lookback 与 target-start-date backfill 收敛，以及前端详情壳子 |

## Upgrade Rule

只有当约束被编码为脚本、测试、lint 或稳定接口时，质量分才能真正提高。仅靠“大家都知道”不算升级。
