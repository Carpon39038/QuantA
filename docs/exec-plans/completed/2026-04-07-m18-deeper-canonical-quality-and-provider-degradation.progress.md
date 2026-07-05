# M18 Deeper Canonical Quality And Provider Degradation Progress

## Completed

1. `tushare` canonical provider 现已接入 `adj_factor` 与 `suspend_d`，并把 `adj_factor_count`、缺失 symbol 和停牌 symbol 摘要写入 `source_watermark`。
2. `shadow_validation` 新增 canonical checks：
   - `adj_factor` 覆盖率 / 非法值
   - `limit_price` 与板块涨跌停规则
   - `suspension` 与停牌标记一致性
3. `price_series_daily` 现在会在缺失当日 `adj_factor` 时从前一版已发布 price series carry-forward，避免 rebuild 把历史复权因子写回 `1.0`。
4. `akshare` 的 Eastmoney 链路问题现在会被稳定分类为 `akshare_upstream_connectivity`，并在 sync 后写入 provider degradation alerts。
5. `baostock` 当前在 `core_operating_40` 上对原始行情七字段仍为 `40/40` match，但在 10 只较老股票上暴露 `adj_factor_semantics_mismatch`；结果会作为非阻断 WARN 暴露。
6. `QUANTA_ALERTS_PATH` 已改成相对 `QUANTA_RUNTIME_DATA_DIR` 解析，隔离 smoke 与常驻 runtime 不再错误共享一份 alerts 文件。
7. `scripts/tushare_live_sync_smoke.py` 现会输出 `alert_count` 与最近 alerts，能直接证明 provider degradation 已真实落盘。

## Verification

1. `env PYTHONPYCACHEPREFIX=/tmp/quanta-pycache python3 -m py_compile backend/app/app_wiring/settings.py backend/app/shared/providers/source_validation.py backend/app/shared/providers/market_data_source.py backend/app/domains/market_data/sync.py scripts/tushare_live_sync_smoke.py scripts/app_smoke.py`
2. live `python3 scripts/tushare_live_smoke.py`
3. live `python3 scripts/tushare_live_sync_smoke.py`
4. `scripts/smoke.sh`
5. `python3 scripts/check_harness_docs.py`
6. `python3 scripts/check_execution_harness.py --require-all-passing`

## Live Result

2026-04-07 在 `QUANTA_SOURCE_PROVIDER=tushare`、`QUANTA_SOURCE_UNIVERSE=core_operating_40`、`QUANTA_SOURCE_VALIDATION_PROVIDERS=akshare,baostock`、`QUANTA_DISCLOSURE_PROVIDER=cninfo` 环境下：

1. `python3 scripts/tushare_live_smoke.py` 返回：
   - `latest_biz_date=2026-04-03`
   - `daily_bar_count=40`
   - `fundamental_feature_override_count=40`
   - `adj_factor_count=40`
   - `adj_factor_missing_symbols=[]`
   - `suspended_symbol_count=0`
2. `python3 scripts/tushare_live_sync_smoke.py` 返回：
   - `inserted_daily_bar: 40`
   - `inserted_official_disclosure_item: 22`
   - `inserted_fundamental_feature_daily: 40`
   - `shadow_validation.canonical_check_status=OK`
   - `shadow_validation.canonical_checks.adj_factor/limit_price/suspension` 全部 `OK`
   - `shadow_validation.degradation_status=DEGRADED`
   - `akshare` 为 `UNAVAILABLE`，`degradation_category=akshare_upstream_connectivity`
   - `baostock` 为 `WARN`，`degradation_category=adj_factor_semantics_mismatch`
   - `alert_count=2`，并在隔离 runtime 真实写出两条 `shadow_validation_provider_degraded`

## Next

1. 把更深的数据质量口径继续推进到分红送配、复权基准长期回溯与更多企业行为修正。
2. 把 `akshare` / `baostock` 的降级告警继续桥接到更显式的运维通知面，而不只停留在本地 alerts JSONL。
