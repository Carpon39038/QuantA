# QuantA Harness Plan

## What We Mean By Harness

在 QuantA 里，`harness` 不是单指一个进程或协议，而是三层支撑结构：

1. `repo harness`
   让智能体可以仅靠仓库上下文理解项目、约束和下一步动作。
2. `execution harness`
   让任务可以被可靠触发、重试、校验和追踪。
3. `runtime harness`
   如果未来要把智能体嵌入产品或 IDE，再引入线程、回合、审批和事件流。

## What We Are Building Now

当前阶段已经从纯 `repo harness` 推进到 `execution harness + runtime foundation`：

1. 后端、前端、DuckDB、tasking 和 app-level smoke 已经稳定可跑。
2. 当前最大风险已经从“上下文散落”转成“真实同步、失败恢复和日终编排口径不够硬”。
3. 所以现在一边继续维护仓库级入口，一边把真实 source sync、BUILDING -> READY 发布门禁、retry/backoff、告警和 resident scheduler 编进系统。

## QuantA MVP Harness

首版 harness 包含：

1. 短 `AGENTS.md`
   只做地图，避免把所有规则塞进一个超长文件。
2. `docs/` 作为系统记录层
   把产品、架构、计划、质量、可靠性和安全入口组织起来。
3. 活跃执行计划
   大任务必须能从仓库里看出目标、范围、决策和下一步。
4. 文档校验脚本
   最小化保证这套结构不会很快失效。
5. 未来代码结构地图
   在没有实现前，先把边界和依赖方向说清楚。

## Minimal Execution Harness

为了支持“长时间持续开发 + 自测 + 交接”，在运行时 harness 之前先补一层最小 execution harness：

1. active exec plan
   继续用 Markdown 说明目标、范围、任务和决策，但必须补 `Done When` 与 `Verify By`。
2. `acceptance` 文件
   用机器可读的 JSON 记录当前里程碑的验收条目、验证步骤和 `passes` 状态。
3. `progress` 文件
   每轮结束时写清当前状态、刚完成什么、验证了什么、下一轮第一步做什么。
4. `scripts/init_dev.sh`
   新一轮开始时先检查基础环境、仓库入口和 acceptance 摘要。
5. `scripts/smoke.sh`
   在改代码前先跑最小 smoke，先确保 harness 没漂移，再确保 backend/frontend 的 app-level smoke 还能通过。
6. `scripts/pipeline_smoke.py`
   对阶段化 pipeline、retry/backoff 和 scheduler resident 语义做额外的临时 runtime 验证。

## Long-Running Loop

推荐的长期开发循环：

1. 读取 active plan、`acceptance`、`progress`。
2. 运行 `scripts/init_dev.sh`。
3. 运行 `scripts/smoke.sh`。
4. 只领取一个清晰的子任务，完成后立刻验证。
5. 更新 `progress` 和对应 `acceptance` 条目。
6. 只有当 `python3 scripts/check_execution_harness.py --require-all-passing` 通过时，才宣称该里程碑完成。

## What We Are Explicitly Not Building Yet

现在不急着实现：

1. 产品内智能体会话系统。
2. App Server 客户端。
3. 浏览器驱动、录像回放、全量可观测性堆栈。
4. 多 worktree 自动调度。

这些能力更适合在下列场景再引入：

1. 后端与前端已经能稳定启动。
2. 盘后任务链路已经成型。
3. 我们希望让智能体直接验证 UI、任务和性能。

## Next Harness Milestones

1. M0
   完成仓库级 harness、代码骨架和初始化脚本。
2. M1
   用 DDL 和 as-of 查询实现“可读可查”的数据底座。
3. M2
   为分析产物建立 DuckDB-backed 结构和查询路径。
4. M3
   落地最小选股引擎、解释性结果和 dedicated screener API。
5. M4
   落地最小回测回放层和 dedicated backtest API。
6. M5
   为任务编排增加 run log、queue-backed POST 入口、worker 和可追踪验收。
7. M6
   把日终链路拆成 `daily_sync -> daily_screener -> daily_backtest` 的最小阶段化流水线。
8. M7
   把 source-backed sync、retry/backoff、失败告警和 resident scheduler 接进这条流水线。
9. M8
   用 `docs/OPERATIONS.md`、`pnpm run pipeline:daemon` 和 health / alerts / runtime API，收敛第一版无人值守运行口径。
10. M9
   当产品里需要 agent 能力时，再补运行时 harness。
