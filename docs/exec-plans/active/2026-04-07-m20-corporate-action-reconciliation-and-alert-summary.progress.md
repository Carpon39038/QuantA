# M20 Corporate Action Reconciliation And Alert Summary Progress

## Completed

1. `market_data.sync` 现会在 `price_series_daily` 与 `corporate_action_item` 落库后补做 `corporate_action` reconciliation，并把结果合并回 `shadow_validation.canonical_checks`。
2. reconciliation 采用“覆盖内比对、覆盖外显式跳过”的语义：
   - 事件日在当前 `price_series_daily` 覆盖内时，比对 `adj_factor` 前后是否变化
   - 事件日早于当前覆盖窗口时，累计到 `out_of_coverage_count`
3. `raw_snapshot.source_watermark_json` 现在会在 sync 后二次更新，确保新的 `corporate_action` canonical check 真实落盘并被查询侧看到。
4. `backend/app/shared/telemetry/alerts.py` 新增 alert summary 聚合，`/api/v1/system/health` 与 `/api/v1/system/alerts` 都会返回：
   - `window_count`
   - `severity_counts`
   - `alert_type_counts`
   - `provider_alerts`
   - `latest_alert`
5. workbench 现在会优先显示 provider incident 摘要，再显示最近原始 alerts；status strip 的告警卡片也会优先提示最新 provider degradation。
6. `scripts/market_data_backfill_smoke.py` 已补 fake `adj_factor` 数据，并显式断言 latest snapshot 的 `corporate_action` canonical check 为 `OK`。

## Verification

1. `env PYTHONPYCACHEPREFIX=/tmp/quanta-pycache python3 -m py_compile backend/app/shared/telemetry/alerts.py backend/app/domains/market_data/repo.py backend/app/app_wiring/container.py backend/app/domains/market_data/sync.py scripts/app_smoke.py scripts/market_data_backfill_smoke.py`
2. `node --check frontend/src/app/main.js`
3. `python3 scripts/market_data_backfill_smoke.py`
4. `scripts/smoke.sh`
5. live `python3 scripts/tushare_live_sync_smoke.py`

## Live Result

2026-04-07 在 `QUANTA_SOURCE_PROVIDER=tushare`、`QUANTA_SOURCE_UNIVERSE=core_operating_40`、`QUANTA_SOURCE_VALIDATION_PROVIDERS=akshare,baostock`、`QUANTA_DISCLOSURE_PROVIDER=cninfo` 环境下：

1. `python3 scripts/tushare_live_sync_smoke.py` 返回：
   - `inserted_corporate_action_item: 936`
   - `shadow_validation.canonical_checks.corporate_action.status = SKIPPED`
   - `shadow_validation.canonical_checks.corporate_action.out_of_coverage_count = 607`
   - `alert_count = 2`
2. 上述 `SKIPPED` 的原因不是坏数据，而是当前隔离 live sync 的价格历史窗口没有覆盖这些已实施企业行为的事件日；这条语义已被显式编码进 check message。
3. provider degradation 仍然清晰可见：
   - `akshare = UNAVAILABLE / akshare_upstream_connectivity`
   - `baostock = WARN / adj_factor_semantics_mismatch`

## Next

1. 继续把长期企业行为覆盖窗口往前推，让 `corporate_action` reconciliation 在更长 live backfill 下从 `SKIPPED/out_of_coverage` 逐步进入更高比例的 `checked/aligned`。
2. 把 alert summary 从 workbench/runtime 再桥接到更主动的通知面。
