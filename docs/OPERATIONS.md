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
   `scheduler_tick_started` 表示 resident loop 已开始本轮轮询；`scheduler_tick` 表示一次轮询已完成；`scheduler_loop_finished` 只会在有限 iterations 的测试模式里出现。
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

同一份 JSONL tick 也会追加到 runtime 的 `logs/pipeline-daemon.jsonl`；默认本机路径是 `data/logs/pipeline-daemon.jsonl`。该文件按 10 MiB 触发本地轮转，保留 5 份 `pipeline-daemon.jsonl.N` 备份。

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

如果准备用 macOS launchd 守护进程，先准备本机 env 文件：

```bash
mkdir -p data/env data/logs
cp ops/live.env.example data/env/live.env
chmod 600 data/env/live.env
```

然后编辑 `data/env/live.env` 写入真实 token。本仓库只提供 `ops/live.env.example`，不要把真实 `data/env/live.env` 提交。

`ops/live.env.example` 默认把 live 端口放到较少冲突的高位端口：backend `18765`，frontend `24173`。
同时它会把 live runtime 单独落到 `data/live/`，避免和默认开发用的 `data/duckdb/quanta.duckdb` 混在一起。

launchd 模板位于 `ops/launchd/`；三个服务分别是 `com.quanta.pipeline`、`com.quanta.backend` 和 `com.quanta.frontend`。模板统一调用 `bash scripts/ops_entrypoint.sh <service>`，入口脚本会加载 `data/env/live.env`，并在 pipeline 启动前执行最小 schema bootstrap。

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
pnpm run ops:after-close
curl -s http://127.0.0.1:8765/api/v1/system/health
curl -s http://127.0.0.1:8765/api/v1/system/alerts
curl -s http://127.0.0.1:8765/api/v1/runtime
```

如果你按 `ops/live.env.example` 安装了 live runtime，对应健康检查地址会变成：

```bash
curl -s http://127.0.0.1:18765/api/v1/system/health
curl -s http://127.0.0.1:18765/api/v1/system/alerts
curl -s http://127.0.0.1:18765/api/v1/runtime
```

如果想让 doctor 顺手请求 live source 并检查最新 READY 是否落后：

```bash
python3 scripts/ops_doctor.py --live-source
```

如果 backend 和 pipeline daemon 已经常驻，并且想把 warning 也收紧成硬失败：

```bash
python3 scripts/after_close_check.py \
  --live-source \
  --require-http \
  --require-fresh-pipeline-log \
  --fail-on-alert
```

`after_close_check.py` 会汇总 `ops_doctor`、backend `/health`、`data/logs/pipeline-daemon.jsonl` 最后一条事件和日志年龄。

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
3. launchd / 进程重启后遗留的 `queue/*/processing/*.json`
   daemon / worker 启动时会自动把这类 orphaned item 回收到 `pending`，并写 `service_queue_processing_recovered` 或 `backtest_queue_processing_recovered` warning alert。

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
