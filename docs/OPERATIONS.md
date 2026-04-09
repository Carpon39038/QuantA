# QuantA Operations Runbook

## Goal

这份 runbook 面向“盘后无人值守跑起来”的第一版。

当前推荐把 QuantA 拆成三个常驻入口：

1. backend API / dev server
2. frontend workbench / dev server
3. pipeline daemon

其中 pipeline daemon 已经包含 scheduler、service queue worker 和 backtest queue worker；不需要再额外常驻一个 worker 进程。

## Local Fixture Start

用于开发和演练：

```bash
scripts/init_dev.sh
pnpm run pipeline:once
pnpm run backend:dev
pnpm run frontend:dev
```

如果要演练常驻调度：

```bash
QUANTA_SCHEDULER_POLL_INTERVAL_SECONDS=5 pnpm run pipeline:daemon
```

`pipeline:daemon` 每个 tick 输出一行 JSON。重点看这些字段：

1. `event`
   `scheduler_tick` 表示一次轮询，`scheduler_loop_finished` 只会在有限 iterations 的测试模式里出现。
2. `pipeline.enqueued`
   非空表示本 tick 排入了 `history_backfill/daily_sync/daily_screener/daily_backtest` 之一。
3. `service_worker.processed`
   大于 0 表示 service task 已被消费。
4. `backtest_worker.processed`
   大于 0 表示手动 backtest request 已被消费。
5. `error`
   非空表示 tick 级调度失败；daemon 默认会写 alert 并继续轮询。
6. `settled`
   `true` 表示当前 source、queue、BUILDING snapshot 和历史覆盖目标已经暂时追平。

## Live Runtime Start

第一版 live 运行至少需要显式设置 canonical source 和 token：

```bash
export QUANTA_SOURCE_PROVIDER=tushare
export QUANTA_TUSHARE_TOKEN='***'
export QUANTA_SOURCE_UNIVERSE=core_operating_40
export QUANTA_HISTORY_BACKFILL_TARGET_START_BIZ_DATE=auto
export QUANTA_HISTORY_BACKFILL_TARGET_OPEN_DAYS=80

pnpm run backend:dev
pnpm run frontend:dev
pnpm run pipeline:daemon
```

正式 runtime 前，建议先跑一次隔离 canary：

```bash
export QUANTA_SOURCE_PROVIDER=tushare
export QUANTA_TUSHARE_TOKEN='***'
export QUANTA_SOURCE_UNIVERSE=core_research_12
pnpm run pipeline:canary
```

`pipeline:canary` 会创建临时 runtime、bootstrap seed、用 resident scheduler 跑有限 tick，再输出 latest snapshot、health、alerts、task logs 和 scheduler JSONL 摘要。默认不保留临时库；需要排障时可加：

```bash
QUANTA_PIPELINE_CANARY_KEEP_RUNTIME=1 pnpm run pipeline:canary
```

2026-04-09 的第一轮 live canary 结果：

1. 配置：`tushare + core_research_12 + QUANTA_SOURCE_VALIDATION_PROVIDERS=none + QUANTA_DISCLOSURE_PROVIDER=none`
2. 调度：resident scheduler 4 ticks，第一 tick 自动 enqueue 并完成 `history_backfill`
3. 结果：最新 READY snapshot 到 `2026-04-09`
4. 数据：`raw_snapshot=10`、`artifact_publish=3`、`fundamental_feature_daily=12`、`corporate_action_item=317`
5. 健康：`/api/v1/system/health.status=ok`、`alerts=0`

`QUANTA_HISTORY_BACKFILL_TARGET_START_BIZ_DATE=auto` 会优先消费 health payload 里的下一次建议目标；如果 recommendation 暂时不存在，则回退到 `QUANTA_HISTORY_BACKFILL_TARGET_OPEN_DAYS`。

## Health Checks

本机默认：

```bash
pnpm run ops:doctor
curl -s http://127.0.0.1:8765/api/v1/system/health
curl -s http://127.0.0.1:8765/api/v1/system/alerts
curl -s http://127.0.0.1:8765/api/v1/runtime
```

如果想让 doctor 顺手请求 live source 并检查最新 READY 是否落后：

```bash
python3 scripts/ops_doctor.py --live-source
```

盘后运行的最低验收：

1. `/api/v1/system/health.status` 是 `ok`。
2. 最新 READY snapshot 的 `biz_date` 等于预期 source 交易日。
3. `history_coverage.start_biz_date` 不晚于你的运行目标。
4. `history_coverage.recommended_target_start_biz_date` 要么为空，要么被下一轮 daemon 解析进 runtime 的 `resolved_history_backfill_target_start_biz_date`。
5. `/api/v1/system/alerts` 没有新的 `error` 级 alert。
6. 最新 screener 和 backtest payload 的 `snapshot_id` 与最新 READY snapshot 一致。

## Backfill Deepening

隔离 live 验证用：

```bash
QUANTA_SOURCE_PROVIDER=tushare \
QUANTA_TUSHARE_TOKEN='***' \
QUANTA_LIVE_BACKFILL_TARGET_START_BIZ_DATE=2025-12-15 \
QUANTA_LIVE_BACKFILL_SKIP_RERUN=1 \
python3 scripts/tushare_live_backfill_smoke.py
```

正式 runtime 追深用 daemon，不建议直接在生产库上反复跑隔离 smoke。

长窗口回补的默认运维口径：

1. queue / worker 的 `history_backfill` 使用 latest artifact 模式。
2. 中间历史日只写 raw facts。
3. 窗口终点会重建一次完整 artifact。
4. 如果终点 artifact 的 price history 已覆盖目标起点，rerun 应保持 no-op。

## Failure Handling

daemon 有两层恢复：

1. task-level 失败
   queue worker 会按 `QUANTA_TASK_MAX_RETRIES` 与 `QUANTA_TASK_RETRY_BACKOFF_SECONDS` 重试；耗尽后写 alert。
2. tick-level 失败
   resident scheduler 默认写 `scheduler_loop_failure` alert，并在下一个 poll 继续运行。

如果你希望排障时 fail-fast：

```bash
python3 -m backend.app.domains.tasking.scheduler \
  --daemon \
  --auto-pipeline \
  --stream-ticks \
  --stop-on-error
```

## Stop

开发机上用 `Ctrl-C` 停止 daemon。

如果停在 `BUILDING` snapshot 或 pending queue 中间，不要手动删库；优先重新启动 `pnpm run pipeline:daemon`，让 worker 继续推进或进入 retry / alert 路径。
