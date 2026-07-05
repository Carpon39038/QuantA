# Frontend Src

这里是 QuantA 前端主代码目录。

当前页面路由：

1. `/monitor`
   盘中监控队列，默认第一屏。
2. `/market`
   市场概览。
3. `/screener`
   选股结果。
4. `/stocks/:symbol`
   个股详情。
5. `/backtest`
   回测报告。

展示层默认消费稳定的已发布快照视图；盘中触发只读取 preview 监控接口，并在页面中标注不进入 READY snapshot 或回测。

当前组织：

1. `app/`
   应用壳、轻量浏览器路由、状态条、任务侧栏和快照元信息。
2. `features/`
   按页面能力拆分的 feature-first 模块。
3. `hooks/`
   API 读取和轮询 hook。
4. `shared/ui/`
   跨 feature 复用的小 UI 原语。

本地运行仍通过 `python3 scripts/run_frontend.py` 或根目录 `pnpm run frontend:dev` 启动 Vite，并由 dev server 代理后端 `/api`。
