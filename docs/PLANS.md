# Planning Rules

## Why Plans Matter

大任务不能只靠一次对话上下文推进。执行计划是 QuantA 的长期记忆和交接界面。

## When To Create A Plan

满足任一条件时，应该写到 `docs/exec-plans/`：

1. 会跨多个提交或多个模块。
2. 需要记录取舍、假设或阶段性决策。
3. 未来其他智能体可能接手。
4. 用户验收标准不是一句话能说清。

## Plan Layout

1. `active/`
   正在推进或仍有后续动作的计划。
2. `completed/`
   已交付、仅供回溯的计划。
3. `tech-debt-tracker.md`
   不中断当前主线但必须持续跟踪的问题。

## Plan Requirements

每份计划至少包含：

1. 目标
2. 范围与非目标
3. 里程碑或任务清单
4. 决策日志
5. 当前状态
6. `Done When`
7. `Verify By`

## Lightweight Rule

小改动不必强制建计划，但一旦发现任务正在扩大，就应及时补计划，而不是继续把上下文留在对话里。

## Long-Running Rule

如果任务预计会跨多轮会话或希望 agent 尽量少停下来问人，除了 plan 之外再补两份伴生工件：

1. `*.acceptance.json`
   用机器可读条目定义本阶段还剩什么、每项怎么验收、当前是否 `passes=true`。
2. `*.progress.md`
   作为交接物，至少记录当前状态、刚完成的事、已做验证、下一步第一动作。

长期执行时，默认顺序是：

1. 先读 plan、`acceptance`、`progress`
2. 再跑初始化与 smoke
3. 然后只做一个可验证的小步
4. 如果需要活服务，再启动 backend/frontend dev server，而不是跳过 smoke 直接开发
