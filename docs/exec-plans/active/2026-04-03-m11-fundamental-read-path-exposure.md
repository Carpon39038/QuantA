# M11 Fundamental Read-Path Exposure

## Goal

把已经落地到 DuckDB 的 `fundamental_feature_daily` 真正暴露到 QuantA 的产品面，让财务 sidecar 不只在 screener 内部消费，也能通过 stock detail API 和 workbench 直接查看。

## Scope

本计划聚焦：

1. 增加 `stock fundamentals` read-path 查询与 API。
2. 在前端个股详情里展示财务侧 panel。
3. 保持默认 `fixture_json` 开发链返回“空但合法”的财务 payload，不伪造 canonical 财务值。
4. 更新 app smoke、README 和计划记录。

## Non-Goals

本计划不包含：

1. 强行要求默认 fixture 链伪造真实财务 sidecar。
2. 接入 live Tushare token。
3. 设计完整财务分析页面或多股票财务对比。
4. 改写 screener/backtest 主逻辑。

## Done When

1. `GET /api/v1/stocks/{symbol}/fundamentals` 返回合法 payload，并支持 as-of snapshot 读取。
2. 前端 workbench 能展示财务侧 panel。
3. 默认 fixture 链与 app smoke 仍然通过。

## Verify By

1. `env PYTHONPYCACHEPREFIX=/tmp/quanta-pycache python3 -m py_compile backend/app/api/dev_server.py backend/app/app_wiring/container.py backend/app/domains/market_data/repo.py backend/app/domains/analysis/bootstrap.py scripts/app_smoke.py`
2. `node --check frontend/src/app/main.js`
3. `scripts/smoke.sh`
4. `python3 scripts/check_harness_docs.py`
5. `python3 scripts/check_execution_harness.py --require-all-passing`

## Tasks

- [x] 增加 fundamentals repo/query/container/api 读口
- [x] 在 stock snapshot 中暴露 fundamental sidecar 的可用范围
- [x] 在前端个股详情新增财务侧 panel
- [x] 更新 app smoke 与 README

## Decisions

1. 默认 `fixture_json` 开发链不伪造 canonical 财务 sidecar，`fundamentals` endpoint 可以为空，但必须语义稳定。
2. 财务 panel 先放在 stock detail 里，保持 read-path 最小闭环，再决定是否做更完整财务页面。

## Status

当前状态：M11 已完成。`fundamentals` API、workbench 财务侧 panel 和 app smoke 都已通过；下一步回到 live Tushare token 验证与历史回补。
