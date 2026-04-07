# M16 Realistic Universe And Shadow Validation

## Goal

把 QuantA 的“可用初版”从 3 只样本股继续推进到更真实的研究池，并把补充数据源交叉校验真正接进 live canonical sync，而不是只在文档里写“以后做多源验证”。

## Scope

1. 引入版本化的 source universe manifest，并把默认研究池切到 `core_research_12`。
2. 为 canonical source 增加 `shadow_validation`，支持 `akshare` 与 `baostock` 对 `tushare` 结果做逐股 close 校验。
3. 在 snapshot/runtime/system health payload 中暴露研究池与补充校验状态。
4. 修正 `tushare` provider 的日切语义，让白天 sync 会回退到最近一个真正已有日线的交易日。
5. 用真 token 在 `core_research_12` 上完成 live sync / live validation / live backfill 验证。

## Non-Goals

1. 本里程碑不把研究池直接扩到全市场。
2. 本里程碑不把多源校验扩展到复权因子、成交额、停牌和公告级别。
3. 本里程碑不引入新的正式 canonical provider。

## Acceptance

1. 仓库有可版本化的默认研究池定义，且未设置 `QUANTA_SOURCE_SYMBOLS` 时会自动加载。
2. `market_data.sync` 会把 `shadow_validation` 写入 `raw_snapshot.source_watermark_json`，并通过最新快照与系统健康读口暴露。
3. `tushare` live 路径在白天不会因为“今天开市但日线未出”而直接失败，而是回退到最近一个真正可用的 `biz_date`。
4. 2026-04-07 的真 token 验证在 `core_research_12` 上能跑通：
   - `tushare_live_smoke.py`
   - `tushare_live_sync_smoke.py`
   - `tushare_live_backfill_smoke.py`
5. 默认 smoke 与 harness 门禁仍保持通过。

## Tasks

- [x] 增加 `source_universe` manifest 读取与默认 `core_research_12`
- [x] 增加 `shadow_validation` provider 聚合与 close tolerance 配置
- [x] 把 `shadow_validation` 接入 sync / snapshot / runtime / health payload
- [x] 修正 `tushare` provider 的 latest available biz_date 解析
- [x] 扩展前端状态条，展示研究池与补充校验状态
- [x] 跑通默认 smoke 与 live `tushare + akshare + baostock` 验证

## Notes

1. `shadow_validation` 当前是“补充校验”，不是新的 canonical source 决策器。
2. `tushare_live_backfill_smoke.py` 为了让验收时间保持可控，会关闭补充校验与官方披露 sidecar，专注验证历史回补语义。
