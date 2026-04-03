# M13 Tushare History Backfill Progress

## Current State

最小 Tushare 历史回补链已经落地：provider 能列出区间开市日，`market_data.sync` 能按日期区间逐日回补，重跑同一区间会自动跳过已存在的 `biz_date`。

## Last Completed

1. `MarketDataProvider` 新增 `list_open_biz_dates`，并已接到 `fixture_json`、`tushare`、`akshare` 三个 provider。
2. `market_data.sync` 新增 `backfill_market_data(...)` 与 CLI 参数 `--start-biz-date/--end-biz-date`。
3. backfill 默认会查询现有 `raw_snapshot.biz_date` 并跳过已存在日期，避免重复写同日快照。
4. 新增 `scripts/market_data_backfill_smoke.py`，在 fake Tushare 环境里验证：
   - 首跑 `2026-03-31 ~ 2026-04-02` 可写入 3 个新 snapshot
   - 二次重跑会 `snapshot_count=0` 且全部进入 `skipped_existing_biz_dates`
5. 新增 `scripts/tushare_live_backfill_smoke.py`，在真 token 环境里验证最近 5 个交易日的隔离 live backfill：
   - 首跑 `synced_biz_date_count=5`
   - 二次重跑 `skipped_existing_biz_date_count=5`
   - 隔离库结果为 `raw_snapshot=7`、`artifact_publish=7`、`daily_bar=25`、`fundamental_feature_daily=15`

## Verification

1. `python3 scripts/market_data_backfill_smoke.py`
2. `python3 scripts/tushare_live_backfill_smoke.py`
3. `scripts/smoke.sh`

## Next Step

把历史回补接入正式运维链，再继续推进官方披露源、AKShare/BaoStock shadow validation 和更高等级的浏览器级验收。
