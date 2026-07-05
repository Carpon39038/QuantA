# Frontend Notes

## Frontend Role

前端负责把“已发布快照里的研究依据”和“盘中预览层里的触发状态”放在同一个盯盘工作流里，不直接参与复杂计算。

## Planned Views

当前前端已经按可直接访问的页面路由组织：

1. `/monitor`
   盘中监控队列。第一屏工作流，合并 READY snapshot 研究依据、preview 盘中触发状态、市场概览和选中个股详情。
2. `/market`
   市场概览页。展示市场事实、历史覆盖和告警摘要。
3. `/screener`
   选股结果页。展示候选池、策略口径、候选解释，并联动个股详情。
4. `/stocks/:symbol`
   个股详情页。展示个股量价诊断、价格曲线、技术指标、资金流向、基本面和公告。
5. `/backtest`
   回测报告页。展示历史回放指标、净值曲线、交易记录和备注。

## Frontend Constraints

1. 研究依据默认只读取 `READY snapshot_id`。
2. 所有图表都要展示口径和时间范围。
3. 展示层尽量复用后端聚合结果，避免浏览器重复推导核心指标。
4. 页面必须能区分“盘后研究依据”“盘中预览触发状态”和“历史回放结果”。
5. 个股详情里的量价状态读取 `/api/v1/stocks/{symbol}/price-volume-analysis`，只展示后端给出的买点状态、理由和风险。
6. 盘中监控状态读取 `/api/v1/preview/watchlist`，必须明确标注其为 preview / 非 READY / 不用于回测。

## File Organization

前端采用 feature-first 组织：

1. `frontend/src/app/`
   应用壳、路由、顶层状态条、任务侧栏和通用页面元信息。
2. `frontend/src/features/market-overview/`
   市场概览页面与面板。
3. `frontend/src/features/intraday-monitor/`
   盘中监控页面和策略监控队列。
4. `frontend/src/features/stock-detail/`
   个股详情与量价诊断。
5. `frontend/src/features/screener-results/`
   选股结果页面。
6. `frontend/src/features/backtest-report/`
   回测报告页面。
7. `frontend/src/shared/ui/`
   可跨 feature 复用的小 UI 原语。

新增页面或面板优先落在对应 feature 下；只有真正跨页面复用的视觉原语才进入 `shared/ui/`。
