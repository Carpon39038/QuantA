# QuantA Operations Runbook

## Goal

这份 runbook 面向“盘后无人值守生成次日盘中监控计划，并在盘中持续检查触发状态”的第一版。

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

`scripts/ops_entrypoint.sh` 会优先使用 `QUANTA_PYTHON_BIN`，否则自动寻找一个能 `import duckdb` 的 `python3`。这是为了避免 macOS launchd 的精简 PATH 或 Homebrew Python 升级后命中缺少项目依赖的解释器。若本机有多个 Python，建议在 `data/env/live.env` 显式设置：

```bash
QUANTA_PYTHON_BIN=/Applications/Xcode.app/Contents/Developer/usr/bin/python3
```

live entrypoint 启动 backend 时默认设置 `QUANTA_BACKEND_SKIP_BOOTSTRAP=1`，避免 backend 重启时和 pipeline 单写者抢 DuckDB 写锁。需要重建 schema 或 fixture 时，先停 live pipeline，或显式运行 `scripts/init_dev.sh` / domain bootstrap 命令，再启动服务。

live runtime 默认日志路径取决于 `QUANTA_RUNTIME_DATA_DIR`。如果按 `ops/live.env.example` 使用 `QUANTA_RUNTIME_DATA_DIR=data/live`，核心路径是：

1. DuckDB：`data/live/duckdb/quanta.duckdb`
2. runtime alerts：`data/live/logs/alerts.jsonl`
3. resident scheduler JSONL：`data/live/logs/pipeline-daemon.jsonl`
4. launchd stdout/stderr：`data/logs/launchd-*.stdout.log` 与 `data/logs/launchd-*.stderr.log`

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
curl -s http://127.0.0.1:8765/api/v1/preview/watchlist
```

如果你按 `ops/live.env.example` 安装了 live runtime，对应健康检查地址会变成：

```bash
curl -s http://127.0.0.1:18765/api/v1/system/health
curl -s http://127.0.0.1:18765/api/v1/system/alerts
curl -s http://127.0.0.1:18765/api/v1/runtime
curl -s http://127.0.0.1:18765/api/v1/preview/watchlist
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

## 2026-07-03 Local Launchd Verification

本机已安装并运行三个 launchd label：

1. `com.quanta.backend`
   监听 `127.0.0.1:18765`
2. `com.quanta.frontend`
   监听 `127.0.0.1:24173`
3. `com.quanta.pipeline`
   常驻 scheduler，JSONL 写入 `data/live/logs/pipeline-daemon.jsonl`

验证命令：

```bash
launchctl print gui/501/com.quanta.backend
launchctl print gui/501/com.quanta.frontend
launchctl print gui/501/com.quanta.pipeline
curl -s http://127.0.0.1:18765/health
curl -s http://127.0.0.1:18765/api/v1/system/health
curl -s http://127.0.0.1:18765/api/v1/system/alerts
curl -s http://127.0.0.1:18765/api/v1/runtime
curl -s http://127.0.0.1:18765/api/v1/preview/watchlist
bash scripts/ops_entrypoint.sh doctor
```

2026-07-03 验证结果：

1. launchd 三个 label 均为 `state = running`。
2. pipeline 最近 tick 持续写入 `data/live/logs/pipeline-daemon.jsonl`，最近状态为 `settled=true`，`pipeline.reason=source_not_newer`。
3. backend `/health` 返回 `ok`，最新 READY 为 `snapshot_2026-07-02_ready_061`。
4. `/api/v1/system/health.status=ok`，`source_latest_biz_date=2026-07-02` 与 READY snapshot 持平，history coverage 为 `2025-12-08 -> 2026-07-02`，共 136 个 open days。
5. `/api/v1/preview/watchlist` 可读取盘中预览，`source_status.status=ok`，provider 为 `tushare_realtime`。
6. `bash scripts/ops_entrypoint.sh doctor` 在 `--require-http --require-fresh-pipeline-log --fail-on-alert` 口径下完成了真实检查；DB health、source freshness、backend HTTP 和 pipeline JSONL 均通过，但 hard gate 仍失败，因为最近 50 条 alerts 中有 26 条 error 级告警：24 条历史 `scheduler_loop_failure` 和 2 条 `intraday_stop_loss_triggered`。
7. 修复 entrypoint 后执行过 `launchctl kickstart -k gui/501/com.quanta.pipeline/backend/frontend`。重启后三个 label 重新进入 `running`；backend 由 `QUANTA_BACKEND_SKIP_BOOTSTRAP=1` 只读启动并监听 `127.0.0.1:18765`；frontend 监听 `127.0.0.1:24173`；pipeline tick 重新从 `tick_no=1` 开始写入并保持 `settled=true`。
8. kickstart 后再次运行 hard gate：backend HTTP、source freshness、open queue、history coverage 与 pipeline JSONL 均通过；最终失败项仍是同一个 `recent_error_alerts=26`。

当前结论：live supervisor 与盘中/盘后常驻链路已能运行并进入 settled；无人值守硬门禁的阻塞点不是服务启动，而是 alert hygiene。下一步需要区分运维错误、交易触发和历史已确认告警，再决定 `--fail-on-alert` 的清理窗口或确认机制。

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
