# M21 History Coverage Targeting For Corporate Actions Progress

## Completed

1. `backend.app.domains.market_data.sync` 新增 `resolve_source_backfill_window(...)` 和 `--lookback-open-days`，现在可以按最新 source biz date 自动解析滚动回补窗口，而不必手工算 `start_biz_date/end_biz_date`。
2. `history_backfill` 的 queue / worker / API 现已支持 `lookback_open_days`；`POST /api/v1/tasks/history-backfill/run` 可以直接传滚动窗口大小。
3. scheduler 新增 `QUANTA_HISTORY_BACKFILL_TARGET_OPEN_DAYS` 语义：当 source 已追平但历史覆盖不足时，pipeline 仍会把系统视为未 settled，并优先 enqueue `history_backfill` 扩历史覆盖。
4. `/api/v1/system/health` 现在会返回最新 READY snapshot 的 `history_coverage`，包括：
   - `start_biz_date`
   - `end_biz_date`
   - `open_day_count`
5. `corporate_action` reconciliation 新增 coverage 诊断字段：
   - `coverage_start_biz_date`
   - `coverage_end_biz_date`
   - `nearest_out_of_coverage_event_date`
6. `scripts/tushare_live_backfill_smoke.py` 现会输出：
   - `lookback_open_days`
   - `history_coverage`
   - `corporate_action_check`

## Verification

1. `env PYTHONPYCACHEPREFIX=/tmp/quanta-pycache python3 -m py_compile backend/app/app_wiring/settings.py backend/app/api/dev_server.py backend/app/domains/market_data/sync.py backend/app/domains/tasking/queue.py backend/app/domains/tasking/service_runner.py backend/app/domains/tasking/worker.py backend/app/domains/tasking/scheduler.py backend/app/domains/market_data/repo.py scripts/market_data_backfill_smoke.py scripts/tushare_live_backfill_smoke.py`
2. `python3 scripts/market_data_backfill_smoke.py`
3. `scripts/smoke.sh`
4. live `QUANTA_LIVE_BACKFILL_OPEN_DAYS=10 python3 scripts/tushare_live_backfill_smoke.py`

## Live Result

2026-04-08 在 `QUANTA_SOURCE_PROVIDER=tushare`、`QUANTA_SOURCE_UNIVERSE=core_operating_40`、`QUANTA_SOURCE_VALIDATION_PROVIDERS=none`、`QUANTA_DISCLOSURE_PROVIDER=none` 环境下：

1. `QUANTA_LIVE_BACKFILL_OPEN_DAYS=10 python3 scripts/tushare_live_backfill_smoke.py` 返回：
   - `latest_biz_date = 2026-04-08`
   - `history_coverage.open_day_count = 10`
   - `history_coverage.start_biz_date = 2026-03-25`
   - `history_coverage.end_biz_date = 2026-04-08`
   - `raw_snapshot_count = 10`
   - `corporate_action_count = 7464`
2. 在 10 个 open days 的覆盖下，`corporate_action_check` 仍是：
   - `status = SKIPPED`
   - `checked_action_count = 0`
   - `out_of_coverage_count = 607`
   - `nearest_out_of_coverage_event_date = 2026-02-12`
3. 随后重试 `QUANTA_LIVE_BACKFILL_OPEN_DAYS=40 QUANTA_LIVE_BACKFILL_SKIP_RERUN=1 python3 scripts/tushare_live_backfill_smoke.py`，返回：
   - `history_coverage.open_day_count = 40`
   - `history_coverage.start_biz_date = 2026-02-03`
   - `history_coverage.end_biz_date = 2026-04-08`
   - `corporate_action_check.status = OK`
   - `checked_action_count = 3`
   - `aligned_action_count = 3`
   - `out_of_coverage_count = 604`
   - `nearest_out_of_coverage_event_date = 2026-01-29`
4. 这说明长窗口能力已经不只是“会补历史”，而是真正把 `corporate_action` reconciliation 从 `SKIPPED` 推进到了非零 `checked/aligned`；下一步要做的是继续把窗口往 `2026-01-29` 之前推进，而不是继续证明这条能力存在。

## Next

1. 该里程碑解决的是“如何正式维护更长历史覆盖窗口”；继续把窗口精确推进到具体起始日、消掉边界缺口的后续工作已转入 `2026-04-08-m22-target-start-date-backfill-convergence`。
2. `QUANTA_HISTORY_BACKFILL_TARGET_OPEN_DAYS=40` 现在已经足够作为最小 live 运营基线，而更深覆盖则开始由显式 `target_start_biz_date` 驱动。
