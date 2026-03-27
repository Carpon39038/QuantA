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
| 数据模型设计 | 3 | 快照语义明确，且已落第一版 DuckDB DDL 与生成态 schema 快照 |
| 仓库级 harness | 2 | 已建立入口、计划与约束，但缺 CI 和自动清理 |
| 执行 harness | 3 | 已有 acceptance、progress、init、smoke，且能跑 DuckDB-backed app smoke |
| 后端代码骨架 | 3 | 已有最小 dev server、DuckDB bootstrap、latest snapshot API 与 runtime bootstrap |
| 前端代码骨架 | 2 | 已有最小 workbench shell、dev server 与 API proxy，当前消费 DuckDB-backed latest snapshot |
| 任务编排 | 0 | 尚未实现 |
| 可观测性 | 0 | 尚未实现 |
| 测试与结构校验 | 2 | 已有 repo/execution harness 校验与 backend/frontend smoke 入口 |

## Upgrade Rule

只有当约束被编码为脚本、测试、lint 或稳定接口时，质量分才能真正提高。仅靠“大家都知道”不算升级。
