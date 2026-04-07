# Tech Debt Tracker

| ID | Area | Debt | Impact | Next Step |
| --- | --- | --- | --- | --- |
| TD-001 | Repo | DuckDB-backed dev 闭环已覆盖 latest snapshot、as-of、analysis、screener、backtest、source-backed sync、最小历史回补、retry/backoff、alerts、resident scheduler、Tushare canonical provider 的离线 / live 主链、CNInfo 官方披露元数据 sidecar，以及 AKShare/BaoStock 补充校验；当前仍缺更完整的长期补数策略、更细的数据质量口径和更稳的 AKShare 链路 | 当前已能稳定开发与验证更大研究池下的最小研究闭环，也能跑真实 canonical sync、财务 sidecar、官方披露 metadata、多字段 shadow validation、隔离历史回补和基础调度 catch-up；离完整 v1.0 盘后生产运行仍差长期 backfill 运维策略、更细粒度数据质量规则，以及 AKShare 上游链路稳定性 | 继续补全长期 backfill 运维策略，再把 shadow validation 从当前七字段扩到复权因子/停牌/涨跌停等更细口径，并把 AKShare 的外部链路波动隔离成更清晰的降级与告警策略 |
| TD-002 | Data | 最小 v1.0 DDL 已落地，并新增 `fundamental_feature_daily` 财务 sidecar，但 benchmark 历史、原始财务事实表和更完整任务/请求状态仍有缺口 | 数据层现在可支撑开发 workbench，并开始消费 canonical 财务分，但真实研究与运维约束仍不够全 | 继续按里程碑补齐 benchmark/原始财务/任务状态相关表与口径 |
| TD-003 | Reliability | 任务状态、durable request、阶段化 worker、retry/backoff、alerts 和 resident scheduler 已落地，但仍缺远端通知、自动 supervisor、运行手册和更细粒度的失败分类 | 盘后链路已有最小可靠性护栏，但仍不算真正可运维 | 继续补告警下游、部署侧常驻守护和 source/provider 级故障分层 |
| TD-004 | Quality | 文档校验与 smoke 未接入 CI | 结构可能随时间失效 | 后续补最小 CI job |
| TD-005 | Testing | app-level smoke 与 pipeline smoke 已覆盖 stock/screener/backtest detail、source sync 和 retry 路径，但仍缺单元测试和浏览器级断言 | 页面和流水线结构已有回归保护，但复杂逻辑仍主要靠集成 smoke 兜底 | 后续补 bootstrap/repo 单测和浏览器级 UI smoke |
| TD-006 | Execution Harness | execution harness 已托住多里程碑开发，但 active/completed plan 归档和 CI 自动门禁还没落地 | 长任务虽可连续推进，但历史计划会逐渐累积在 `active/` 下 | 后续补 completed 归档和最小 CI gate，并把 app-level smoke 接进持续门禁 |
