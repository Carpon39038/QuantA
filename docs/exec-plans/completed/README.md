# Completed Plans

已完成且不再活跃的执行计划归档到这里。

## Archive Criteria

一组 plan / acceptance / progress 文件可以从 `active/` 迁到这里，必须同时满足：

1. acceptance 条目已经全绿，或该计划没有 acceptance 但后续事项已经被后续计划吸收。
2. `progress` 里的下一步不再是当前交付闭环的一部分。
3. 仍需跟踪的遗留问题已经转入后续 active plan 或 `../tech-debt-tracker.md`。
4. 迁移后 `scripts/check_harness_docs.py` 和 `scripts/check_execution_harness.py --require-all-passing` 仍能通过。

归档时保留：

1. 原始目标
2. 决策日志
3. 完成时间
4. 后续遗留问题

## 2026-07-03 Archive Batch

本批次把 M0 到 M23 的已完成里程碑移入 `completed/`。`active/` 只保留仍在观察 live daemon 自动追深与旧 raw snapshot refresh 口径的 M24。
