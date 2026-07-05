# M17 Field-Level Shadow Validation And Operating Universe

## Goal

把 QuantA 从“12 只研究池 + close-only 补充校验”推进到“更大的默认运营研究池 + 七字段 shadow validation”，让 live canonical sync 更接近日常盘后使用形态。

## Scope

1. 把默认 source universe 从 `core_research_12` 扩到更大的 `core_operating_40`。
2. 把 `shadow_validation` 从只比 `close_raw` 扩到：
   - `open_raw`
   - `high_raw`
   - `low_raw`
   - `close_raw`
   - `pre_close_raw`
   - `volume`
   - `amount`
3. 为 `volume` / `amount` 增加独立容差配置。
4. 更新 runtime / frontend / smoke / live smoke，让更大研究池和多字段校验成为系统事实。

## Non-Goals

1. 本里程碑不把研究池直接扩到全市场。
2. 本里程碑不引入复权因子、停牌、涨跌停、企业行为等更深数据质量口径。
3. 本里程碑不修复 AKShare 上游链路本身。

## Acceptance

1. 默认 `load_settings()` 未设置 `QUANTA_SOURCE_SYMBOLS` 时会加载 `core_operating_40`。
2. `shadow_validation` 输出会包含字段级 summary 和容差，而不是只有 close match。
3. `scripts/smoke.sh`、`check_harness_docs.py`、`check_execution_harness.py --require-all-passing` 通过。
4. 2026-04-07 的 live `tushare` 验证在 `core_operating_40` 上能证明：
   - provider 能产出 40 只 tracked daily bars
   - live sync 能写出 40 只 canonical bars 与 40 只财务 sidecar
   - `baostock` 在七字段上达到 `40/40` match
5. `tushare_live_backfill_smoke.py` 在 `core_operating_40` 上仍保持首跑插入 / 二次跳过语义。

## Tasks

- [x] 增加 `core_operating_40` universe manifest 并切成默认
- [x] 给 `shadow_validation` 增加字段级 summary 与 `volume/amount` 容差
- [x] 更新 workbench / smoke / live smoke 输出
- [x] 用真 token 在 `core_operating_40` 上做 live smoke / live sync / live backfill
- [x] 把本轮结果写回系统记录层

## Notes

1. 当前 `shadow_validation` 是“补充源质量信号”，不是 canonical source 仲裁器。
2. `akshare` 仍受其上游链路影响；本里程碑把这种不稳定显式记录成 provider-level `UNAVAILABLE`，而不让它阻断 `tushare` canonical sync。
