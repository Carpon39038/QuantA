# M10 Tushare VIP Fundamental Sidecar

## Goal

把 `Tushare Pro 5000积分档` 的 VIP 财务接口真正接进 QuantA 当前可消费的发布链，让 screener 的 `fundamental_score` 开始读取 canonical 财务信号，而不再只依赖启发式规则。

## Scope

本计划聚焦：

1. 用 `fina_indicator_vip`、`income_vip`、`balancesheet_vip`、`cashflow_vip` 构造最小财务 sidecar。
2. 新增 `fundamental_feature_daily` 派生表，并保持 `snapshot_id` / `trade_date` 语义清晰。
3. 让 `screener` 在有 canonical 财务分时优先消费真实 `fundamental_score`，缺失时再回退到启发式分数。
4. 用离线 fake client 与默认 smoke 覆盖“季度回落、字段归一、screener 接线”。

## Non-Goals

本计划不包含：

1. 落完整原始财务报表事实表。
2. 在没有 token 的前提下强行做 live Tushare 验证。
3. 把公告披露、财报正文或分钟级行情混进本轮。
4. 一次性重写所有 read-path 来展示财务明细。

## Done When

1. provider 能从最近可用财报期回落加载 VIP 财务数据，并归一成 `fundamental_feature_overrides`。
2. `analysis` 能把财务 sidecar 落成 `fundamental_feature_daily`。
3. `screener` 能在有 canonical 财务分时优先消费 `fundamental_feature_daily`。
4. 离线 smoke 和默认 `scripts/smoke.sh` 仍然通过。

## Verify By

1. `env PYTHONPYCACHEPREFIX=/tmp/quanta-pycache python3 -m py_compile backend/app/shared/providers/market_data_source.py backend/app/domains/analysis/bootstrap.py backend/app/domains/market_data/sync.py backend/app/domains/screener/bootstrap.py backend/app/domains/market_data/repo.py backend/app/domains/market_data/schema.py backend/app/domains/market_data/bootstrap.py scripts/tushare_provider_smoke.py`
2. `python3 scripts/tushare_provider_smoke.py`
3. `python3 scripts/render_db_schema.py`
4. `scripts/smoke.sh`
5. `python3 scripts/check_harness_docs.py`
6. `python3 scripts/check_execution_harness.py --require-all-passing`

## Tasks

- [x] 增加 `fundamental_feature_daily` schema 与 bootstrap 兼容性检查
- [x] 把 Tushare VIP 财务接口归一成 `fundamental_feature_overrides`
- [x] 在 analysis/sync 中落地 `fundamental_feature_daily`
- [x] 让 screener 优先消费 canonical 财务分
- [x] 扩展离线 smoke、schema 生成与默认 smoke

## Decisions

1. 先落“可消费的财务 sidecar 表”，而不是一次性引入完整原始财务事实表，减少对当前 DuckDB foundation 的破坏面。
2. 财务报告期按 `biz_date` 向后回落季度末探测，避免盘后日期落在新季度初期时因为最新季报尚未可用而直接失败。
3. 当 canonical 财务分缺失时，screener 仍保留原有启发式回退，避免默认 fixture 开发链被 token 缺失阻塞。

## Status

当前状态：M10 第一刀已完成。`fundamental_feature_daily`、VIP 财务 sidecar、screener 接线、离线 smoke 和默认 smoke 都已通过；下一步进入 live token 验证，以及决定是否要把财务明细继续暴露到 read-path。
