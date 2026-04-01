# M8 Official Data Source Strategy Progress

## Current State

QuantA 已经不再只是“列出几个可能的数据源”，而是有了正式 source stack：`Tushare Pro 2000积分档` 的核心结构化盘后数据、法定披露/公开信息、补充适配层和未来授权实时层已经在仓库中分层定义。

## Last Completed

1. 回查了 `mydoc/` 中关于 AKShare、腾讯和外部数据源的原始要求，确认 AKShare 确实是既定正式来源之一。
2. 调研了 `Tushare Pro`、`巨潮资讯`、`上交所`、`深交所`、`Choice` 的公开文档和服务边界。
3. 明确把 `Tushare Pro 2000积分档` 设为 v1.0 核心结构化盘后数据的 canonical source 基线。
4. 明确把 `巨潮资讯`、`上交所`、`深交所` 设为公告、公开信息和披露类数据的 official source。
5. 明确 `AKShare/BaoStock` 在正式方案中保留为正式支持的 source adapter，但主要承担补充、验证和缺口兜底职责。
6. 明确全市场季度财务 `*_vip` 接口不再作为 v1.0 默认前提，财务过滤先按“候选池后拉取”或“分批缓存”实现。

## Verification

1. `python3 scripts/check_harness_docs.py`
2. `python3 scripts/check_execution_harness.py --require-all-passing`

## Next Step

按新的 source strategy 推进实现：先补 `Tushare Pro 2000` provider，再把公告/公开信息链接到 `巨潮资讯` 和交易所官方源，最后保留 `AKShare/BaoStock` 作为 shadow validation 和 gap-fill。
