# M9 Tushare Canonical Provider

## Goal

把 `Tushare Pro 5000积分档` 真正接入 QuantA 的 provider 层与 source-backed sync 入口，让正式 canonical structured source 不再只停留在架构口径。

## Scope

本计划聚焦：

1. 为 `Tushare Pro` 增加 provider 配置、token 读取和最小调用封装。
2. 落地 `TushareMarketDataProvider`，覆盖当前 DuckDB foundation 已需要的结构化 market sync 字段映射。
3. 提供离线 provider smoke，验证 `Tushare -> MarketDataSnapshot` 的字段归一和快照语义。
4. 把 provider 能力与新的环境变量写回 README / `.env.example` / 计划记录。
5. 保持默认 `fixture_json` 开发链和现有 smoke 稳定通过。

## Non-Goals

本计划不包含：

1. 立刻完成完整的 `Tushare Pro` 全市场回补任务。
2. 在本轮内接完 `巨潮资讯`、`上交所`、`深交所` 的披露 adapter。
3. 实现分钟级、公告正文和盘中实时数据。
4. 在没有 token 的前提下强行做 live Tushare 验证。

## Done When

1. `source_provider=tushare` 时，runtime 能构造 `TushareMarketDataProvider` 并生成合法的 `MarketDataSnapshot`。
2. provider 至少映射 `stock_basic`、`trade_calendar`、`daily`、`daily_basic`、`stk_limit` 到当前 sync 需要的字段，并把 `moneyflow`、`top_list`、`moneyflow_hsgt` 落成当前可消费的资金侧 sidecar。
3. 仓库有离线 smoke 覆盖 Tushare provider 的字段归一逻辑，不依赖 live token。
4. 默认 `fixture_json` 的 `scripts/smoke.sh` 仍然通过。

## Verify By

1. `python3 scripts/tushare_provider_smoke.py`
2. `python3 scripts/check_harness_docs.py`
3. `python3 scripts/check_execution_harness.py --require-all-passing`
4. `scripts/smoke.sh`

## Tasks

- [x] 增加 Tushare settings/env 和 optional dependency 记录
- [x] 落地 `TushareMarketDataProvider`
- [x] 增加离线 `tushare_provider_smoke`
- [x] 把新的 provider 口径写回 README 和计划记录
- [x] 跑通 harness checks 和默认 smoke

## Decisions

1. M9 先实现当前 DuckDB foundation 真正消费到的 canonical sync 字段，不在第一刀强行覆盖全部 Tushare VIP 表。
2. live token 缺失不能阻塞 provider 结构落地；离线 smoke 先负责验证字段映射和快照语义。
3. 当前开发环境仍默认 `fixture_json`，`tushare` 作为显式可切换 provider 接入，避免在没有 token 的机器上破坏默认开发链。

## Status

当前状态：M9 第三阶段已完成。`TushareMarketDataProvider`、环境变量、离线 provider smoke、资金侧 sidecar 和最小 VIP 财务 sidecar 已全部通过；下一步进入 live token 验证与正式历史回补。
