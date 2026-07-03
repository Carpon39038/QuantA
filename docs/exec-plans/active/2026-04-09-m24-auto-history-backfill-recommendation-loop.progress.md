# M24 Auto History Backfill Recommendation Loop Progress

## Completed

1. scheduler 现在支持 `QUANTA_HISTORY_BACKFILL_TARGET_START_BIZ_DATE=auto`：当 recommendation 存在时，会优先把它解析成具体 `target_start_biz_date`；当 recommendation 缺失时，会继续回退到 `QUANTA_HISTORY_BACKFILL_TARGET_OPEN_DAYS`。
2. `history_backfill_target_open_days` 的优先级语义已经收紧：只有在 `auto` recommendation 缺失时才会继续生效，不再和已解析出的具体 `target_start_biz_date` 并行竞争。
3. `/api/v1/runtime` 现在会返回 `resolved_history_backfill_target_start_biz_date`，便于直接确认当前 `auto` 已解析到了哪一天。
4. `scripts/market_data_backfill_smoke.py` 已新增 fake Tushare 下的 `auto` recommendation / fallback 断言，并直接覆盖到 `enqueue_next_pipeline_task` 的决策层，验证 scheduler 会把 recommendation 作为 `history_backfill.target_start_biz_date` 传到 queue 入口；recommendation 缺失时则继续回退 open days。
5. `TushareCorporateActionProvider` 现会在同一次 provider 生命周期里按 symbol 缓存原始 `dividend` rows；as-of 过滤仍按每个 `biz_date` 执行。`scripts/market_data_backfill_smoke.py` 已断言三天、两只股票的 fake 回补只触发 `2` 次 dividend 调用，而不是 `6` 次。
6. 长窗口 live 回补在 `dividend` 缓存后仍然会进入较长的本地 CPU-heavy 阶段；这说明下一轮优化重点应放到长窗口 snapshot rebuild / price series rebuild 的增量化，而不只是继续减少 provider 请求。
7. `market_data.sync` 新增 `artifact_mode=latest`：中间历史日通过 source-only raw ingest 写入 `raw_snapshot/daily_bar`，窗口终点才完整发布 artifact；service worker 的 `history_backfill` 现默认走 latest artifact 模式，直接避免在长窗口中按天重复重建完整 `price_series_daily/analysis/screener/backtest`。
8. `scripts/tushare_live_backfill_smoke.py` 现调用 CLI 的 `--artifact-mode latest`；`scripts/market_data_backfill_smoke.py` 覆盖 latest 模式的 raw/artifact 数、source-only watermark、终点 price history 覆盖，以及二次运行 no-op。
9. `scripts/tushare_live_backfill_smoke.py` 增加阶段日志、固定 `QUANTA_LIVE_BACKFILL_END_BIZ_DATE` 与耗时字段；脚本先解析一次窗口，再把显式 `--start-biz-date/--end-biz-date` 传给 CLI，避免首轮和 rerun 重复做 latest source 探测。
10. Tushare source-only 中间日现在跳过财务、资金流、指数、suspend 等终点 artifact 才需要的重输入，同时保留 `adj_factor` 并把 `adj_factor_overrides` 写入 raw snapshot watermark；终点 price series rebuild 会读取历史 raw watermark，避免 latest-artifact 从空隔离库发布时丢失中间日复权因子。
11. `history_coverage.recommended_target_start_biz_date` 在本地 `trade_calendar` 不足以找到 anchor 前一个开市日时，会兜底到 anchor 前 10 个自然日，避免 live runtime 已发现 `nearest_out_of_coverage_event_date` 但 `auto` 解析成 `null` 后停止追深。

## Verification

1. `env PYTHONPYCACHEPREFIX=/tmp/quanta-pycache python3 -m py_compile backend/app/domains/tasking/scheduler.py backend/app/api/dev_server.py backend/app/shared/providers/corporate_action_source.py backend/app/domains/market_data/sync.py backend/app/domains/tasking/service_runner.py scripts/market_data_backfill_smoke.py scripts/tushare_live_backfill_smoke.py`
2. `python3 scripts/market_data_backfill_smoke.py`
3. `env PYTHONPYCACHEPREFIX=/tmp/quanta-pycache python3 scripts/app_smoke.py`
4. `scripts/smoke.sh`
5. `python3 scripts/check_harness_docs.py`
6. `python3 scripts/check_execution_harness.py --require-all-passing`
7. `QUANTA_LIVE_BACKFILL_TARGET_START_BIZ_DATE=2025-11-17 QUANTA_LIVE_BACKFILL_END_BIZ_DATE=2026-07-03 python3 scripts/tushare_live_backfill_smoke.py`

