# QuantA Architecture Map

## Goal

QuantA 的首要目标不是一次性做成“大而全量化平台”，而是建立一套对智能体和人类都清晰的可演进结构，让我们先把 `日线数据 -> 盘后分析 -> 选股 -> 回测 -> 展示` 的闭环跑通。

## Architecture Shape

系统按三层来理解：

1. `repo harness`
   由 `AGENTS.md`、`docs/`、执行计划、校验脚本组成，负责让智能体知道“项目是什么、规则是什么、下一步去哪里看”。
2. `application architecture`
   由数据采集、标准化、存储、分析、选股、回测、API、前端组成，负责业务实现。
3. `runtime harness`
   未来如果要把智能体嵌入产品或后台任务，再引入线程、回合、审批、事件流等运行时能力。

当前仓库优先建设前两层。

## Planned Code Layout

```text
backend/
  app/
    domains/
      market_data/
      analysis/
      screener/
      backtest/
      tasking/
    shared/
      providers/
      telemetry/
      utils/
    app_wiring/
    api/

frontend/
  src/
    app/
    pages/
    features/
      market-overview/
      stock-detail/
      screener-results/
      backtest-report/
    shared/
```

## Domain Layering

后端默认采用固定依赖方向，减少架构漂移：

```text
Types -> Config -> Repo -> Service -> Runtime/API
                 ^
                 |
             Providers
```

约束：

1. `Types`
   领域对象、请求参数、枚举、口径定义。
2. `Config`
   领域配置、默认值、策略参数定义。
3. `Repo`
   DuckDB 读取、写入、as-of 查询封装。
4. `Service`
   业务编排，例如分析计算、选股评分、回测回放。
5. `Runtime/API`
   任务入口、FastAPI、CLI、调度器。
6. `Providers`
   连接外部世界的显式入口，例如 AKShare、腾讯行情、通知、日志、遥测。

## Core Data Flow

```mermaid
flowchart LR
    A["外部数据源"] --> B["标准化与质量校验"]
    B --> C["raw_snapshot_id"]
    C --> D["DuckDB as-of 读取层"]
    D --> E["分析产物"]
    D --> F["选股结果"]
    D --> G["回测结果"]
    E --> H["snapshot_id 发布"]
    F --> H
    G --> H
    H --> I["FastAPI / Web / 报告"]
```

## Non-Negotiable Invariants

1. 所有外部数据都要经过边界标准化。
2. 原始数据快照和发布快照分离。
3. 查询侧默认只读 `READY` 的 `snapshot_id`。
4. 回测记录同时绑定 `raw_snapshot_id` 和 `snapshot_id`。
5. 任务链路必须可重跑、可追踪、可解释。
6. 能写成规则的约束，尽量不要只写成口头偏好。

## Source Documents

当前业务设计以这些文档为准：

1. [A股分析系统需求路线图](/Users/carpon/web/QuantA/mydoc/A股分析系统需求路线图.md)
2. [A股分析系统架构设计](/Users/carpon/web/QuantA/mydoc/A股分析系统架构设计.md)
3. [A股分析系统实施文档](/Users/carpon/web/QuantA/mydoc/A股分析系统实施文档.md)

面向智能体的摘要、计划和约束则沉淀到 `docs/`。
