# M22 Target Start Date Backfill Convergence Progress

## Completed

1. `backend.app.domains.market_data.sync` 新增 `resolve_source_backfill_window_to_start_date(...)` 与 `--target-start-biz-date`，现在可以直接指定“至少补到哪一天”，而不必继续把未覆盖事件日手算成 `open_day_count`。
2. `history_backfill` 的 queue / worker / service path / HTTP API 已支持 `target_start_biz_date`；`POST /api/v1/tasks/history-backfill/run` 现在可以直接传具体起始日。
3. scheduler 新增 `QUANTA_HISTORY_BACKFILL_TARGET_START_BIZ_DATE` 语义，并定义其优先级高于 `QUANTA_HISTORY_BACKFILL_TARGET_OPEN_DAYS`，这样 live runtime 可以直接围绕最近未覆盖事件日继续向前收敛。
4. `scripts/tushare_live_backfill_smoke.py` 现在支持 `QUANTA_LIVE_BACKFILL_TARGET_START_BIZ_DATE`，并输出 `target_start_biz_date`、`history_coverage` 与 `corporate_action_check`，便于把“窗口加深”与“企业行为收敛”放在同一条输出里观察。

## Verification

1. `env PYTHONPYCACHEPREFIX=/tmp/quanta-pycache python3 -m py_compile backend/app/app_wiring/settings.py backend/app/api/dev_server.py backend/app/domains/market_data/sync.py backend/app/domains/tasking/queue.py backend/app/domains/tasking/service_runner.py backend/app/domains/tasking/worker.py backend/app/domains/tasking/scheduler.py scripts/market_data_backfill_smoke.py scripts/tushare_live_backfill_smoke.py`
2. `python3 scripts/market_data_backfill_smoke.py`
3. `scripts/smoke.sh`
4. `python3 scripts/check_harness_docs.py`
5. `python3 scripts/check_execution_harness.py --require-all-passing`
6. live `QUANTA_LIVE_BACKFILL_TARGET_START_BIZ_DATE=2026-01-29 QUANTA_LIVE_BACKFILL_SKIP_RERUN=1 python3 scripts/tushare_live_backfill_smoke.py`
7. live `QUANTA_LIVE_BACKFILL_TARGET_START_BIZ_DATE=2026-01-20 QUANTA_LIVE_BACKFILL_SKIP_RERUN=1 python3 scripts/tushare_live_backfill_smoke.py`

## Live Result

2026-04-08 在 `QUANTA_SOURCE_PROVIDER=tushare`、`QUANTA_SOURCE_UNIVERSE=core_operating_40`、`QUANTA_SOURCE_VALIDATION_PROVIDERS=none`、`QUANTA_DISCLOSURE_PROVIDER=none` 环境下：

1. `QUANTA_LIVE_BACKFILL_TARGET_START_BIZ_DATE=2026-01-29 QUANTA_LIVE_BACKFILL_SKIP_RERUN=1 python3 scripts/tushare_live_backfill_smoke.py` 返回：
   - `history_coverage.open_day_count = 43`
   - `history_coverage.start_biz_date = 2026-01-29`
   - `history_coverage.end_biz_date = 2026-04-08`
   - `corporate_action_check.status = OK`
   - `checked_action_count = 4`
   - `aligned_action_count = 3`
   - `boundary_gap_count = 1`
   - `nearest_out_of_coverage_event_date = 2026-01-23`
2. 这次结果说明 `target_start_biz_date` 已经能把覆盖精确推进到最近缺口，但当事件日正好落在覆盖起点时，系统会明确报出 `boundary_gap`，而不是把它误记成 canonical mismatch。
3. 随后继续运行 `QUANTA_LIVE_BACKFILL_TARGET_START_BIZ_DATE=2026-01-20 QUANTA_LIVE_BACKFILL_SKIP_RERUN=1 python3 scripts/tushare_live_backfill_smoke.py`，返回：
   - `history_coverage.open_day_count = 50`
   - `history_coverage.start_biz_date = 2026-01-20`
   - `history_coverage.end_biz_date = 2026-04-08`
   - `corporate_action_check.status = OK`
   - `checked_action_count = 5`
   - `aligned_action_count = 5`
   - `boundary_gap_count = 0`
   - `nearest_out_of_coverage_event_date = 2026-01-16`
4. 这说明显式 target-date backfill 不只是“能补到指定日期”，而是已经把企业行为 reconciliation 从 `40 open days -> checked=3/aligned=3` 继续推进到了 `50 open days -> checked=5/aligned=5/boundary_gap=0`。

## Next

1. 继续把覆盖从当前 `2026-01-20` 再往 `2026-01-16` 之前推进，扩大 `corporate_action` 的 in-coverage 比例。
2. 开始评估是否要把 `QUANTA_HISTORY_BACKFILL_TARGET_START_BIZ_DATE` 暴露到正式 live runtime 配置，而不是只在 smoke/运维回补里手工使用。
