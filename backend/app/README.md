# Backend App

这里是 QuantA 后端主代码目录。

目标结构见 [ARCHITECTURE.md](/Users/carpon/web/QuantA/ARCHITECTURE.md)。

当前已落的最小骨架：

1. `domains/market_data`
2. `domains/analysis`
3. `domains/screener`
4. `domains/backtest`
5. `domains/tasking`
6. `shared/providers`

当前可用入口：

1. `python3 -m backend.app.domains.tasking.bootstrap`
2. `python3 -m backend.app.api.dev_server`
3. `python3 -m backend.app.domains.tasking.worker --once --task service`
4. `python3 -m backend.app.domains.tasking.worker --once --task backtest`
5. `python3 -m backend.app.domains.tasking.scheduler --max-ticks 6`
6. `python3 -m backend.app.domains.tasking.scheduler --daemon --auto-pipeline --iterations 3`
7. `python3 -m backend.app.domains.market_data.bootstrap --print-summary`
8. `python3 -m backend.app.domains.market_data.sync --print-summary`
9. `python3 -m backend.app.domains.analysis.bootstrap --print-summary`
10. `python3 -m backend.app.domains.screener.bootstrap --print-summary`
11. `python3 -m backend.app.domains.backtest.bootstrap --print-summary`
12. `python3 scripts/tushare_provider_smoke.py`
13. `python3 scripts/tushare_live_smoke.py`
14. `python3 scripts/tushare_live_sync_smoke.py`
15. `python3 scripts/market_data_backfill_smoke.py`
16. `python3 scripts/tushare_live_backfill_smoke.py`

当前行为已升级为 `source-backed DuckDB dev foundation`：

