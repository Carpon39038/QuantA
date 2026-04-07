# Reliability Notes

## First Reliability Goals

v1.0 可靠性重点不是高并发，而是稳定完成每日盘后链路。

## Reliability Invariants

1. 盘后任务必须可重跑。
2. 同一天重复执行不应产生不可解释的重复结果。
3. 查询只读已发布快照，避免读到半成品。
4. 每次任务都要留下 run log 和失败原因。
5. 回测必须绑定快照和策略版本，避免“结果漂移”。
6. `daily_sync` 产生的 source-backed snapshot 在 `screener/backtest` 完成前必须保持 `BUILDING`，不能被查询侧当成最终发布结果。

## Planned Operational Signals

1. 最近一次 `raw_snapshot_id` 生成时间
2. 最近一次 `snapshot_id` 发布时间
3. 数据更新成功率
4. 关键任务耗时
5. 失败重试次数

## Current Guardrails

1. `daily_sync` 会先写 `raw_snapshot` 与 `artifact_publish(status=BUILDING)`，再由 `daily_screener`、`daily_backtest` 逐步把产物状态推进到 `READY`。
2. service queue 与 backtest queue 都带 `retry_count`、`max_retries`、`next_attempt_at`、`last_error`，worker 会按指数 backoff 重试。
3. 重试耗尽时会把失败写入 `data/logs/alerts.jsonl`，并通过 `/api/v1/system/alerts` 暴露最近告警。
4. `domains.tasking.scheduler` 既能跑有限 tick 的 pipeline，也能以 resident loop 方式持续轮询。
5. `scripts/pipeline_smoke.py` 会在临时 runtime 验证成功路径和 retry 路径，避免把失败恢复逻辑只留在对话里。
6. `market_data.sync --start-biz-date/--end-biz-date` 已支持最小历史回补，并默认跳过已存在的 `biz_date`，避免重复生成同日 source-backed 快照。
7. scheduler 在 source provider 明显领先于最新 READY snapshot 时，会优先 enqueue `history_backfill`，并由 service worker 把回补出的历史 snapshot 继续推进到 `READY`，避免遗留多条悬空 `BUILDING` 快照。
8. 官方披露现已作为独立 sidecar 接入 `official_disclosure_item`；`fixture_json` 开发链走本地 fixture，live 环境默认走 CNInfo 官方检索页与 stock lookup JSON，不再把披露信息混入 canonical 日线 provider 本体。
9. `tushare` canonical sync 现在会在白天自动回退到最近一个真正有日线的交易日，而不是只依据 `trade_cal` 判断“今天开市”后直接失败。
10. `shadow_validation` 已接入 `akshare` 与 `baostock` 两条补充源，会把 `open/high/low/close/pre_close/volume/amount` 的逐股对比结果写入 `source_watermark_json`，并经 `/api/v1/snapshot/latest` 与 `/api/v1/system/health` 暴露。

## Known Risks

1. 真实外部数据源字段漂移和限流仍可能让 `akshare` 或 `baostock` 的补充校验失效；当前实测 `akshare` 在更大研究池上仍会受 Eastmoney 上游链路波动影响。
2. 单机 DuckDB 读写争用仍需要靠“单写者优先”和顺序 smoke 避免。
3. 当前 source-backed sync 虽已支持更大默认研究池、最小历史回补、CNInfo 公告元数据 sidecar、多字段 shadow validation 与调度面接线，但还没有覆盖全市场、复权修复、企业行为修正和自动化长期补数策略。
4. 官方披露目前还是 metadata-first，尚未纳入公告正文、交易所问询、回复函和跨源去重策略。
5. 回测成交假设仍偏理想化，尚未引入更真实的滑点和撮合约束。

## Guardrail Direction

后续优先把这些风险编码成检查：

1. 数据质量校验
2. source provider 字段标准化与 schema 断言
3. 快照发布前验收
4. 样例回测回放测试
5. 本地 alerts 到远端通知通道的桥接
