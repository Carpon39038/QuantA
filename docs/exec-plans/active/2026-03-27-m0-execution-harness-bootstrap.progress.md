# M0 Execution Harness Progress

## Current State

最小 execution harness 和 fixture-backed app skeleton 已经落地：active plan、acceptance、progress、`scripts/init_dev.sh`、`scripts/smoke.sh`、backend dev server、frontend dev server 都已加入仓库，并且可以通过 smoke 启动验证。

## Last Completed

1. 把 repo harness 扩成最小 execution harness。
2. 给长期任务补了 machine-readable acceptance 条目。
3. 给新会话补了固定启动入口、backend/frontend dev server 和 app-level smoke 入口。
4. 把 fixture-backed published snapshot 接到最小后端和前端 workbench shell。
5. 把相关工作流写回 `docs/HARNESS.md`、`docs/PLANS.md`、`docs/QUALITY_SCORE.md`。

## Verification

1. `python3 scripts/check_harness_docs.py`
2. `python3 scripts/check_execution_harness.py --print-summary`
3. `python3 scripts/check_execution_harness.py --require-all-passing`
4. `scripts/init_dev.sh`
5. `scripts/smoke.sh`
6. `python3 scripts/app_smoke.py`

## Next Step

把 fixture-backed app skeleton 继续替换成真实 DuckDB、任务状态与浏览器级 UI smoke，让 acceptance 从“能启动并返回稳定样例”推进到“能验证真实产品行为”。
