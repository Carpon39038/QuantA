# M9 Tushare Canonical Provider Progress

## Current State

QuantA 已经不再只是在文档里写 `Tushare Pro 5000积分档`。当前 runtime 已经支持 `source_provider=tushare`，并且离线 smoke 能验证其 `MarketDataSnapshot` 映射、资金侧 sidecar，以及最小 VIP 财务 sidecar 到当前分析/选股主链的归一。

## Last Completed

1. 为 `AppSettings` 增加了 `QUANTA_TUSHARE_TOKEN`、`QUANTA_TUSHARE_EXCHANGE` 等配置入口，并把 `tushare` 记入可选依赖。
2. 落地 `TushareMarketDataProvider`，当前已覆盖 `stock_basic`、`trade_cal`、`daily`、`daily_basic`、`stk_limit` 到 `MarketDataSnapshot` 的映射。
3. 把 `moneyflow`、`top_list`、`moneyflow_hsgt` 归一成 `capital_feature_overrides`、`source_watermark` 和 `market_overview.highlights`，让现有 analysis sync 能消费到更真实的资金侧信号。
4. 新增并扩展 `scripts/tushare_provider_smoke.py`，用离线 fake client 验证字段归一、单位换算、资金流 sidecar 和快照语义。
5. 新增 `fundamental_feature_daily` 派生表，并把 `fina_indicator_vip`、`income_vip`、`balancesheet_vip`、`cashflow_vip` 归一成 canonical 财务 sidecar，再由 screener 直接消费真实 `fundamental_score`。
6. 把新的 provider smoke 接进 `scripts/smoke.sh`，并确认默认 `fixture_json` 开发链仍稳定通过。

## Verification

1. `env PYTHONPYCACHEPREFIX=/tmp/quanta-pycache python3 -m py_compile backend/app/shared/providers/market_data_source.py backend/app/domains/analysis/bootstrap.py backend/app/domains/market_data/sync.py scripts/tushare_provider_smoke.py`
2. `python3 scripts/tushare_provider_smoke.py`
3. `python3 scripts/check_harness_docs.py`
4. `python3 scripts/check_execution_harness.py --require-all-passing`
5. `scripts/smoke.sh`

## Next Step

在有 `Tushare` token 的环境里做 live provider 验证，并继续把 canonical provider 扩展到正式历史回补与更多 read-path 暴露。
