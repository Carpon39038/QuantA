# M17 Field-Level Shadow Validation And Operating Universe Progress

## Completed

1. 新增 `backend/app/fixtures/source_universes/core_operating_40.json`，并把默认 `source_universe` 切到 `core_operating_40`。
2. `shadow_validation` 已从 close-only 扩到七字段：
   - `open_raw`
   - `high_raw`
   - `low_raw`
   - `close_raw`
   - `pre_close_raw`
   - `volume`
   - `amount`
3. 新增独立容差配置：
   - `QUANTA_SOURCE_VALIDATION_CLOSE_TOLERANCE_BPS`
   - `QUANTA_SOURCE_VALIDATION_VOLUME_TOLERANCE_BPS`
   - `QUANTA_SOURCE_VALIDATION_AMOUNT_TOLERANCE_BPS`
4. workbench 状态条、runtime payload、live smoke 输出与 app smoke 已同步到新的默认研究池和校验摘要。
5. `source_validation` 现在会输出字段级 `field_summary`，让每个补充源明确说明哪些字段 matched / mismatched / missing。

## Verification

1. `env PYTHONPYCACHEPREFIX=/tmp/quanta-pycache python3 -m py_compile backend/app/app_wiring/settings.py backend/app/shared/providers/source_validation.py backend/app/shared/providers/market_data_source.py scripts/app_smoke.py scripts/tushare_live_smoke.py scripts/tushare_live_sync_smoke.py scripts/tushare_live_backfill_smoke.py`
2. `node --check frontend/src/app/main.js`
3. `scripts/smoke.sh`
4. `python3 scripts/check_harness_docs.py`
5. `python3 scripts/check_execution_harness.py --require-all-passing`
6. live `python3 scripts/tushare_live_smoke.py`
7. live `python3 scripts/tushare_live_sync_smoke.py`
8. live `python3 scripts/tushare_live_backfill_smoke.py`

## Live Result

2026-04-07 在 `QUANTA_SOURCE_PROVIDER=tushare`、`QUANTA_SOURCE_UNIVERSE=core_operating_40`、`QUANTA_SOURCE_VALIDATION_PROVIDERS=akshare,baostock`、`QUANTA_DISCLOSURE_PROVIDER=cninfo` 环境下：

1. `python3 scripts/tushare_live_smoke.py` 返回：
   - `latest_biz_date=2026-04-03`
   - `daily_bar_count=40`
   - `fundamental_feature_override_count=40`
   - `vip_financials_ready=true`
2. `python3 scripts/tushare_live_sync_smoke.py` 返回：
   - `inserted_daily_bar: 40`
   - `inserted_official_disclosure_item: 22`
   - `inserted_fundamental_feature_daily: 40`
   - `shadow_validation.status=OK`
   - `baostock fully matched 40/40 symbols`
   - `baostock field_summary` 在七字段全部 `40 matched / 0 mismatch / 0 missing`
   - `akshare` 当前仍因 Eastmoney 上游链路问题表现为 `UNAVAILABLE`
3. `python3 scripts/tushare_live_backfill_smoke.py` 在隔离 DuckDB 最近 5 个交易日首跑全部写入、二次重跑全部跳过：
   - `raw_snapshot_count=7`
   - `artifact_publish_count=7`
   - `daily_bar_count=210`
   - `fundamental_feature_count=200`

## Next

1. 把 `shadow_validation` 从当前七字段继续扩到复权因子、停牌、涨跌停和企业行为口径。
2. 给 `akshare` 的不稳定链路补更清晰的降级告警，避免它只在 live 结果里表现成长报错字符串。
