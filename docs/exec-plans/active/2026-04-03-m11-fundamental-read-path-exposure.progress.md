# M11 Fundamental Read-Path Exposure Progress

## Current State

QuantA 现在已经能在发布链里读到财务 sidecar，不再只有 screener 内部知道 `fundamental_feature_daily` 的存在。后端新增了 `stock fundamentals` API，前端 workbench 也补上了财务侧 panel。

## Last Completed

1. 增加了 `load_stock_fundamentals`、container 接线和 `/api/v1/stocks/{symbol}/fundamentals`。
2. 在 `stock_snapshot` 的 `available_series` 里补进 `fundamental_feature` 范围信息。
3. 前端个股详情新增“财务侧” panel，并读取 fundamentals payload。
4. 默认 `fixture_json` 链不再落全空的 `fundamental_feature_daily` placeholder 行，空 payload 会被明确保留为“暂无 canonical 财务 sidecar”。
5. 更新了 `scripts/app_smoke.py`，覆盖新的 API 和前端壳子。

## Verification

1. `env PYTHONPYCACHEPREFIX=/tmp/quanta-pycache python3 -m py_compile backend/app/api/dev_server.py backend/app/app_wiring/container.py backend/app/domains/market_data/repo.py backend/app/domains/analysis/bootstrap.py scripts/app_smoke.py`
2. `node --check frontend/src/app/main.js`
3. `scripts/smoke.sh`
4. `python3 scripts/check_harness_docs.py`
5. `python3 scripts/check_execution_harness.py --require-all-passing`

## Next Step

在有 `Tushare` token 的环境里做 live provider 验证，并开始推进历史回补与更完整的财务 read-path。
