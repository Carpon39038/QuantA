# QuantA

QuantA 是一个面向 A 股的“盘后研究驱动盘中监控”工作台。

当前 v1.0 的主目标不是做成“大而全量化平台”，而是先把这条闭环稳定跑通：

`日线数据 -> 盘后分析 -> 选股 -> 回测 -> 监控计划 -> 盘中触发提醒`

仓库当前已经具备：

1. DuckDB-backed 数据底座与 as-of 读取路径
2. `daily_sync -> daily_screener -> daily_backtest` 的阶段化流水线
3. `BUILDING -> READY` 的发布门禁
4. queue、retry/backoff、alerts 和 resident scheduler
5. 本机 backend/frontend workbench
6. `Tushare Pro 5000积分档 + 巨潮资讯/上交所/深交所 + AKShare/BaoStock补充层` 的正式数据源口径

## 当前定位

QuantA 目前的产品定位是：盘后研究负责给出可复现的观察名单、买点、止盈和风控线，盘中监控负责把这些计划转成实时触发和提醒。

1. `READY snapshot` 是盘后研究和监控计划的事实来源。
2. 盘中预览行情用于判断计划是否触发，不直接混入正式回测与发布链。
3. 白天如果 source 还没有当天日线，正式研究视图仍显示最近一个已完成盘后发布的 `biz_date`；盘中状态走独立预览层。

盘中监控层的需求和方案概述记录在：
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
5. 手动把研究池内股票加入策略监控队列，并基于内置三策略查看 `BUY / WATCH / SELL`、买点、止盈位和风控线
6. 在盘中用 experimental 预览层轮询手动监控池，实时看盘中价、买点/止盈/风控/止损触发状态，并把提醒写入 alerts
7. 在本机以 launchd / daemon 方式常驻运行

仍未成熟或未纳入当前默认正式链的能力包括：

1. 正式授权实时行情源
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
