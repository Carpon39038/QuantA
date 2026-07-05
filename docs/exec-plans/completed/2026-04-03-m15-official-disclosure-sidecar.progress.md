# M15 Official Disclosure Sidecar Progress

## Completed

1. 新增 `official_disclosure_item` 表，并让 dev bootstrap 为默认快照 seed 最小公告元数据。
2. 新增 `official_disclosure_source.py`，支持：
   - `auto`
   - `fixture_json`
   - `cninfo`
   - `none`
3. `market_data.sync` 现会在 source-backed snapshot 生成时同步官方披露 sidecar，并把 `official_disclosure_item` 写进 artifact status。
4. 新增 `GET /api/v1/stocks/{symbol}/disclosures`，以及 stock snapshot 中的 `available_series.official_disclosure`。
5. workbench stock detail 新增“官方披露” panel，默认展示最近 4 条公告元数据。
6. 2026-07-03 T-35 扩展：`official_disclosure_item` 新增 `disclosure_event_id`、`disclosure_event_type`、`body_summary`、`classification_explanation`、`inquiry_status`、`reply_status` 和 `related_announcement_id`。
7. stock disclosures read path 现在按 `disclosure_event_id` 返回去重后的披露事件，并保留 `effective_snapshot_id/effective_publish_seq`。
8. `fixture_json` 与 dev seed 已覆盖正文摘要、分类解释、交易所问询函、问询回复和重复来源去重样例。
9. workbench stock detail 公告 panel 现在展示分类、披露时间、摘要、来源、问询/回复状态和快照绑定。

## Verification

1. `scripts/smoke.sh`
2. `pnpm --dir frontend exec tsc --noEmit`
3. `env PYTHONPYCACHEPREFIX=/tmp/quanta-pycache python3 -m py_compile ...`
4. live `python3 scripts/tushare_live_sync_smoke.py`
5. `pnpm exec eslint frontend/src/api/types.ts frontend/src/features/stock-detail/StockDetail.tsx --cache --ext .ts,.tsx`
6. `pnpm --dir frontend exec tsc --noEmit`
7. `python3 scripts/app_smoke.py`
8. `scripts/smoke.sh`

## Live Result

2026-04-03 实测在 `QUANTA_SOURCE_PROVIDER=tushare`、`QUANTA_DISCLOSURE_PROVIDER=cninfo` 环境下，隔离 live sync 返回：

- `inserted_official_disclosure_item: 3`
- `official_disclosure_item: READY`

说明官方披露元数据 sidecar 已经真正落到 live sync 主链，不再只是 fixture-only 能力。

## Next

1. 继续把 live 官方披露从标题摘要推进到 PDF/正文片段抽取，并评估上交所/深交所问询深链采集。
2. 增加 AKShare/BaoStock shadow validation，做多源交叉校验。
