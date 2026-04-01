# M7 Real Sync And Reliability

## Goal

把 QuantA 的日终流水线从“deterministic bootstrap + 手动编排”推进成“source-backed sync + 最小可靠性护栏”的可持续开发底座。

## Scope

本计划聚焦：

1. 为 market data 增加 source provider 抽象，默认接入可复现的 `fixture_json` source snapshot，并落地 `akshare` 作为既定真实数据源之一的 provider 实现。
2. 把 `daily_sync` 升级为真正的 source-backed sync，写入新的 `raw_snapshot` 与 `artifact_publish(status=BUILDING)`，再由后续阶段推进到 `READY`。
3. 为 service queue 和 backtest queue 增加 `retry/backoff` 语义，包括 `retry_count`、`max_retries`、`next_attempt_at` 和 `last_error`。
4. 增加本地 alerts sink、`/api/v1/system/alerts` 和 runtime alert count，让失败不再只留在 worker stdout。
5. 增加 resident scheduler loop 与 `pipeline_smoke`，验证 success path 和 retry path。
6. 把新的运行参数、质量口径和技术债写回系统记录。

## Non-Goals

本计划不包含：

1. 真正的远端通知通道，例如企业微信、邮件或 PagerDuty。
2. 覆盖全市场、全历史回补的正式同步作业。
3. 完整产品化的 source schema 演进与字段漂移监控。
4. 浏览器级任务面板和实时进度流。

## Done When

1. `daily_sync` 能从 source provider 生成新的 `raw_snapshot` 和 `BUILDING` 发布快照，而不是只重放静态 seed。
2. scheduler 能自动把新的 source-backed snapshot 从 `BUILDING` 推进到 `READY`。
3. service/backtest worker 失败时会执行 retry/backoff；耗尽重试后会写 alerts。
4. backend 能通过 `system health` 和 `system alerts` 暴露最小可靠性状态。
5. `scripts/pipeline_smoke.py` 与 `scripts/smoke.sh` 能覆盖 success path、retry path 和 alerts 基线。

## Verify By

1. `scripts/init_dev.sh`
2. `scripts/smoke.sh`
3. `python3 scripts/pipeline_smoke.py`
4. `python3 scripts/check_harness_docs.py`
5. `python3 scripts/check_execution_harness.py --require-all-passing`

## Tasks

- [x] 增加 source provider 抽象与 `fixture_json` source snapshot 输入
- [x] 增加 `akshare` provider 实现和可配置 source env
- [x] 把 `daily_sync` 升级为 `BUILDING -> READY` 的 source-backed sync
- [x] 为 service/backtest queue 增加 retry/backoff 元数据和 worker 重试逻辑
- [x] 增加 alerts JSONL、`/api/v1/system/alerts` 与 runtime alert count
- [x] 增加 resident scheduler loop 和 `scripts/pipeline_smoke.py`
- [x] 把新的状态写回 README、HARNESS、RELIABILITY、QUALITY 和 tech debt

## Decisions

1. M7 先用 `fixture_json` 作为已验证的 source provider，保证离线可复现；同时落地 `akshare` 作为既定真实数据源之一的 market provider。
2. `daily_sync` 只负责把 source snapshot 规范化成新的 `raw_snapshot` 和前半段产物，发布门禁交给 `artifact_publish(status=BUILDING)`。
3. retry/backoff 状态优先记录在 durable queue item 中，数据库表继续负责 run/request 的业务状态，而不是反过来驱动队列。
4. alerts 先落本地 JSONL 和 HTTP 读取接口，先把失败可见性固定下来，再接远端通知。

## Status

当前状态：M7 已完成。QuantA 现在具备 source-backed sync、BUILDING -> READY 发布门禁、retry/backoff、alerts 和 resident scheduler 的最小可靠性闭环；AKShare 作为既定真实数据源之一也已接入并修正了“空快照”语义，但 live fetch 仍取决于当前机器的外部网络/代理环境以及其上游公开接口状态。下一步应继续推进真实外部 provider 产品化、全量历史回补和浏览器级验收。
