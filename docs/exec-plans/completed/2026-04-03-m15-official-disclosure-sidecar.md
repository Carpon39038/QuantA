# M15 Official Disclosure Sidecar

## Goal

把 `巨潮资讯` 这条官方披露源真正接进 QuantA 当前可消费的发布链，先落“公告元数据 sidecar”，让个股详情和 API 能读取官方披露，而不是只在架构文档里写“以后会接”。

## Scope

1. 新增 `official_disclosure_item` DuckDB 表，语义绑定 `snapshot_id`。
2. 新增官方披露 provider，默认 live 环境走 CNInfo 官方公告检索页与 stock lookup JSON。
3. 在 `market_data.sync` 中落地官方披露 sidecar，并把它纳入 artifact status。
4. 暴露 `GET /api/v1/stocks/{symbol}/disclosures` 读口。
5. workbench 增加最小“官方披露” panel。

## Non-Goals

1. 本里程碑不做公告正文抽取。
2. 本里程碑不做上交所/深交所问询函与回复函深链整合。
3. 本里程碑不做跨源去重和正文 NLP 摘要。

## Acceptance

1. DuckDB 中存在 `official_disclosure_item`，并可随 `snapshot_id` 一起清理与重建。
2. 默认开发链可以通过本地 fixture 跑通 disclosures read-path，不引入外网依赖。
3. live `tushare + cninfo` 环境里，隔离 sync 能写出非零 `official_disclosure_item`。
4. `GET /api/v1/stocks/{symbol}/disclosures` 返回合法 payload，支持 as-of snapshot 读取。
5. 前端 stock detail 展示官方披露列表，app smoke 覆盖到了该读口与 UI 文案。

## Tasks

- [x] 增加 `official_disclosure_item` schema 与 dev bootstrap seed
- [x] 新增 official disclosure provider，支持 `auto/fixture_json/cninfo/none`
- [x] 把 official disclosure sidecar 接入 `market_data.sync`
- [x] 增加 disclosures repo/query/container/api 读口
- [x] 在 workbench stock detail 增加“官方披露” panel
- [x] 补 app smoke / live sync 验证并更新系统记录

## Notes

1. CNInfo 官方检索页的 stock 参数需要 `证券代码,orgId` 组合，orgId 通过官方 `szse_stock.json` stock lookup 文件解析。
2. 当前默认只落公告元数据，不把公告正文混进 canonical 日线/财务 provider。

## T-35 Extension: Disclosure Events

2026-07-03 在原 M15 sidecar 上继续扩展，而不是另建一条披露系统：

1. `official_disclosure_item` 继续绑定 `snapshot_id`，但每行现在带 `disclosure_event_id` 与 `disclosure_event_type`，读口按事件 ID 返回去重后的披露事件。
2. 事件 payload 新增 `body_summary`、`classification_explanation`、`inquiry_status`、`reply_status` 与 `related_announcement_id`，供盘后研究引用正文摘要、公告分类和问询/回复状态。
3. `fixture_json` 开发链覆盖普通公告、股份回购、交易所问询函、问询回复和重复来源行；`cninfo` live 路径会基于官方公告标题/分类生成保守分类与摘要字段。
4. `/api/v1/stocks/{symbol}/disclosures` 保持原 endpoint，但返回 source、披露时间、摘要/分类、问询状态和 effective snapshot binding。
5. workbench 个股详情公告 panel 现在展示分类、披露时间、正文摘要、来源、问询/回复状态与快照绑定。

边界：本扩展没有做 PDF 全文下载、OCR 或深度 NLP 摘要；live CNInfo 没有正文片段时，`body_summary` 是基于官方标题生成的保守短摘要。完整公告正文解析和上交所/深交所深链采集仍是后续增强。
