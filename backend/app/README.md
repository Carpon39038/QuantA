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

当前行为仍是 fixture-backed，作用是先把启动、接口和 smoke 入口接起来，后续再替换成真实 DuckDB 与任务链路。
