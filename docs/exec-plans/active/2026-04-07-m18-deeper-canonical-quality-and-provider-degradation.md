# M18 Deeper Canonical Quality And Provider Degradation

## Goal

把 QuantA 从“多字段补充校验”继续推进到“canonical source 自检更深、补充源降级更清晰且可告警”，让 live source-backed sync 更接近日常可运维形态。

## Scope

1. 在 `tushare` canonical provider 中接入 `adj_factor` 与 `suspend_d`，并把结果写入 `source_watermark`。
2. 把 `shadow_validation` 继续扩到更深口径：
   - `adj_factor` 覆盖率与有效性
   - `limit_price` 与板块涨跌停规则
   - `suspension` 与停牌标记一致性
3. 让 `price_series_daily` 在 rebuild 时对 `adj_factor` 做 carry-forward，而不是把旧日复权因子重置为 `1.0`。
4. 把 `akshare` 的 Eastmoney 上游不稳定显式收口为 provider degradation category，并写入 alerts。
5. 让 live sync smoke 直接暴露隔离 runtime 的 alerts，验证降级告警真实落盘。

## Non-Goals

1. 本里程碑不修复 AKShare / Eastmoney 上游链路本身。
2. 本里程碑不把企业行为修正扩到分红送配全量长期回溯。
3. 本里程碑不把披露源扩到公告正文抽取和交易所问询正文。

## Acceptance

1. `tushare` provider 在 tracked universe 上返回 `adj_factor_count`、`adj_factor_missing_symbols`、`suspended_symbol_count` 和 `suspended_symbols`。
2. `shadow_validation` 输出会包含 canonical checks：
   - `adj_factor`
   - `limit_price`
   - `suspension`
3. `scripts/tushare_live_sync_smoke.py` 在 `core_operating_40` 上能证明：
   - canonical checks 为 `OK`
   - `akshare` 被分类成 `akshare_upstream_connectivity`
   - `baostock` 的 10 只 `adj_factor` 差异被单列为 `adj_factor_semantics_mismatch`
   - 隔离 runtime 会真实写出 provider degradation alerts
4. `scripts/smoke.sh`、`check_harness_docs.py`、`check_execution_harness.py --require-all-passing` 通过。

## Tasks

- [x] 接入 `adj_factor` / `suspend_d` 并刷新 source watermark
- [x] 扩 canonical quality checks 到复权、停牌、涨跌停
- [x] 给 `price_series_daily` 增加 `adj_factor` carry-forward
- [x] 细化 `akshare` / `baostock` 降级分类，并把降级写入 alerts
- [x] 更新 live smoke 与系统记录层

## Notes

1. `baostock` 当前暴露出的 `adj_factor` 差异被视为“补充源语义差异”，不是 canonical `tushare` 日线原始价格错误。
2. `akshare` 仍保留在补充源链路中，但现在是“非阻断、可分类、可告警”的降级状态。
