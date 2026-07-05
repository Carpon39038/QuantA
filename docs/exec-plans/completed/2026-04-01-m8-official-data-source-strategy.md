# M8 Official Data Source Strategy

## Goal

把 QuantA 的“正式数据源”从宽泛的外部来源列表，收敛成可交付、可复现、可运维的 v1.0 canonical source stack。

## Scope

本计划聚焦：

1. 明确 v1.0 核心结构化盘后数据的 canonical source，并把默认能力约束在 `Tushare Pro 5000积分档`。
2. 明确公告、公开信息和披露类数据的 official source。
3. 明确 `AKShare` 在正式方案中的职责边界。
4. 明确哪些网页内部接口不能直接作为 canonical source。
5. 把新的数据源策略写回架构与 backend 入口文档。

## Non-Goals

本计划不包含：

1. 立刻完成所有新 source adapter 的实现。
2. 采购商业终端或签订正式授权合同。
3. 覆盖分钟级、Level-1、Level-2 的实时数据实施细节。
4. 推翻 `mydoc/` 中“AKShare 是正式来源之一”的既有业务输入。

## Done When

1. 仓库明确区分 `canonical structured source`、`official disclosure source`、`supplementary adapter source` 和 `future licensed realtime source`。
2. 仓库明确把 `Tushare Pro 5000积分档` 作为 v1.0 默认 canonical 能力基线，允许直接覆盖全市场季度财务过滤所需的 VIP 接口。
3. `AKShare/BaoStock` 在仓库记录里被定义为正式支持的数据采集适配器，但不再承担 v1.0 核心表的唯一 canonical source 责任。
4. 仓库明确排除无公开文档、授权边界不清的网页内部接口作为核心持久化表的 canonical source。
5. 后续 agent 只看仓库，就能知道应该优先接哪个源、哪个源只做补充、哪些功能需要降级实现。

## Verify By

1. `python3 scripts/check_harness_docs.py`
2. `python3 scripts/check_execution_harness.py --require-all-passing`

## Tasks

- [x] 回查 `mydoc/`、`ARCHITECTURE.md` 与当前实现中的数据源口径
- [x] 调研 `Tushare Pro`、`巨潮资讯`、`上交所`、`深交所`、`Choice` 的公开产品与文档边界
- [x] 定义 QuantA v1.0 的正式数据源分层策略
- [x] 把默认结构化能力收敛到 `Tushare Pro 5000积分档`
- [x] 把数据源分层和排除项写回架构文档
- [x] 把 backend 实施入口改写成新的 source strategy 口径

## Decisions

1. `Tushare Pro 5000积分档` 作为 v1.0 核心结构化盘后数据的 canonical source 基线，负责 `stock_basic`、`trade_calendar`、`daily_bar`、`adj_factor`、`daily_basic`、`stk_limit`、`moneyflow`、`top_list`、`moneyflow_hsgt`，以及全市场季度财务过滤所需的 `fina_indicator_vip`、`income_vip`、`balancesheet_vip`、`cashflow_vip`。
2. `巨潮资讯`、`上交所`、`深交所` 作为法定或官方披露/公开信息 source，负责公告、公开信息、披露日历和交易所公开统计。
3. `AKShare` 与 `BaoStock` 继续保留为正式支持的数据采集适配器，但在 v1.0 中承担补充、验证、缺口兜底和快速探索职责，不再单独定义核心持久化表的 canonical source。
4. 全市场季度财务 `*_vip` 接口重新回到 v1.0 默认前提；正式选股主链允许直接使用全市场季度财务过滤。
5. `腾讯` 或其他盘中实时源，不进入当前盘后 READY snapshot 的 canonical 发布链；后续若要进入正式方案，应归入有明确授权的实时层。
6. 无公开文档、无稳定授权边界的网页内部接口，不直接作为核心持久化表 canonical source。

## Status

当前状态：M8 已完成。QuantA 的正式数据源方案已收敛为 `Tushare Pro 5000积分档 + 巨潮资讯/上交所/深交所 + AKShare/BaoStock补充层 + 未来授权实时层` 的四层结构。
