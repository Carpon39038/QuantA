# Tech Debt Tracker

| ID | Area | Debt | Impact | Next Step |
| --- | --- | --- | --- | --- |
| TD-001 | Repo | 当前后端与前端骨架仍是 fixture-backed demo | 启动链路已通，但真实业务实现仍未接入 | 继续把 DuckDB、任务状态和真实页面数据替换进骨架 |
| TD-002 | Data | `docs/generated/db-schema.md` 仍是规划态 | 数据层无法机械校对 | 生成 DuckDB DDL 后刷新 |
| TD-003 | Reliability | 任务日志和失败告警未实现 | 盘后链路不可运维 | 在 M3 前先落最小 run log |
| TD-004 | Quality | 文档校验与 smoke 未接入 CI | 结构可能随时间失效 | 后续补最小 CI job |
| TD-005 | Testing | 没有样例数据和结构测试 | 快照和回测约束难以验证 | M1-M2 增加 fixture 与结构测试 |
| TD-006 | Execution Harness | app-level smoke 仍是 fixture-backed startup check，未覆盖 DuckDB、真实任务链和浏览器级交互 | 长任务可以自动验证启动链，但还不能证明真实产品行为完全可用 | 后续把真实数据底座、任务链和浏览器级 UI smoke 接进 `scripts/smoke.sh` |