1. 本地 runtime 会在 `data/duckdb/quanta.duckdb` 初始化最小 schema。
2. 当前默认使用 `fixture_json` source provider，从 `backend/app/fixtures/source_snapshots/` 读取“可复现的外部数据源快照”；同时已接入 `tushare`、`akshare` 作为正式支持的 source provider / adapter，并把默认研究池切到 `backend/app/fixtures/source_universes/core_operating_40.json`。
3. startup 会按 `market_data -> analysis -> screener -> backtest` 顺序完成最小 dev bootstrap；repo 查询使用 DuckDB 只读连接，避免写时副作用。
4. 已提供 stock detail 入口：`/api/v1/stocks/{symbol}/snapshot`、`/api/v1/stocks/{symbol}/kline`、`/api/v1/stocks/{symbol}/indicators`、`/api/v1/stocks/{symbol}/capital-flow`、`/api/v1/stocks/{symbol}/fundamentals`、`/api/v1/stocks/{symbol}/disclosures`。
5. 已提供 screener/backtest detail 入口：`/api/v1/screener/runs/latest`、`/api/v1/screener/runs/{run_id}`、`/api/v1/backtests/runs/latest`、`/api/v1/backtests/runs/{backtest_id}`。
6. 已提供最小 tasking/service 入口：`/api/v1/tasks/runs`、`/api/v1/system/health`、`/api/v1/system/alerts`、`POST /api/v1/tasks/daily-sync/run`、`POST /api/v1/tasks/history-backfill/run`、`POST /api/v1/tasks/daily-screener/run`、`POST /api/v1/tasks/daily-backtest/run`、`POST /api/v1/backtests/runs`。
7. `daily_sync` 已改成真正的 source-backed sync：会先写 `raw_snapshot` 与 `artifact_publish(status=BUILDING)`，再由 `daily_screener`、`daily_backtest` 逐步补齐产物并最终发布为 `READY`。
8. service/backtest durable queue 现已带 `retry_count`、`max_retries`、`next_attempt_at` 与 `last_error`，worker 会执行 retry/backoff，并在耗尽时写本地 alerts JSONL。
9. 已提供最小 `domains.tasking.scheduler` resident loop，可轮询 auto pipeline，并通过 `scripts/pipeline_smoke.py` 覆盖成功路径与 retry 路径。
10. 当前正式数据源口径已经收敛为 `Tushare Pro 5000积分档 + 巨潮资讯/上交所/深交所 + AKShare/BaoStock补充层`。
11. `Tushare Pro 5000` 当前承担的 canonical 目标表包括：`stock_basic`、`trade_calendar`、`daily_bar`、`adj_factor`、`daily_basic`、`stk_limit`、`moneyflow`、`top_list`、`moneyflow_hsgt`，以及全市场季度财务过滤所需的 `fina_indicator_vip`、`income_vip`、`balancesheet_vip`、`cashflow_vip`。
12. 全市场季度财务过滤现在回到 v1.0 默认前提，可以直接进入正式选股主链，而不必先降级成“候选池后拉取”。
13. 当前 `akshare.stock_zh_a_hist` 这条历史日线路径底层会依赖其上游公开行情接口；仓库已接入 AKShare provider，但 live fetch 是否成功仍取决于当前机器的代理/网络环境以及 AKShare 上游链路状态。
14. `tushare` provider 当前已覆盖 `stock_basic`、`trade_calendar`、`daily`、`daily_basic`、`stk_limit`、`adj_factor`、`suspend_d`，并会把 `moneyflow`、`top_list`、`moneyflow_hsgt` 归一成 `capital_feature_daily` 可消费的 sidecar overrides、source watermark 与 market overview highlights。
15. `tushare` provider 现已把 `fina_indicator_vip`、`income_vip`、`balancesheet_vip`、`cashflow_vip` 归一成 `fundamental_feature_daily`，让 screener 可以直接读取 canonical 财务分，而不再只用启发式 `fundamental_score`。
16. workbench 已开始展示财务侧 panel；默认 `fixture_json` 链会返回空但合法的 fundamentals payload，而 `tushare` canonical provider 可填充真实财务 sidecar。
17. `scripts/tushare_live_smoke.py` 与 `scripts/tushare_live_sync_smoke.py` 已可用于真 token 校验 provider 与隔离 live sync；当前实测 live canonical 数据、双源 shadow validation 与隔离 DuckDB 写入都已通过。
18. `tushare` provider 现在会按股票回退到最近可用财报期，而不是强制所有股票共用一个最新报告期；这让 live 路径下的 `fundamental_feature_daily` 可以在财报披露错位时仍保持较高覆盖率。
19. `tushare` provider 还会在白天自动从 `trade_cal` 最近开市日回退到“最近一个真正已有日线的 biz_date”，避免把当天尚未发布的日线误判成 provider 失败。
20. 当前默认研究池已扩到 `core_operating_40`；2026-04-07 实测 `tushare_live_smoke.py` 在该研究池下返回 `latest_biz_date=2026-04-03`、`daily_bar_count=40`、`fundamental_feature_override_count=40`，并达到 `40/40` 财务覆盖。
21. `market_data.sync` 现在会把 `shadow_validation` 写进 `raw_snapshot.source_watermark_json`，并通过 `/api/v1/snapshot/latest`、`/api/v1/system/health` 与 runtime payload 暴露研究池、symbol count 和补充校验状态。
22. 当前补充校验支持 `akshare` 与 `baostock`，已从只比 `close_raw` 扩到 `open/high/low/close/pre_close/volume/amount/adj_factor` 八个字段；默认容差为价格与 `adj_factor` 各 `5 bps`、`volume/amount` 各 `20 bps`。
23. `shadow_validation` 现已新增 canonical quality checks：`adj_factor` 覆盖率、`limit_price` 与板块涨跌停规则、`suspension` 与停牌标记一致性；这些检查结果会写入 `source_watermark_json`，并经 `/api/v1/snapshot/latest` 与 `/api/v1/system/health` 暴露。
24. `price_series_daily` 现在会优先使用当日 `adj_factor`，并在缺失时从前一版 `price_series_daily` carry forward，避免 source-backed rebuild 把旧交易日的复权因子错误重置为 `1.0`。
25. 2026-04-07 在 `core_operating_40` 上实测，canonical `tushare` 的 `adj_factor/limit_price/suspension` 三类检查均为 `OK`；`baostock` 对原始行情七字段达到 `40/40` match，但在 10 只较老股票上暴露 `adj_factor_semantics_mismatch`；`akshare` 仍会受其上游 Eastmoney 链路稳定性影响，当前在该研究池 live sync 中表现为 `UNAVAILABLE`，但不会阻断 canonical sync 本身。
26. `market_data.sync` 现在会把 `shadow_validation` 降级项写成本地 alerts；`scripts/tushare_live_sync_smoke.py` 也会在隔离 runtime 中输出 `alert_count` 与最近 alerts，便于验证 `akshare` 降级是否真的落盘。
27. `QUANTA_ALERTS_PATH` 现按 `QUANTA_RUNTIME_DATA_DIR` 相对解析；隔离 smoke 与常驻 runtime 不再错误共用 repo root 下的一份 alerts JSONL。
28. `python3 -m backend.app.domains.market_data.sync --start-biz-date YYYY-MM-DD --end-biz-date YYYY-MM-DD --print-summary` 现在已支持最小历史回补；provider 会先列出开市日，再按日期逐日同步，并默认跳过已存在的 `biz_date`，避免重复堆叠同日快照。
29. `scripts/market_data_backfill_smoke.py` 会在 fake Tushare 环境里验证“首跑回补 + 二次跳过已存在日期”；`scripts/tushare_live_backfill_smoke.py` 则会在真 token 下用隔离 DuckDB 验证最近 5 个交易日的 live backfill，并为了保持时长可控而关闭 shadow validation / disclosure sidecar。
30. `history_backfill` 现在也已接入 API / durable queue / worker / scheduler；scheduler 在发现最新 READY snapshot 落后于 source provider 时，会优先 enqueue `history_backfill`，而不是只同步单天。
31. `history_backfill` service task 会把区间内每个新同步 snapshot 继续推进 through `daily_screener -> daily_backtest -> READY`，避免在正式运行时留下悬空 `BUILDING` 历史快照。
32. 官方披露 sidecar 现已按 `CNInfo official search + stock lookup JSON` 接入 `official_disclosure_item`，并通过 stock disclosures API 与 workbench 暴露最小公告元数据；默认 `fixture_json` 开发链会从 `backend/app/fixtures/source_disclosures/` 读取本地披露 fixture，live `tushare`/`akshare` 则默认走 `cninfo`。
33. 当前官方披露接入仍是“公告元数据优先”，主要覆盖标题、公告时间、详情链接和 PDF 链接；公告正文抽取、交易所问询和更丰富的披露分类仍在后续范围内。
