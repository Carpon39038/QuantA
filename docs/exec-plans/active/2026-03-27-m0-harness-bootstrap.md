# M0 Harness Bootstrap

## Goal

为 QuantA 建立一套最小可运行的 agent-first 仓库 harness，让后续工程实现不依赖一次性对话上下文。

## Scope

本计划聚焦：

1. 建立 `AGENTS.md`
2. 建立 `docs/` 系统记录层
3. 明确未来代码结构和依赖方向
4. 增加最小文档校验脚本

## Non-Goals

本计划不包含：

1. 实现 FastAPI 或前端应用
2. 落地 DuckDB DDL
3. 集成数据源
4. 实现运行时 App Server harness

## Tasks

- [x] 提炼现有 `mydoc/` 为仓库级地图
- [x] 建立根入口文档和领域约束
- [x] 建立计划、质量、可靠性、安全文档
- [x] 增加最小脚本校验关键文档存在
- [ ] 把代码骨架真正落到 `backend/` 与 `frontend/`
- [ ] 把文档校验接入后续 CI
- [ ] 生成第一版 DDL 并刷新 `docs/generated/db-schema.md`

## Decisions

1. 先做仓库级 harness，再做运行时 harness。
2. 不迁移 `mydoc/` 原文，先通过 `docs/product-specs/index.md` 建立入口。
3. 保持 `AGENTS.md` 短小，只做导航和硬约束。

## Status

当前状态：已完成第一轮仓库级 harness 落地，下一步进入代码骨架和 DDL 实现。
