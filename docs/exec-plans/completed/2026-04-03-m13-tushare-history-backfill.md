# M13 Tushare History Backfill

## Goal

把 `Tushare` live canonical provider 从“可同步单天”推进到“可在隔离 DuckDB 中回补一段历史交易日”，让 QuantA 不再只能验证当天快照。

## Scope

本计划聚焦：

1. 为 source provider 增加开市日枚举能力。
2. 为 `market_data.sync` 增加最小 backfill CLI，支持按日期区间逐日同步。
3. 保证 backfill 默认跳过已存在的 `biz_date`，避免重复堆叠同日快照。
4. 补离线 smoke 与 live smoke，验证真实回补链可复现。

## Non-Goals

本计划不包含：

1. 一次性补齐全市场多年历史。
2. 在本轮内引入企业行为修正、复权回补与分钟级历史。
3. 把 backfill 直接接进 resident scheduler 的正式日常运维链。

## Done When

1. `MarketDataProvider` 能列出给定区间内的开市日。
2. `python3 -m backend.app.domains.market_data.sync --start-biz-date ... --end-biz-date ... --print-summary` 能完成最小历史回补。
3. 重跑同一日期区间时，backfill 会跳过已存在的 `biz_date`。
4. 仓库内同时有离线 smoke 与真 token live smoke 覆盖这条 backfill 路径。

## Verify By

1. `python3 scripts/market_data_backfill_smoke.py`
2. `python3 scripts/tushare_live_backfill_smoke.py`
3. `scripts/smoke.sh`

## Tasks

- [x] 为 source provider 增加 `list_open_biz_dates`
- [x] 为 `market_data.sync` 增加最小 backfill CLI
- [x] 实现默认跳过已存在 `biz_date` 的幂等行为
- [x] 增加离线 `market_data_backfill_smoke.py`
- [x] 增加 `tushare_live_backfill_smoke.py`
- [x] 把 backfill 能力写回 README / 可靠性说明 / 技术债记录

## Decisions

1. M13 先采用“逐交易日循环单日 sync”的实现，优先追求正确性和可追溯快照语义，而不是一次性做高吞吐批处理。
2. backfill 默认跳过已存在的 `biz_date`，避免把同一天历史重复写成多条 source-backed 快照。
3. live backfill 统一使用隔离 DuckDB，不污染默认开发库。

## Status

当前状态：M13 已完成。QuantA 现在既能做单日 live sync，也能对最近一段交易日执行最小历史回补，并在重跑时自动跳过已存在日期。下一步把这条 backfill 能力接进正式运维链，并继续推进官方披露源。
