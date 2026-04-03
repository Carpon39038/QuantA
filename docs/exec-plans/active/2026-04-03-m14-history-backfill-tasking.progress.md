# M14 History Backfill Tasking Progress

## Current State

历史回补已经不是手动 CLI 能力，而是正式接入了 API、durable queue、worker 和 scheduler。系统现在可以在 source 领先于最新 READY snapshot 时自动走最小 catch-up。

## Last Completed

1. `SUPPORTED_SERVICE_TASKS` 新增 `history_backfill`。
2. queue 支持显式或自动推导 `start_biz_date/end_biz_date`。
3. `history_backfill` worker 会对回补出的每个 snapshot 继续执行 `daily_screener`、`daily_backtest` 并最终发布到 `READY`。
4. backend API 新增 `POST /api/v1/tasks/history-backfill/run`。
5. scheduler 现在在检测到 source 更新领先时，会优先 enqueue `history_backfill`。
6. `scripts/app_smoke.py` 已验证：
   - backfill task 可被接受并排队
   - worker 可成功执行 backfill task
   - 对已存在日期的回补会 `snapshot_count=0` 且进入 `skipped_existing_biz_dates`

## Verification

1. `python3 scripts/pipeline_smoke.py`
2. `scripts/smoke.sh`
3. `python3 scripts/check_harness_docs.py`
4. `python3 scripts/check_execution_harness.py --require-all-passing`

## Next Step

继续推进官方披露源，并补更完整的长期历史回补策略，例如更大窗口、补数节奏和 source shadow validation。
