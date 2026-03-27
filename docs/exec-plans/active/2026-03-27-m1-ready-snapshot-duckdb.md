# M1 Ready Snapshot DuckDB Foundation

## Goal

把 QuantA 当前“最新 READY 快照”的开发读路径推进到本地 DuckDB 驱动的最小真实数据底座，并补上 `daily_bar`、`price_series_daily` 与最小 stock as-of 查询。

## Scope

本计划聚焦：

1. 落地第一版本地 DuckDB schema
2. 增加 deterministic dev bootstrap，把现有 fixture 导入 DuckDB
3. 让 backend latest snapshot API 从 DuckDB 组装 payload
4. 给 `daily_bar`、`price_series_daily` 增加两期快照 seed 和最小 as-of 查询
5. 把 schema 快照和开发流程写回仓库

## Non-Goals

本计划不包含：

1. 接入真实 AKShare 或其他外部数据源
2. 跑通全市场存量日线同步
3. 完成完整 as-of 历史查询接口与真实增量同步
4. 实现浏览器级 UI smoke

## Done When

1. 本地存在可重复初始化的 DuckDB dev foundation。
2. backend/frontend 的 latest snapshot 链路不再直接读取 JSON fixture，而是读取 DuckDB。
3. `daily_bar` 与 `price_series_daily` 已有最小两期快照 seed，可验证 as-of 修订语义。
4. backend 提供最小 stock snapshot / kline as-of 查询入口。
5. `docs/generated/db-schema.md` 不再是纯规划态，而是当前 landed DDL 的生成快照。
6. `scripts/init_dev.sh` 与 `scripts/smoke.sh` 能暴露 DuckDB foundation 的健康状态。

## Verify By

1. `python3 -m backend.app.domains.market_data.bootstrap --print-summary`
2. `python3 scripts/render_db_schema.py`
3. `scripts/init_dev.sh`
4. `scripts/smoke.sh`
5. `pnpm run backend:dev`
6. `pnpm run frontend:dev`

## Tasks

- [x] 定义最小可运行的 DuckDB schema
- [x] 增加 dev seed bootstrap
- [x] 让 backend latest snapshot API 读取 DuckDB
- [x] 为 `daily_bar` 与 `price_series_daily` 增加两期快照 seed
- [x] 提供最小 stock snapshot / kline as-of 查询
- [x] 刷新 schema 快照文档
- [x] 把 DuckDB foundation 接进 init/smoke
- [ ] 扩展到真实日线同步与更完整的 as-of 查询

## Decisions

1. 先把“最新 READY snapshot”读路径接到 DuckDB，再扩 full history as-of。
2. 当前仍保留 fixture 作为 deterministic seed source，但它只负责初始化，不再是 runtime 读取来源。
3. 用“两期快照 + 局部修订”的 dev seed 证明 as-of 语义，再接真实同步。
4. schema 先覆盖最小可运行集合和 M1 主路径所需表，不一次性发明完整 v1.0 全量表。

## Status

当前状态：第一版本地 DuckDB foundation 已落地，并已接入 latest snapshot 读路径、最小 `daily_bar` / `price_series_daily` 两期 seed 与 stock as-of 查询；下一步是接真实日线同步、更完整 as-of 和分析产物层。
