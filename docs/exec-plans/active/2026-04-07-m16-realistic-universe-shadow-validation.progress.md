# M16 Realistic Universe And Shadow Validation Progress

## Completed

1. 新增 `backend/app/fixtures/source_universes/core_research_12.json`，并让 `load_settings()` 在未设置 `QUANTA_SOURCE_SYMBOLS` 时默认加载该研究池。
2. 新增 `source_validation.py`，支持：
   - `akshare`
   - `baostock`
   - `none`
3. `market_data.sync` 现会把 `shadow_validation` 写进 `raw_snapshot.source_watermark_json`，并在 market highlights 中留下校验状态。
4. `/api/v1/snapshot/latest`、`/api/v1/system/health` 与 runtime payload 现已暴露：
   - `source_universe`
   - `source_symbol_count`
   - `source_validation_providers`
   - `shadow_validation`
5. `tushare` provider 现在会从最近开市日回退到最近一个真正有日线的 `biz_date`，避免盘中空日线导致 sync 假失败。
6. workbench 状态条新增“研究池”和“补充校验”信息卡。

## Verification

1. `env PYTHONPYCACHEPREFIX=/tmp/quanta-pycache python3 -m py_compile backend/app/app_wiring/container.py backend/app/app_wiring/settings.py backend/app/shared/providers/market_data_source.py backend/app/shared/providers/source_validation.py backend/app/domains/market_data/bootstrap.py backend/app/domains/market_data/repo.py backend/app/domains/market_data/sync.py scripts/app_smoke.py scripts/market_data_backfill_smoke.py scripts/tushare_live_sync_smoke.py scripts/tushare_live_backfill_smoke.py`
2. `node --check frontend/src/app/main.js`
3. `scripts/smoke.sh`
4. `python3 scripts/check_harness_docs.py`
5. `python3 scripts/check_execution_harness.py --require-all-passing`
6. live `python3 scripts/tushare_live_smoke.py`
7. live `python3 scripts/tushare_live_sync_smoke.py`
8. live `python3 scripts/tushare_live_backfill_smoke.py`

## Live Result

2026-04-07 在 `QUANTA_SOURCE_PROVIDER=tushare`、`QUANTA_SOURCE_UNIVERSE=core_research_12`、`QUANTA_SOURCE_VALIDATION_PROVIDERS=akshare,baostock`、`QUANTA_DISCLOSURE_PROVIDER=cninfo` 环境下：

1. `python3 scripts/tushare_live_smoke.py` 返回：
   - `latest_biz_date=2026-04-03`
   - `daily_bar_count=12`
   - `fundamental_feature_override_count=12`
   - `vip_financials_ready=true`
2. `python3 scripts/tushare_live_sync_smoke.py` 返回：
   - `inserted_daily_bar: 12`
   - `inserted_official_disclosure_item: 7`
   - `inserted_fundamental_feature_daily: 12`
   - `shadow_validation.status=OK`
   - `akshare matched 12/12 symbols`
   - `baostock matched 12/12 symbols`
3. `python3 scripts/tushare_live_backfill_smoke.py` 在隔离 DuckDB 最近 5 个交易日首跑全部写入、二次重跑全部跳过：
   - `raw_snapshot_count=7`
   - `artifact_publish_count=7`
   - `daily_bar_count=70`
   - `fundamental_feature_count=60`

## Next

1. 把 `shadow_validation` 从 close 扩展到成交额、复权因子、停牌和涨跌停等更细口径。
2. 继续把研究池从 `core_research_12` 扩到更大的可运营 universe，并增加质量分层。
