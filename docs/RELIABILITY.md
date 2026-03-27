# Reliability Notes

## First Reliability Goals

v1.0 可靠性重点不是高并发，而是稳定完成每日盘后链路。

## Reliability Invariants

1. 盘后任务必须可重跑。
2. 同一天重复执行不应产生不可解释的重复结果。
3. 查询只读已发布快照，避免读到半成品。
4. 每次任务都要留下 run log 和失败原因。
5. 回测必须绑定快照和策略版本，避免“结果漂移”。

## Planned Operational Signals

1. 最近一次 `raw_snapshot_id` 生成时间
2. 最近一次 `snapshot_id` 发布时间
3. 数据更新成功率
4. 关键任务耗时
5. 失败重试次数

## Known Risks

1. 外部数据源字段漂移
2. 单机 DuckDB 读写争用
3. 复权和涨跌停规则实现错误
4. 回测成交假设过于理想化

## Guardrail Direction

后续优先把这些风险编码成检查：

1. 数据质量校验
2. 快照发布前验收
3. 样例回测回放测试
4. 任务失败告警
