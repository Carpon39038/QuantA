# M0 Execution Harness Progress

## Current State

最小 execution harness 已经稳定托住多里程碑演进：latest snapshot、stock as-of、analysis、screener、backtest 和前端 detail workbench 都已接到 DuckDB-backed dev foundation，`scripts/init_dev.sh` 与 `scripts/smoke.sh` 仍可作为长任务的固定入口。

## Last Completed

1. 把 repo harness 扩成最小 execution harness。
2. 给长期任务补了 machine-readable acceptance 条目。
3. 给新会话补了固定启动入口、backend/frontend dev server 和 app-level smoke 入口。
4. 把 fixture-backed published snapshot 接到最小后端和前端 workbench shell。
5. 把相关工作流写回 `docs/HARNESS.md`、`docs/PLANS.md`、`docs/QUALITY_SCORE.md`。
6. 把 latest snapshot runtime 读路径升级成 DuckDB-backed dev foundation，并沿 M1-M4 继续推进到 analysis、screener、backtest 和 detail workbench。

## Verification

1. `python3 scripts/check_harness_docs.py`
2. `python3 scripts/check_execution_harness.py --print-summary`
3. `python3 scripts/check_execution_harness.py --require-all-passing`
4. `scripts/init_dev.sh`
5. `scripts/smoke.sh`
6. `python3 scripts/app_smoke.py`

## Next Step

继续沿 M5 把手动触发、`tasks` API、本地 durable request queue 消费和更真实的任务状态链接进这套 foundation，并逐步把 smoke 提升到浏览器级 UI 验证。
