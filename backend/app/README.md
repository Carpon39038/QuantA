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
5. `python3 -m backend.app.domains.market_data.bootstrap --print-summary`
6. `python3 -m backend.app.domains.analysis.bootstrap --print-summary`
7. `python3 -m backend.app.domains.screener.bootstrap --print-summary`
8. `python3 -m backend.app.domains.backtest.bootstrap --print-summary`

当前行为已升级为 `DuckDB-backed dev foundation`：

1. 本地 runtime 会在 `data/duckdb/quanta.duckdb` 初始化最小 schema。
2. 当前仍用仓库 fixture 作为 deterministic dev seed，但 backend 读取路径已经走 DuckDB，而不是直接读 JSON。
3. startup 会按 `market_data -> analysis -> screener -> backtest` 顺序完成最小 dev bootstrap；repo 查询使用 DuckDB 只读连接，避免写时副作用。
4. 已提供 stock detail 入口：`/api/v1/stocks/{symbol}/snapshot`、`/api/v1/stocks/{symbol}/kline`、`/api/v1/stocks/{symbol}/indicators`、`/api/v1/stocks/{symbol}/capital-flow`。
5. 已提供 screener/backtest detail 入口：`/api/v1/screener/runs/latest`、`/api/v1/screener/runs/{run_id}`、`/api/v1/backtests/runs/latest`、`/api/v1/backtests/runs/{backtest_id}`。
6. 已提供最小 tasking/service 入口：`/api/v1/tasks/runs`、`/api/v1/system/health`、`POST /api/v1/tasks/daily-sync/run`、`POST /api/v1/tasks/daily-screener/run`、`POST /api/v1/backtests/runs`。
7. 这些 POST 入口现在返回 durable queue request object，由 `domains.tasking.worker` 异步消费；query GET 继续保持 DuckDB 只读连接。
8. 后续继续把真实日线同步、调度器、失败重试和更完整的产品 API 替换进这套底座。
