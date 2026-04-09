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
3. 重试耗尽时会把失败写入 runtime-local `logs/alerts.jsonl`，并通过 `/api/v1/system/alerts` 暴露最近告警。
4. `domains.tasking.scheduler` 既能跑有限 tick 的 pipeline，也能以 resident loop 方式持续轮询。
4.1. `pnpm run pipeline:daemon` 是本机第一版常驻流水线入口；resident scheduler 每个 tick 会输出一行 JSON，并把同一份 JSONL 追加到 `data/logs/pipeline-daemon.jsonl`。tick-level 异常会写 `scheduler_loop_failure` alert 后继续轮询。完整启动、launchd 示例、健康检查、追深回补和停机口径见 `docs/OPERATIONS.md`。
4.2. `pnpm run pipeline:canary` 会在隔离 runtime 里 bootstrap seed、跑有限次 resident scheduler、汇总 scheduler events / latest snapshot / system health / alerts / task logs；2026-04-09 的 live canary 使用 `tushare + core_research_12 + no shadow/disclosure` 跑通了 resident daemon catch-up，自动把最新 READY 推到 `2026-04-09`，写出 `raw_snapshot=10/artifact_publish=3/fundamental_feature_daily=12/corporate_action_item=317`，且 `alerts=0`。
4.3. `pnpm run ops:after-close` 会汇总 DB-level doctor、backend `/health` 和 pipeline JSONL log；常驻进程已经启动时，可以加 `--require-http --require-fresh-pipeline-log --fail-on-alert` 把 warning 收紧成盘后硬门禁。
5. `scripts/pipeline_smoke.py` 会在临时 runtime 验证成功路径和 retry 路径，避免把失败恢复逻辑只留在对话里。
6. `market_data.sync --start-biz-date/--end-biz-date` 已支持最小历史回补，并默认跳过已存在的 `biz_date`，避免重复生成同日 source-backed 快照；CLI 仍可用 `--artifact-mode all` 逐日发布，也可用 `--artifact-mode latest` 只发布窗口终点。
7. scheduler 在 source provider 明显领先于最新 READY snapshot 时，会优先 enqueue `history_backfill`；queue/worker 的 `history_backfill` 当前使用 latest artifact 模式：中间历史日只 ingest `raw_snapshot + daily_bar`，窗口终点才发布完整 `artifact_publish/price_series_daily/analysis/screener/backtest`，避免长窗口把全量 price series 按天重复重建。
8. `history_backfill` 现在同时支持 `lookback_open_days` 与 `target_start_biz_date`；`market_data.sync --lookback-open-days N`、`market_data.sync --target-start-biz-date YYYY-MM-DD`、`POST /api/v1/tasks/history-backfill/run` 和 queue/worker 都可以按最新 source biz date 自动解析滚动回补窗口，或直接把覆盖推进到指定起始日期；若目标终点已有 artifact 且 price series 覆盖已满足目标起点，latest 模式会保持 no-op，不会再发布一条同日快照。
9. 当 `QUANTA_HISTORY_BACKFILL_TARGET_OPEN_DAYS > 0` 或 `QUANTA_HISTORY_BACKFILL_TARGET_START_BIZ_DATE` 被设置时，scheduler 即使在 source 已追平后，也会把“历史覆盖不足”视为未 settled，并继续 enqueue `history_backfill` 扩最新 READY snapshot 的历史窗口；其中 `QUANTA_HISTORY_BACKFILL_TARGET_START_BIZ_DATE=auto` 会优先消费最新 `history_coverage.recommended_target_start_biz_date`，只有 recommendation 缺失时才回退到 `target_open_days`。
10. 官方披露现已作为独立 sidecar 接入 `official_disclosure_item`；`fixture_json` 开发链走本地 fixture，live 环境默认走 CNInfo 官方检索页与 stock lookup JSON，不再把披露信息混入 canonical 日线 provider 本体。
11. `tushare` canonical sync 现在会在白天自动回退到最近一个真正有日线的交易日，而不是只依据 `trade_cal` 判断“今天开市”后直接失败。
12. `shadow_validation` 已接入 `akshare` 与 `baostock` 两条补充源，会把 `open/high/low/close/pre_close/volume/amount/adj_factor` 的逐股对比结果写入 `source_watermark_json`，并经 `/api/v1/snapshot/latest` 与 `/api/v1/system/health` 暴露。
13. canonical source 现在还会在 sync 时执行 `adj_factor` 覆盖率、板块涨跌停规则、停牌标记一致性，以及 `corporate_action_item + price_series_daily` 的企业行为 reconciliation 自检；若补充源降级或 canonical quality check 报警，会直接写 runtime-local alerts。
14. 企业行为 sidecar 现已作为独立 `corporate_action_item` 接入：`tushare.dividend` 会先按 `knowledge_date <= biz_date` 做 as-of 过滤，再落到 snapshot 绑定表中，避免未来已知的分红送配事件泄漏进历史回测语义。
14.1. `tushare.dividend` 的上游原始结果会在 provider 进程内按 symbol 缓存；同一次长窗口回补中，每只股票只需要拉一次完整分红送配结果，再由本地 as-of 过滤生成各日期的 snapshot sidecar。`scripts/market_data_backfill_smoke.py` 已覆盖这个调用次数约束。
14.2. latest artifact 回补模式会把中间历史日标记为 source-only raw ingest，并在 `source_watermark_json.artifact_mode` 中记录 `source_only`；这些中间日不抓官方披露 / 企业行为 / shadow validation，相关 sidecar 与企业行为 reconciliation 延迟到窗口终点 artifact 统一执行。
15. 对落在当前价格历史覆盖范围内的企业行为，reconciliation 会检查事件日前后 `adj_factor` 是否发生变化；若事件日早于当前覆盖窗口，则明确记为 `out_of_coverage`，并额外暴露 `coverage_start_biz_date/coverage_end_biz_date/nearest_out_of_coverage_event_date` 帮助继续扩深回补窗口。2026-04-08 的 live 验证里，这条链已先在 40 个 open days 的覆盖下首次进入非零 `checked/aligned`，随后再通过显式 `target_start_biz_date` 把覆盖推进到 `2026-01-20`，把企业行为校验提升到 `checked=5/aligned=5/boundary_gap=0`；2026-04-09 继续推进到 `2026-01-15` 后，live 结果已到 `checked=6/aligned=6/boundary_gap=0`，最近未覆盖事件前移到 `2025-12-19`；继续推到 `2025-12-18` 后，系统明确暴露了新的 `boundary_gap=1` 和 `nearest_out_of_coverage_event_date=2025-12-16`；最终把目标提前到 `2025-12-15` 后，live 结果已到 `checked=9/aligned=9/boundary_gap=0`，最近未覆盖事件前移到 `2025-11-18`。
16. `/api/v1/system/health` 现在会返回最新 READY snapshot 的 `history_coverage`，其中还包含 `recommended_target_start_biz_date`、`recommendation_reason` 与 `recommendation_anchor_biz_date`；`/api/v1/runtime` 还会额外暴露 `resolved_history_backfill_target_start_biz_date`，帮助确认 `auto` 当前实际采用的回补起点。workbench 当前也会直接读取 `/api/v1/system/alerts` 并展示最近 alerts、provider incident 摘要和建议的下一次回补起点，降级信号与补数建议不再只存在本地 JSONL 文件或终端输出里。

## Known Risks

1. 真实外部数据源字段漂移和限流仍可能让 `akshare` 或 `baostock` 的补充校验失效；当前实测 `akshare` 在更大研究池上仍会受 Eastmoney 上游链路波动影响，而 `baostock` 的 `adj_factor` 在部分老股票上与 Tushare 存在语义基准差异。
2. 单机 DuckDB 读写争用仍需要靠“单写者优先”和顺序 smoke 避免。
3. 当前 source-backed sync 虽已支持更大默认研究池、最小历史回补、CNInfo 公告元数据 sidecar、企业行为 sidecar、企业行为 reconciliation、canonical quality checks、多字段 shadow validation 与调度面接线，但还没有覆盖全市场、完整企业行为修正和自动化长期补数策略。
4. 官方披露目前还是 metadata-first，尚未纳入公告正文、交易所问询、回复函和跨源去重策略。
5. 回测成交假设仍偏理想化，尚未引入更真实的滑点和撮合约束。

## Guardrail Direction

后续优先把这些风险编码成检查：

1. 数据质量校验
2. source provider 字段标准化与 schema 断言
3. 快照发布前验收
4. 样例回测回放测试
5. 本地 alerts 到远端通知通道的桥接
6. 企业行为长期回溯与复权基准核对
