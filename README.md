# QuantA

QuantA 是一个面向 A 股盘后研究的 `snapshot-first` 工作台。

当前 v1.0 的主目标不是做成“大而全量化平台”，而是先把这条闭环稳定跑通：

`日线数据 -> 盘后分析 -> 选股 -> 回测 -> 展示`

仓库当前已经具备：

1. DuckDB-backed 数据底座与 as-of 读取路径
2. `daily_sync -> daily_screener -> daily_backtest` 的阶段化流水线
3. `BUILDING -> READY` 的发布门禁
4. queue、retry/backoff、alerts 和 resident scheduler
5. 本机 backend/frontend workbench
6. `Tushare Pro 5000积分档 + 巨潮资讯/上交所/深交所 + AKShare/BaoStock补充层` 的正式数据源口径

## 当前定位

QuantA 目前默认是盘后研究系统，不是盘中实时行情终端。

1. workbench 默认只读取最新 `READY snapshot`
2. 盘中未收盘数据不会直接混入正式回测与发布链
3. 白天如果 source 还没有当天日线，页面通常会显示最近一个已完成盘后发布的 `biz_date`

“盘中预览层”的需求和方案概述已经单独记录在：
[盘中预览层](docs/product-specs/intraday-preview-layer.md)

## 快速开始

### 本地开发

```bash
scripts/init_dev.sh
scripts/smoke.sh
pnpm run backend:dev
pnpm run frontend:dev
pnpm run pipeline:once
```

默认开发端口：

1. backend: `http://127.0.0.1:8765`
2. frontend: `http://127.0.0.1:4173`

### 常驻调度

```bash
pnpm run pipeline:daemon
pnpm run ops:doctor
pnpm run ops:after-close
```

如果要装本机 live runtime，入口见：

1. [docs/OPERATIONS.md](docs/OPERATIONS.md)
2. [ops/live.env.example](ops/live.env.example)
3. [ops/launchd/README.md](ops/launchd/README.md)

`ops/live.env.example` 默认使用较少冲突的高位端口：

1. backend: `18765`
2. frontend: `24173`

## 先看这些文档

如果你刚进入仓库，推荐按这个顺序建立上下文：

1. [ARCHITECTURE.md](ARCHITECTURE.md)
2. [docs/HARNESS.md](docs/HARNESS.md)
3. [docs/PLANS.md](docs/PLANS.md)
4. [docs/product-specs/index.md](docs/product-specs/index.md)
5. [backend/app/README.md](backend/app/README.md)
6. [docs/OPERATIONS.md](docs/OPERATIONS.md)

如果你是 agent，还应该看：

1. [AGENTS.md](AGENTS.md)

## 核心语义

有几条语义要先分清：

1. `raw_snapshot_id`
   外部 source 进入系统后的原始数据快照
2. `snapshot_id`
   经过分析、选股、回测后可供 API 和前端读取的发布快照
3. `READY snapshot`
   查询侧默认只读的最终发布态
4. `BUILDING snapshot`
   已开始构建但还不能被正式读取的中间态

## 仓库结构

```text
backend/     后端主代码、providers、tasking、API
frontend/    workbench 前端
docs/        计划、约束、运维、产品 spec、技术记录
mydoc/       现有中文需求/架构/实施输入源
scripts/     init、smoke、doctor、live smoke、校验脚本
ops/         launchd 和 live env 模板
data/        本地运行时数据目录（已 gitignore）
```

## 当前状态

截至当前仓库状态，QuantA 已经能：

1. 用 fixture 稳定开发
2. 用 Tushare live token 跑真实 canonical sync
3. 自动推进历史回补、analysis、screener、backtest 和发布
4. 用 workbench 查看最新 `READY snapshot`
5. 在本机以 launchd / daemon 方式常驻运行

仍未纳入当前默认正式链的能力包括：

1. 盘中实时预览层
2. 分钟级历史
3. Level-1 / Level-2 授权行情
4. 更深的企业行为和更长窗口回补运维优化

## 常用入口

```bash
python3 -m backend.app.domains.tasking.bootstrap
python3 -m backend.app.api.dev_server
pnpm run backend:dev
pnpm run frontend:dev
pnpm run pipeline:once
pnpm run pipeline:daemon
pnpm run ops:doctor
pnpm run ops:after-close
```

更细的 backend 入口、provider 说明和 live sync 口径见：
[backend/app/README.md](backend/app/README.md)
