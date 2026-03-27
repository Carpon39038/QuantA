# Frontend Notes

## Frontend Role

前端负责消费“已发布快照”的稳定视图，不直接参与复杂计算。

## Planned Views

1. 市场概览页
2. 个股详情页
3. 选股结果页
4. 回测报告页

## Frontend Constraints

1. 默认只读取 `READY snapshot_id`。
2. 所有图表都要展示口径和时间范围。
3. 展示层尽量复用后端聚合结果，避免浏览器重复推导核心指标。
4. 页面必须能区分“最新结果”和“历史回放结果”。

## File Organization

建议采用 feature-first 组织，而不是一个巨大的 components 目录。
