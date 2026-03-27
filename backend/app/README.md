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
3. `python3 -m backend.app.domains.market_data.bootstrap --print-summary`

当前行为已升级为 `DuckDB-backed dev foundation`：

1. 本地 runtime 会在 `data/duckdb/quanta.duckdb` 初始化最小 schema。
2. 当前仍用仓库 fixture 作为 dev seed，但 backend 读取路径已经走 DuckDB，而不是直接读 JSON。
3. 后续继续把真实日线同步、as-of 查询和任务链路替换进这套底座。
