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

当前行为已升级为 `source-backed DuckDB dev foundation`：

1. 本地 runtime 会在 `data/duckdb/quanta.duckdb` 初始化最小 schema。
2. 当前默认使用 `fixture_json` source provider，从 `backend/app/fixtures/source_snapshots/` 读取“可复现的外部数据源快照”；同时已接入 `akshare` 作为正式支持的 source adapter 之一。
3. startup 会按 `market_data -> analysis -> screener -> backtest` 顺序完成最小 dev bootstrap；repo 查询使用 DuckDB 只读连接，避免写时副作用。
4. 已提供 stock detail 入口：`/api/v1/stocks/{symbol}/snapshot`、`/api/v1/stocks/{symbol}/kline`、`/api/v1/stocks/{symbol}/indicators`、`/api/v1/stocks/{symbol}/capital-flow`。
5. 已提供 screener/backtest detail 入口：`/api/v1/screener/runs/latest`、`/api/v1/screener/runs/{run_id}`、`/api/v1/backtests/runs/latest`、`/api/v1/backtests/runs/{backtest_id}`。
6. 已提供最小 tasking/service 入口：`/api/v1/tasks/runs`、`/api/v1/system/health`、`/api/v1/system/alerts`、`POST /api/v1/tasks/daily-sync/run`、`POST /api/v1/tasks/daily-screener/run`、`POST /api/v1/tasks/daily-backtest/run`、`POST /api/v1/backtests/runs`。
7. `daily_sync` 已改成真正的 source-backed sync：会先写 `raw_snapshot` 与 `artifact_publish(status=BUILDING)`，再由 `daily_screener`、`daily_backtest` 逐步补齐产物并最终发布为 `READY`。
8. service/backtest durable queue 现已带 `retry_count`、`max_retries`、`next_attempt_at` 与 `last_error`，worker 会执行 retry/backoff，并在耗尽时写本地 alerts JSONL。
9. 已提供最小 `domains.tasking.scheduler` resident loop，可轮询 auto pipeline，并通过 `scripts/pipeline_smoke.py` 覆盖成功路径与 retry 路径。
10. 当前正式数据源口径已经收敛为 `Tushare Pro 5000积分档 + 巨潮资讯/上交所/深交所 + AKShare/BaoStock补充层`。
11. `Tushare Pro 5000` 当前承担的 canonical 目标表包括：`stock_basic`、`trade_calendar`、`daily_bar`、`adj_factor`、`daily_basic`、`stk_limit`、`moneyflow`、`top_list`、`moneyflow_hsgt`，以及全市场季度财务过滤所需的 `fina_indicator_vip`、`income_vip`、`balancesheet_vip`、`cashflow_vip`。
12. 全市场季度财务过滤现在回到 v1.0 默认前提，可以直接进入正式选股主链，而不必先降级成“候选池后拉取”。
13. 当前 `akshare.stock_zh_a_hist` 这条历史日线路径底层会依赖其上游公开行情接口；仓库已接入 AKShare provider，但 live fetch 是否成功仍取决于当前机器的代理/网络环境以及 AKShare 上游链路状态。
14. 后续继续把正式数据源安装、全量历史回补、远端告警通道和更完整的产品 API 替换进这套底座。
