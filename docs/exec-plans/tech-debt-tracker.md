# Tech Debt Tracker

| ID | Area | Debt | Impact | Next Step |
| --- | --- | --- | --- | --- |
| TD-001 | Repo | DuckDB-backed dev 闭环已覆盖 latest snapshot、as-of、analysis、screener、backtest、source-backed sync、retry/backoff、alerts 和 resident scheduler，但按新方案仍缺 `Tushare Pro 2000` canonical provider、官方披露 adapter，以及 AKShare/BaoStock 的补充校验链 | 当前已能稳定开发与验证最小研究闭环，但离真实盘后生产运行仍差正式 canonical source 和披露源接入 | 继续把 `Tushare Pro 2000 + 官方披露源 + AKShare/BaoStock补充层` 实做到位，并补全量历史回补与外部环境检查 |
| TD-002 | Data | 最小 v1.0 DDL 已落地，但 benchmark 历史、真实财务过滤和更完整任务/请求状态仍有缺口 | 数据层现在可支撑开发 workbench，但真实研究与运维约束仍不够全 | 继续按里程碑补齐 benchmark/财务/任务状态相关表与口径 |
| TD-003 | Reliability | 任务状态、durable request、阶段化 worker、retry/backoff、alerts 和 resident scheduler 已落地，但仍缺远端通知、自动 supervisor、运行手册和更细粒度的失败分类 | 盘后链路已有最小可靠性护栏，但仍不算真正可运维 | 继续补告警下游、部署侧常驻守护和 source/provider 级故障分层 |
| TD-004 | Quality | 文档校验与 smoke 未接入 CI | 结构可能随时间失效 | 后续补最小 CI job |
| TD-005 | Testing | app-level smoke 与 pipeline smoke 已覆盖 stock/screener/backtest detail、source sync 和 retry 路径，但仍缺单元测试和浏览器级断言 | 页面和流水线结构已有回归保护，但复杂逻辑仍主要靠集成 smoke 兜底 | 后续补 bootstrap/repo 单测和浏览器级 UI smoke |
| TD-006 | Execution Harness | execution harness 已托住多里程碑开发，但 active/completed plan 归档和 CI 自动门禁还没落地 | 长任务虽可连续推进，但历史计划会逐渐累积在 `active/` 下 | 后续补 completed 归档和最小 CI gate，并把 app-level smoke 接进持续门禁 |
