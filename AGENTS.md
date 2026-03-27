# QuantA Agent Guide

## Purpose

这个文件只做入口地图，不做百科全书。

QuantA 当前处于绿地阶段，目标是先跑通一套可复现的 A 股盘后研究闭环：

1. 盘后更新数据。
2. 生成分析产物与选股结果。
3. 在真实约束下完成回测。
4. 通过 API 和 Web 稳定展示已发布快照。

## Read This First

遇到任务时，按下面顺序建立上下文：

1. [ARCHITECTURE.md](/Users/carpon/web/QuantA/ARCHITECTURE.md)
2. [docs/HARNESS.md](/Users/carpon/web/QuantA/docs/HARNESS.md)
3. [docs/PLANS.md](/Users/carpon/web/QuantA/docs/PLANS.md)
4. [docs/product-specs/index.md](/Users/carpon/web/QuantA/docs/product-specs/index.md)
5. [docs/exec-plans/active/2026-03-27-m0-harness-bootstrap.md](/Users/carpon/web/QuantA/docs/exec-plans/active/2026-03-27-m0-harness-bootstrap.md)

如果任务涉及某个特定领域，再补读：

1. 数据与快照：`ARCHITECTURE.md`、`docs/generated/db-schema.md`、`docs/RELIABILITY.md`
2. 产品范围：`docs/product-specs/index.md`
3. UI 与展示：`docs/FRONTEND.md`、`docs/DESIGN.md`
4. 质量与长期维护：`docs/QUALITY_SCORE.md`、`docs/exec-plans/tech-debt-tracker.md`

## System Of Record

对智能体而言，看不见的东西等于不存在。

以下内容才算项目事实来源：

1. 代码仓库中的代码、脚本、测试、Markdown 和生成产物。
2. 版本化的执行计划和技术债记录。
3. 可复现的命令、数据口径和快照语义。

以下内容不能只停留在聊天或脑中：

1. 领域术语定义。
2. 数据口径和回测约束。
3. 关键架构决策。
4. 新增的工程规范。

## Repo Map

1. `mydoc/`
   现有中文需求、架构和实施文档。把它视为当前业务输入源，不要随意删除。
2. `docs/`
   面向智能体和工程协作的系统记录层。
3. `backend/app/`
   未来后端主代码目录，采用固定分层。
4. `frontend/src/`
   未来前端主代码目录，按页面能力和数据视图拆分。
5. `scripts/check_harness_docs.py`
   最小文档校验脚本。

## Working Rules

1. 先改系统，再改提示。
   如果智能体反复在同一类问题上出错，优先补文档、脚本、测试或结构约束。
2. 术语必须精确。
   `raw_snapshot_id` 是原始数据快照，`snapshot_id` 是产物发布快照，不能混用。
3. 边界先校验，再传播。
   外部数据源进入系统时先标准化与校验，内部模块尽量消费明确结构。
4. 优先保留可复现性。
   涉及选股、分析、回测的结果必须能追溯到数据快照和策略版本。
5. 单写者优先。
   盘后任务负责写入，查询侧默认只读已发布快照。
6. 先补文档入口，再扩实现细节。
   新增模块时，至少把入口写进相应 `docs/` 索引或计划里。
7. lint 只跑本次改动文件。
   TypeScript 或 TSX 使用 `pnpm exec eslint <changed-files> --cache --ext .ts,.tsx`。

## Definition Of Done

一次有价值的改动通常同时满足：

1. 代码或文档改动本身可读。
2. 影响到的约束、计划或口径被记录到仓库。
3. 至少完成必要的本地验证。
4. 后续智能体可以仅靠仓库上下文继续推进。