## Current Status

1. `auto` recommendation 的最小自动收敛已经打通，scheduler 不再只知道“建议补到哪天”，而是能把这条建议实际解析进 `history_backfill` 的目标起点里。
2. 当前这条自动策略仍然建立在最新 READY snapshot 的 recommendation 上，因此下一步的重点不是再证明“auto 能跑”，而是继续把 live coverage 更深地往前推，并观察 recommendation 如何随新缺口继续前移。
3. 2026-04-09 的 live target-date 验证已把覆盖从 `2026-01-20` 继续推到 `2026-01-15`，企业行为校验到达 `checked=6/aligned=6/boundary_gap=0`，最新 `nearest_out_of_coverage_event_date` 前移到 `2025-12-19`。
4. 继续推到 `2025-12-18` 后，企业行为校验达到 `checked=8/aligned=7/boundary_gap=1`；这条边界缺口验证了 recommendation 区分 `resolve_boundary_gap` 与 `extend_to_next_out_of_coverage` 的必要性。
5. 继续推到 `2025-12-15` 后，企业行为校验达到 `checked=9/aligned=9/boundary_gap=0`，最新 `nearest_out_of_coverage_event_date` 前移到 `2025-11-18`。这轮确认 recommendation-driven target-date 的方向是对的，但也暴露了 70+ open days 的 isolated live backfill 已经开始明显受本地 snapshot rebuild 成本影响。
6. 2026-04-09 已完成第一层长窗口增量化：`history_backfill` 的中间日期不再发布 full artifacts，CLI / live smoke 可以显式使用 latest artifact 模式；同时修正了 coverage no-op 判断，不能硬编码 `price_basis='raw'`，否则 fixture/qfq 环境会误重建终点快照。
7. 2026-07-03 的隔离 live smoke 使用 `core_operating_40`、`2025-11-17 -> 2026-07-03` 共 `152` 个 open days 验证 latest artifact：首轮 `190.174s`，rerun `0.712s`；首轮 `source_only_raw_snapshot_count=149`、`artifact_snapshot_count=1`，rerun `synced_biz_date_count=0`、`artifact_snapshot_count=0`；隔离库企业行为校验为 `checked=40/aligned=40/boundary_gap=0`，`nearest_out_of_coverage_event_date=2025-11-12`。
8. 2026-07-03 重启 live `com.quanta.pipeline` 后，正式 runtime 先自动排入 `target_start_biz_date=2025-11-08`，实际 source window 为 `2025-11-10 -> 2026-07-03`，随后连续追深多段；截至 16:04，HTTP health 可见最新 READY 为 `snapshot_2026-07-03_ready_068`，history coverage 已推进到 `2025-08-26 -> 2026-07-03`、`205` 个 open days，最近未覆盖事件前移到 `2025-08-20`，`/api/v1/runtime.resolved_history_backfill_target_start_biz_date=2025-08-11`。
9. 正式 live 库仍保留 `unchanged_adj_factor=9` 的 warning，这是旧 raw snapshots 缺少 `adj_factor_overrides` watermark 的历史遗留；新 source-only raw ingest 会记录 adj factor，隔离全量重跑已证明 latest artifact 从空库构建时可达到 `aligned=40/40`。该 warning 不是 error，但后续如果要清理，需要显式刷新受影响日期的旧 raw snapshots 或设计可审计的 raw reingest 操作。

## Next

1. 继续观察 live daemon 的后续 auto 追深窗口，确认它在新 recommendation fallback 下不会再次停在 `recommended_target_start_biz_date=null`。
2. 后续若要消除正式库 `unchanged_adj_factor=9` warning，应新增可审计的 raw snapshot refresh / reingest 口径，而不是手工删库。
