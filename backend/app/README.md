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
9. `python3 -m backend.app.domains.market_data.sync --lookback-open-days 20 --print-summary`
10. `python3 -m backend.app.domains.market_data.sync --target-start-biz-date 2026-01-29 --print-summary`
11. `python3 -m backend.app.domains.analysis.bootstrap --print-summary`
12. `python3 -m backend.app.domains.screener.bootstrap --print-summary`
13. `python3 -m backend.app.domains.backtest.bootstrap --print-summary`
14. `python3 scripts/tushare_provider_smoke.py`
15. `python3 scripts/tushare_live_smoke.py`
16. `python3 scripts/tushare_live_sync_smoke.py`
17. `python3 scripts/market_data_backfill_smoke.py`
18. `python3 scripts/tushare_live_backfill_smoke.py`

当前行为已升级为 `source-backed DuckDB dev foundation`：

1. 本地 runtime 会在 `data/duckdb/quanta.duckdb` 初始化最小 schema。
2. 当前默认使用 `fixture_json` source provider，从 `backend/app/fixtures/source_snapshots/` 读取“可复现的外部数据源快照”；同时已接入 `tushare`、`akshare` 作为正式支持的 source provider / adapter，并把默认研究池切到 `backend/app/fixtures/source_universes/core_operating_40.json`。
3. startup 会按 `market_data -> analysis -> screener -> backtest` 顺序完成最小 dev bootstrap；repo 查询使用 DuckDB 只读连接，避免写时副作用。
4. 已提供 stock detail 入口：`/api/v1/stocks/{symbol}/snapshot`、`/api/v1/stocks/{symbol}/kline`、`/api/v1/stocks/{symbol}/indicators`、`/api/v1/stocks/{symbol}/capital-flow`、`/api/v1/stocks/{symbol}/fundamentals`、`/api/v1/stocks/{symbol}/disclosures`、`/api/v1/stocks/{symbol}/corporate-actions`。
5. 已提供 screener/backtest detail 入口：`/api/v1/screener/runs/latest`、`/api/v1/screener/runs/{run_id}`、`/api/v1/backtests/runs/latest`、`/api/v1/backtests/runs/{backtest_id}`。
6. 已提供最小 tasking/service 入口：`/api/v1/tasks/runs`、`/api/v1/system/health`、`/api/v1/system/alerts`、`POST /api/v1/tasks/daily-sync/run`、`POST /api/v1/tasks/history-backfill/run`、`POST /api/v1/tasks/daily-screener/run`、`POST /api/v1/tasks/daily-backtest/run`、`POST /api/v1/backtests/runs`；其中 `history-backfill` 现支持 `lookback_open_days` 与 `target_start_biz_date`，既可以按最新 source 日期自动解析滚动回补窗口，也可以直接指定“至少补到哪一天”。
7. `daily_sync` 已改成真正的 source-backed sync：会先写 `raw_snapshot` 与 `artifact_publish(status=BUILDING)`，再由 `daily_screener`、`daily_backtest` 逐步补齐产物并最终发布为 `READY`。
8. service/backtest durable queue 现已带 `retry_count`、`max_retries`、`next_attempt_at` 与 `last_error`，worker 会执行 retry/backoff，并在耗尽时写本地 alerts JSONL。
9. 已提供最小 `domains.tasking.scheduler` resident loop，可轮询 auto pipeline，并通过 `scripts/pipeline_smoke.py` 覆盖成功路径与 retry 路径。
10. 当前正式数据源口径已经收敛为 `Tushare Pro 5000积分档 + 巨潮资讯/上交所/深交所 + AKShare/BaoStock补充层`。
11. `Tushare Pro 5000` 当前承担的 canonical 目标表包括：`stock_basic`、`trade_calendar`、`daily_bar`、`adj_factor`、`daily_basic`、`stk_limit`、`moneyflow`、`top_list`、`moneyflow_hsgt`，以及全市场季度财务过滤所需的 `fina_indicator_vip`、`income_vip`、`balancesheet_vip`、`cashflow_vip`。
12. 全市场季度财务过滤现在回到 v1.0 默认前提，可以直接进入正式选股主链，而不必先降级成“候选池后拉取”。
13. 当前 `akshare.stock_zh_a_hist` 这条历史日线路径底层会依赖其上游公开行情接口；仓库已接入 AKShare provider，但 live fetch 是否成功仍取决于当前机器的代理/网络环境以及 AKShare 上游链路状态。
14. `tushare` provider 当前已覆盖 `stock_basic`、`trade_calendar`、`daily`、`daily_basic`、`stk_limit`、`adj_factor`、`suspend_d`，并会把 `moneyflow`、`top_list`、`moneyflow_hsgt` 归一成 `capital_feature_daily` 可消费的 sidecar overrides、source watermark 与 market overview highlights。
15. `tushare` provider 现已把 `fina_indicator_vip`、`income_vip`、`balancesheet_vip`、`cashflow_vip` 归一成 `fundamental_feature_daily`，让 screener 可以直接读取 canonical 财务分，而不再只用启发式 `fundamental_score`。
16. workbench 已开始展示财务侧、官方披露、企业行为和最近 alerts；默认 `fixture_json` 链会返回确定性的 fundamentals / corporate action / disclosure fixture，而 `tushare` canonical provider 可填充真实财务和企业行为 sidecar。
17. `scripts/tushare_live_smoke.py` 与 `scripts/tushare_live_sync_smoke.py` 已可用于真 token 校验 provider 与隔离 live sync；当前实测 live canonical 数据、双源 shadow validation 与隔离 DuckDB 写入都已通过。
18. `tushare` provider 现在会按股票回退到最近可用财报期，而不是强制所有股票共用一个最新报告期；这让 live 路径下的 `fundamental_feature_daily` 可以在财报披露错位时仍保持较高覆盖率。
19. `tushare` provider 还会在白天自动从 `trade_cal` 最近开市日回退到“最近一个真正已有日线的 biz_date”，避免把当天尚未发布的日线误判成 provider 失败。
20. 当前默认研究池已扩到 `core_operating_40`；2026-04-07 实测 `tushare_live_smoke.py` 在该研究池下返回 `latest_biz_date=2026-04-03`、`daily_bar_count=40`、`fundamental_feature_override_count=40`，并达到 `40/40` 财务覆盖。
21. `market_data.sync` 现在会把 `shadow_validation` 写进 `raw_snapshot.source_watermark_json`，并通过 `/api/v1/snapshot/latest`、`/api/v1/system/health` 与 runtime payload 暴露研究池、symbol count 和补充校验状态。
22. 当前补充校验支持 `akshare` 与 `baostock`，已从只比 `close_raw` 扩到 `open/high/low/close/pre_close/volume/amount/adj_factor` 八个字段；默认容差为价格与 `adj_factor` 各 `5 bps`、`volume/amount` 各 `20 bps`。
23. `shadow_validation` 现已新增 canonical quality checks：`adj_factor` 覆盖率、`limit_price` 与板块涨跌停规则、`suspension` 与停牌标记一致性，以及基于 `price_series_daily + corporate_action_item` 的 `corporate_action` reconciliation；这些检查结果会写入 `source_watermark_json`，并经 `/api/v1/snapshot/latest` 与 `/api/v1/system/health` 暴露。
24. `price_series_daily` 现在会优先使用当日 `adj_factor`，并在缺失时从前一版 `price_series_daily` carry forward，避免 source-backed rebuild 把旧交易日的复权因子错误重置为 `1.0`。
25. `tushare` canonical sync 现已新增 `corporate_action_item` sidecar，当前通过 `dividend` 数据集抽取分红送配、股权登记日、除权除息日和派息日，并在写入前按 `knowledge_date <= biz_date` 做 as-of 过滤，避免未来已知信息泄漏进历史 snapshot。
26. `corporate_action_item` 会在同一 `snapshot_id` 下持久化，并通过 stock corporate-actions API 与 workbench 暴露；默认 `fixture_json` 开发链会从 `backend/app/fixtures/source_corporate_actions/` 读取本地 fixture。
27. 2026-04-07 在 `core_operating_40` 上实测，canonical `tushare` 的 `adj_factor/limit_price/suspension` 三类检查均为 `OK`；同一轮 live sync 真实写出 `936` 条 `corporate_action_item`；`baostock` 对原始行情七字段达到 `40/40` match，但在 10 只较老股票上暴露 `adj_factor_semantics_mismatch`；`akshare` 仍会受其上游 Eastmoney 链路稳定性影响，当前在该研究池 live sync 中表现为 `WARN/partial_coverage`，但不会阻断 canonical sync 本身。
28. `market_data.sync` 现在会把 `shadow_validation` 降级项写成本地 alerts；`scripts/tushare_live_sync_smoke.py` 也会在隔离 runtime 中输出 `alert_count` 与最近 alerts，workbench 会直接把最近 alerts 和 provider incident 摘要展示出来，便于验证降级是否真的落盘并被使用者看到。
29. `QUANTA_ALERTS_PATH` 现按 `QUANTA_RUNTIME_DATA_DIR` 相对解析；隔离 smoke 与常驻 runtime 不再错误共用 repo root 下的一份 alerts JSONL。
30. `python3 -m backend.app.domains.market_data.sync --start-biz-date YYYY-MM-DD --end-biz-date YYYY-MM-DD --print-summary` 现在已支持最小历史回补；provider 会先列出开市日，再按日期逐日同步，并默认跳过已存在的 `biz_date`，避免重复堆叠同日快照。现在也支持 `--lookback-open-days N` 与 `--target-start-biz-date YYYY-MM-DD`，分别用于“按窗口推深历史”和“直接补到某个起始日期”。
31. `scripts/market_data_backfill_smoke.py` 会在 fake Tushare 环境里验证 `lookback window`、显式 `target start date` 与 `target_start_biz_date=auto` 三种语义，以及“首跑回补 + 二次跳过已存在日期”；`scripts/tushare_live_backfill_smoke.py` 则会在真 token 下用隔离 DuckDB 输出 `lookback_open_days/target_start_biz_date`、`history_coverage` 和 `corporate_action_check`，用来观察企业行为 reconciliation 是否随着窗口加深而推进。
32. `history_backfill` 现在也已接入 API / durable queue / worker / scheduler；scheduler 在发现最新 READY snapshot 落后于 source provider 时，会优先 enqueue `history_backfill`，而不是只同步单天。
33. 当 `QUANTA_HISTORY_BACKFILL_TARGET_OPEN_DAYS > 0` 或 `QUANTA_HISTORY_BACKFILL_TARGET_START_BIZ_DATE` 被设置时，scheduler 即使在 source 已追平后，也会继续把“历史覆盖不足”视为未 settled 状态，并自动 enqueue `history_backfill` 去扩最新 READY snapshot 的历史覆盖窗口；其中 `QUANTA_HISTORY_BACKFILL_TARGET_START_BIZ_DATE=auto` 现会直接消费 `/api/v1/system/health` 暴露的 recommendation，并只在 recommendation 缺失时回退到 `target_open_days`。
34. `/api/v1/system/health` 现在会返回最新 READY snapshot 的 `history_coverage(start_biz_date/end_biz_date/open_day_count)`，以及 `recommended_target_start_biz_date/recommendation_reason/recommendation_anchor_biz_date`，便于直接从系统面判断当前回补深度和下一次建议补到哪天；`/api/v1/runtime` 也会返回 `resolved_history_backfill_target_start_biz_date`，让 operator 能看见 `auto` 当前已经解析到了哪一天。
35. 2026-04-08 在 `core_operating_40` 上实测，`QUANTA_LIVE_BACKFILL_OPEN_DAYS=10 python3 scripts/tushare_live_backfill_smoke.py` 会把最新覆盖推进到 `2026-03-25 -> 2026-04-08` 的 10 个 open days，并给出 `nearest_out_of_coverage_event_date = 2026-02-12`；继续用 `QUANTA_LIVE_BACKFILL_OPEN_DAYS=40 QUANTA_LIVE_BACKFILL_SKIP_RERUN=1 python3 scripts/tushare_live_backfill_smoke.py` 后，覆盖已推进到 `2026-02-03 -> 2026-04-08` 的 40 个 open days，且 `corporate_action_check` 首次进入 `OK (checked=3, aligned=3)`，剩余最近缺口变成 `2026-01-29`。随后继续用 `QUANTA_LIVE_BACKFILL_TARGET_START_BIZ_DATE=2026-01-29` 明确把窗口推到该事件日，结果变成 `checked=4, aligned=3, boundary_gap=1, nearest_out_of_coverage_event_date=2026-01-23`；再把目标起始日推进到 `2026-01-20` 后，覆盖到达 `2026-01-20 -> 2026-04-08` 的 50 个 open days，`corporate_action_check` 已达到 `OK (checked=5, aligned=5, boundary_gap=0)`，剩余最近缺口继续前移到 `2026-01-16`。2026-04-09 继续用 `QUANTA_LIVE_BACKFILL_TARGET_START_BIZ_DATE=2026-01-15` 后，覆盖推进到 `2026-01-15 -> 2026-04-08` 的 53 个 open days，`corporate_action_check` 已达到 `OK (checked=6, aligned=6, boundary_gap=0)`，剩余最近缺口前移到 `2025-12-19`。
36. 官方披露 sidecar 现已按 `CNInfo official search + stock lookup JSON` 接入 `official_disclosure_item`，并通过 stock disclosures API 与 workbench 暴露最小公告元数据；默认 `fixture_json` 开发链会从 `backend/app/fixtures/source_disclosures/` 读取本地披露 fixture，live `tushare`/`akshare` 则默认走 `cninfo`。
37. 当前官方披露接入仍是“公告元数据优先”，主要覆盖标题、公告时间、详情链接和 PDF 链接；公告正文抽取、交易所问询和更丰富的披露分类仍在后续范围内。
38. `/api/v1/system/health` 与 `/api/v1/system/alerts` 现在会返回 `alert_summary`，聚合最近窗口里的 severity、alert type 和 provider incidents；前端除了呈现最新 provider degradation，也会直接显示最新 `history_coverage` 与建议的下一次 target start date，而不只是一串原始 alerts。
