# M24 Auto History Backfill Recommendation Loop Progress

## Completed

1. scheduler 现在支持 `QUANTA_HISTORY_BACKFILL_TARGET_START_BIZ_DATE=auto`：当 recommendation 存在时，会优先把它解析成具体 `target_start_biz_date`；当 recommendation 缺失时，会继续回退到 `QUANTA_HISTORY_BACKFILL_TARGET_OPEN_DAYS`。
2. `history_backfill_target_open_days` 的优先级语义已经收紧：只有在 `auto` recommendation 缺失时才会继续生效，不再和已解析出的具体 `target_start_biz_date` 并行竞争。
3. `/api/v1/runtime` 现在会返回 `resolved_history_backfill_target_start_biz_date`，便于直接确认当前 `auto` 已解析到了哪一天。
4. `scripts/market_data_backfill_smoke.py` 已新增 fake Tushare 下的 `auto` recommendation / fallback 断言，验证 scheduler 会在 recommendation 存在时吃 recommendation、缺失时回退 open days。

## Verification

1. `env PYTHONPYCACHEPREFIX=/tmp/quanta-pycache python3 -m py_compile backend/app/domains/tasking/scheduler.py backend/app/api/dev_server.py scripts/market_data_backfill_smoke.py`
2. `python3 scripts/market_data_backfill_smoke.py`
3. `scripts/smoke.sh`
4. `python3 scripts/check_harness_docs.py`
5. `python3 scripts/check_execution_harness.py --require-all-passing`

## Current Status

1. `auto` recommendation 的最小自动收敛已经打通，scheduler 不再只知道“建议补到哪天”，而是能把这条建议实际解析进 `history_backfill` 的目标起点里。
2. 当前这条自动策略仍然建立在最新 READY snapshot 的 recommendation 上，因此下一步的重点不是再证明“auto 能跑”，而是继续把 live coverage 更深地往前推，并观察 recommendation 如何随新缺口继续前移。
3. 2026-04-09 的 live target-date 验证已把覆盖从 `2026-01-20` 继续推到 `2026-01-15`，企业行为校验到达 `checked=6/aligned=6/boundary_gap=0`，最新 `nearest_out_of_coverage_event_date` 前移到 `2025-12-19`。

## Next

1. 继续把 live coverage 从 `2026-01-15` 往 `2025-12-19` 之前推进，并把新的 recommendation 写回系统记录。
2. 在更长窗口下评估是否要让 `auto` 默认跟企业行为 recommendation 连续收敛，而不只是一跳。
