# M23 History Coverage Recommendation Surfacing Progress

## Completed

1. `backend.app.domains.market_data.repo.load_system_health()` 现在会基于最新 READY snapshot 的 `corporate_action` reconciliation 结果，推导 `recommended_target_start_biz_date`、`recommendation_reason` 与 `recommendation_anchor_biz_date`，并一起挂到 `history_coverage` 下。
2. 当系统检测到 `boundary_gap` 时，推荐会回退到当前 coverage 起点前一个 open day；当只剩 `out_of_coverage` 时，推荐会回退到最近未覆盖事件日前一个 open day。
3. workbench 的状态区与告警摘要现已直接展示当前 `history_coverage` 与建议的下一次回补起点，operator 不再需要自己把 `nearest_out_of_coverage_event_date` 手算成目标起始日。

## Verification

1. `env PYTHONPYCACHEPREFIX=/tmp/quanta-pycache python3 -m py_compile backend/app/domains/market_data/repo.py`
2. `node --check frontend/src/app/main.js`
3. `scripts/smoke.sh`
4. `python3 scripts/check_harness_docs.py`
5. `python3 scripts/check_execution_harness.py --require-all-passing`

## Live Interpretation

1. 在 `2026-04-08` 的 target-date live 回补结果里：
   - `target_start_biz_date = 2026-01-29` 时，`corporate_action_check` 会给出 `boundary_gap_count = 1`，因此下一次建议回补起点应当回退到 `2026-01-28`。
   - `target_start_biz_date = 2026-01-20` 时，`boundary_gap_count = 0` 且 `nearest_out_of_coverage_event_date = 2026-01-16`，因此下一次建议回补起点应当回退到 `2026-01-15`。
2. 这说明 recommendation 已经能把“边界缺口”与“更早未覆盖事件”区分开，不再只给一个模糊的“继续补深历史”结论。

## Next

1. 继续把 recommendation 从可见信号推进成正式 live runtime 的自动补数策略；该后续工作已转入 `2026-04-09-m24-auto-history-backfill-recommendation-loop`。
2. 在更长窗口下继续验证企业行为长期回溯与复权基准核对。
