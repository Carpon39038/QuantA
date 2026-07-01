# Frontend Notes

## Frontend Role

前端负责把“已发布快照里的研究依据”和“盘中预览层里的触发状态”放在同一个盯盘工作流里，不直接参与复杂计算。

## Planned Views

1. 盘中监控队列
2. 个股详情页
3. 个股量价诊断区
4. 市场概览页
5. 选股结果页
6. 回测报告页

## Frontend Constraints

1. 研究依据默认只读取 `READY snapshot_id`。
2. 所有图表都要展示口径和时间范围。
3. 展示层尽量复用后端聚合结果，避免浏览器重复推导核心指标。
4. 页面必须能区分“盘后研究依据”“盘中预览触发状态”和“历史回放结果”。
5. 个股详情里的量价状态读取 `/api/v1/stocks/{symbol}/price-volume-analysis`，只展示后端给出的买点状态、理由和风险。
6. 盘中监控状态读取 `/api/v1/preview/watchlist`，必须明确标注其为 preview / 非 READY / 不用于回测。

## File Organization

建议采用 feature-first 组织，而不是一个巨大的 components 目录。
