# M10 Tushare VIP Fundamental Sidecar Progress

## Current State

QuantA 现在已经不只是在 provider 层声明“以后会接 VIP 财务”。当前仓库已把 Tushare VIP 财务接口归一成 `fundamental_feature_daily`，并让 screener 在有 canonical 财务分时优先消费真实财务信号。

## Last Completed

1. 新增 `fundamental_feature_daily` 表结构，并刷新了生成态 schema 文档。
2. 在 `TushareMarketDataProvider` 中增加最近可用财报期回落逻辑，接入 `fina_indicator_vip`、`income_vip`、`balancesheet_vip`、`cashflow_vip`。
3. 把 VIP 财务数据归一成 `fundamental_feature_overrides`，落到 analysis/sync 主链。
4. 更新 screener 查询，让 `fundamental_score` 优先读取 canonical 财务分，并把高杠杆、现金流弱于利润等风险标签写回结果。
5. 扩展 `scripts/tushare_provider_smoke.py` 与 `scripts/smoke.sh`，覆盖季度回落和财务 sidecar 接线。

## Verification

1. `env PYTHONPYCACHEPREFIX=/tmp/quanta-pycache python3 -m py_compile backend/app/shared/providers/market_data_source.py backend/app/domains/analysis/bootstrap.py backend/app/domains/market_data/sync.py backend/app/domains/screener/bootstrap.py backend/app/domains/market_data/repo.py backend/app/domains/market_data/schema.py backend/app/domains/market_data/bootstrap.py scripts/tushare_provider_smoke.py`
2. `python3 scripts/tushare_provider_smoke.py`
3. `python3 scripts/render_db_schema.py`
4. `scripts/smoke.sh`
5. `python3 scripts/check_harness_docs.py`
6. `python3 scripts/check_execution_harness.py --require-all-passing`

## Next Step

在有 `Tushare` token 的环境里做 live provider 验证，并决定是否把 `fundamental_feature_daily` 继续暴露到 stock detail / screener detail 的 read-path。
