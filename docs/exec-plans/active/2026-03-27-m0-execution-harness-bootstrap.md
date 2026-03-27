# M0 Execution Harness Bootstrap

## Goal

为 QuantA 落一套最小 execution harness，让 agent 在多轮会话中可以按同一顺序开工、交接和验收，而不是只靠对话记忆。

## Scope

本计划聚焦：

1. 增加 machine-readable acceptance 文件
2. 增加 progress handoff 文件
3. 增加 `scripts/init_dev.sh`
4. 增加 `scripts/smoke.sh`
5. 增加最小 backend/frontend 可启动骨架
6. 把这套工作流写回 `docs/`

## Non-Goals

本计划不包含：

1. 落地真实 DuckDB 或真实任务队列
2. 接入 Playwright、浏览器录制或多 agent 编排
3. 落地任务运行时的数据库 run log
4. 代替未来的 runtime harness

## Done When

1. 新 agent 能仅靠 plan、acceptance、progress 明白当前状态和下一步。
2. `scripts/init_dev.sh` 能无副作用地检查环境并打印当前 acceptance 摘要。
3. `scripts/smoke.sh` 能验证 repo harness、execution harness，以及最小 backend/frontend app smoke。
4. 后端和前端都存在明确 dev 启动命令，并能在 fixture-backed 模式下返回稳定结果。
5. `python3 scripts/check_execution_harness.py --require-all-passing` 能作为本阶段完成门禁。

## Verify By

1. `python3 scripts/check_harness_docs.py`
2. `python3 scripts/check_execution_harness.py --print-summary`
3. `python3 scripts/check_execution_harness.py --require-all-passing`
4. `scripts/init_dev.sh`
5. `scripts/smoke.sh`
6. `pnpm run backend:dev`
7. `pnpm run frontend:dev`

## Tasks

- [x] 设计 execution harness 的最小工件集合
- [x] 落地 acceptance JSON 与 progress handoff
- [x] 落地 `scripts/init_dev.sh` 与 `scripts/smoke.sh`
- [x] 落地最小 backend/frontend fixture-backed 骨架
- [x] 增加 `scripts/check_execution_harness.py`
- [x] 把工作流写回 `docs/HARNESS.md` 与 `docs/PLANS.md`
- [x] 把 app-level smoke 接进真实服务、fixture 和 API/UI 校验
- [ ] 把 fixture-backed skeleton 替换成真实 DuckDB、任务状态和浏览器级 smoke

## Decisions

1. 先做最小 execution harness，不直接引入 runtime harness。
2. 验收条目先用 JSON 存放，方便后续脚本读取和门禁。
3. `smoke.sh` 只做结构 smoke；“全部通过”由 `check_execution_harness.py --require-all-passing` 承担。
4. progress handoff 继续用 Markdown，保持人类和 agent 都容易编辑。
5. app-level smoke 先走“后端 dev server + 前端 proxy + fixture snapshot”的最小链路，避免过早引入重依赖。

## Status

当前状态：最小 execution harness 与 fixture-backed app skeleton 已落地，可用于长时间开发任务的启动、交接、启动验证和完成门禁；下一步是把真实 DuckDB 与任务链替换进这条 smoke 链。
