# Tech Debt Tracker

| ID | Area | Debt | Impact | Next Step |
| --- | --- | --- | --- | --- |
| TD-001 | Repo | DuckDB-backed dev 闭环已覆盖 latest snapshot、as-of、analysis、screener、backtest 和 queue-backed service/POST 触发，但真实同步数据源和自动盘后编排仍未接入 | 当前已能稳定开发与验证最小研究闭环，但真实盘后运行链仍未打通 | 继续推进真实同步、调度器和更真实的状态传播 |
| TD-002 | Data | 最小 v1.0 DDL 已落地，但 benchmark 历史、真实财务过滤和更完整任务/请求状态仍有缺口 | 数据层现在可支撑开发 workbench，但真实研究与运维约束仍不够全 | 继续按里程碑补齐 benchmark/财务/任务状态相关表与口径 |
| TD-003 | Reliability | 任务状态、durable request 和 worker 消费已可展示，但失败告警、重试和真正的串行调度未实现 | 盘后链路仍不可安全运维 | 在后续里程碑补 scheduler、失败状态传播和重试/告警 |
| TD-004 | Quality | 文档校验与 smoke 未接入 CI | 结构可能随时间失效 | 后续补最小 CI job |
| TD-005 | Testing | app-level smoke 已覆盖 stock/screener/backtest detail，但仍缺单元测试和浏览器级断言 | 页面和回测结构已有回归保护，但复杂逻辑仍主要靠集成 smoke 兜底 | 后续补 bootstrap/repo 单测和浏览器级 UI smoke |
| TD-006 | Execution Harness | execution harness 已托住多里程碑开发，但 active/completed plan 归档和 CI 自动门禁还没落地 | 长任务虽可连续推进，但历史计划会逐渐累积在 `active/` 下 | 后续补 completed 归档和最小 CI gate，并把 app-level smoke 接进持续门禁 |
