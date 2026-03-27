# Tech Debt Tracker

| ID | Area | Debt | Impact | Next Step |
| --- | --- | --- | --- | --- |
| TD-001 | Repo | latest snapshot 链路已接到 DuckDB，但 full history、真实同步和任务编排仍未接入 | 开发支架已可承接真实数据底座，但真实盘后闭环仍未打通 | 继续接 `daily_bar`、`price_series_daily`、最小 as-of 查询和任务状态推进 |
| TD-002 | Data | 第一版 DDL 已落地，但仍不是 v1.0 全量 schema | 数据层已可机械校对最小 foundation，但完整分析/回测表仍有缺口 | 继续按里程碑补齐 `indicator_daily`、`pattern_signal_daily`、`backtest_trade` 等表 |
| TD-003 | Reliability | 任务日志和失败告警未实现 | 盘后链路不可运维 | 在 M3 前先落最小 run log |
| TD-004 | Quality | 文档校验与 smoke 未接入 CI | 结构可能随时间失效 | 后续补最小 CI job |
| TD-005 | Testing | 没有样例数据和结构测试 | 快照和回测约束难以验证 | M1-M2 增加 fixture 与结构测试 |
| TD-006 | Execution Harness | app-level smoke 已覆盖 DuckDB-backed startup check，但仍未覆盖真实任务链和浏览器级交互 | 长任务现在能验证 latest snapshot 数据底座和启动链，但还不能证明真实产品行为完全可用 | 后续把真实任务链和浏览器级 UI smoke 接进 `scripts/smoke.sh` |
