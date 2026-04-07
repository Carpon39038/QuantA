# M19 Corporate Actions And Workbench Alert Visibility Progress

## Completed

1. 新增 `corporate_action_item` 表，并让默认 DuckDB dev seed 提供 3 条确定性企业行为样本。
2. 新增 `backend/app/shared/providers/corporate_action_source.py`，支持：
   - `fixture_json` corporate action fixture
   - `tushare.dividend` live corporate action fetch
   - `auto` 根据 `source_provider` 选择 `fixture_json/tushare/none`
3. `tushare.dividend` 现在会先按 `knowledge_date <= biz_date` 做 as-of 过滤，再按 action key 选择更具体的实施行，避免把未来已知事件和重复记录直接写入 snapshot。
4. `market_data.sync` 已开始写 `corporate_action_item`，并把它纳入 artifact status。
5. 新增 `GET /api/v1/stocks/{symbol}/corporate-actions`，并让 stock snapshot `available_series` 包含 `corporate_action`。
6. workbench 现已展示：
   - 个股企业行为列表
   - 最近 alerts 列表
   - status strip 中的 alert count
7. `app_smoke.py` 已覆盖 corporate-actions endpoint；默认 fixture workbench 可直接显示企业行为样本。

## Verification

1. `env PYTHONPYCACHEPREFIX=/tmp/quanta-pycache python3 -m py_compile backend/app/app_wiring/settings.py backend/app/app_wiring/container.py backend/app/api/dev_server.py backend/app/domains/market_data/schema.py backend/app/domains/market_data/bootstrap.py backend/app/domains/market_data/repo.py backend/app/domains/market_data/sync.py backend/app/shared/providers/corporate_action_source.py scripts/app_smoke.py scripts/market_data_backfill_smoke.py scripts/tushare_live_sync_smoke.py scripts/tushare_live_backfill_smoke.py`
2. `node --check frontend/src/app/main.js`
3. `scripts/smoke.sh`
4. live `python3 scripts/tushare_live_sync_smoke.py`
5. live `python3 scripts/tushare_live_backfill_smoke.py`

## Live Result

2026-04-07 在 `QUANTA_SOURCE_PROVIDER=tushare`、`QUANTA_SOURCE_UNIVERSE=core_operating_40`、`QUANTA_SOURCE_VALIDATION_PROVIDERS=akshare,baostock`、`QUANTA_DISCLOSURE_PROVIDER=cninfo` 环境下：

1. `python3 scripts/tushare_live_sync_smoke.py` 返回：
   - `inserted_corporate_action_item: 936`
   - `corporate_action_count: 936`
   - `artifact_status.corporate_action_item = READY`
   - `alert_count = 2`
2. 同一轮 live sync 中：
   - `akshare` 当前表现为 `WARN/partial_coverage`
   - `baostock` 继续表现为 `WARN/adj_factor_semantics_mismatch`
3. `python3 scripts/tushare_live_backfill_smoke.py` 在最近 5 个交易日首跑全部写入、二次全部跳过，回补链未被企业行为 sidecar 打坏。

## Next

1. 继续把企业行为从当前分红送配 sidecar 推进到更长历史回溯和复权基准核对。
2. 把现在已经能在 workbench 看见的 alerts 继续桥接到更明确的通知面。
