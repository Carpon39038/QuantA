# M7 Real Sync And Reliability Progress

## Current State

QuantA 已经从“阶段化流水线”进一步推进到“带 source-backed sync 和可靠性护栏的流水线”。`daily_sync` 现在会生成新的 `raw_snapshot` 和 `BUILDING` 发布快照，后续由 `daily_screener`、`daily_backtest` 推进到 `READY`；queue 也已经带 retry/backoff、alerts 和 resident scheduler。

## Last Completed

1. 新增 `market_data_source` provider 抽象，默认读取 `backend/app/fixtures/source_snapshots/`，并接入 `akshare` 作为既定真实数据源之一的 provider。
2. 新增 `backend/app/domains/market_data/sync.py`，让 `daily_sync` 走真正的 source-backed snapshot 同步，而不是继续直接重放静态 publish fixture。
3. 为 service/backtest durable queue 增加 `retry_count`、`max_retries`、`next_attempt_at`、`last_error`，并让 worker 在失败时执行指数 backoff 重试。
4. 新增本地 alerts sink、`/api/v1/system/alerts`、runtime alert count，以及 `scripts/pipeline_smoke.py` 来覆盖 success path 和 retry path。
5. 修正 `akshare` provider 在“今天无数据”时会误生成空快照的问题，改成先探测真实最近可用交易日，并在 0 条日线时直接失败。
6. 更新 README、HARNESS、RELIABILITY、QUALITY SCORE 和 tech debt，让后续 agent 可以直接从仓库理解当前可靠性基线，以及外部网络依赖边界。

## Verification

1. `scripts/init_dev.sh`
2. `scripts/smoke.sh`
3. `python3 scripts/pipeline_smoke.py`
4. `python3 scripts/check_harness_docs.py`
5. `python3 scripts/check_execution_harness.py --require-all-passing`

## Next Step

继续沿 1.0 主线推进真实外部 provider 产品化：补 source schema 校验与历史回补、把本地 alerts 接到远端通知，并升级到浏览器级 UI smoke。当前机器上 AKShare 历史日线这条 live fetch 仍被外部网络/代理链路或其上游公开接口状态阻塞，不是仓库内代码阻塞。
