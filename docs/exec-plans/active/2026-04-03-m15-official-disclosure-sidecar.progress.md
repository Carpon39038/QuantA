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

## Verification

1. `scripts/smoke.sh`
2. `node --check frontend/src/app/main.js`
3. `env PYTHONPYCACHEPREFIX=/tmp/quanta-pycache python3 -m py_compile ...`
4. live `python3 scripts/tushare_live_sync_smoke.py`

## Live Result

2026-04-03 实测在 `QUANTA_SOURCE_PROVIDER=tushare`、`QUANTA_DISCLOSURE_PROVIDER=cninfo` 环境下，隔离 live sync 返回：

- `inserted_official_disclosure_item: 3`
- `official_disclosure_item: READY`

说明官方披露元数据 sidecar 已经真正落到 live sync 主链，不再只是 fixture-only 能力。

## Next

1. 把官方披露从 metadata-first 往正文、问询函和公告分类解释继续推进。
2. 增加 AKShare/BaoStock shadow validation，做多源交叉校验。
