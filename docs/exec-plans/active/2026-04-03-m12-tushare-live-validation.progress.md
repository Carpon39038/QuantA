# M12 Tushare Live Validation Progress

## Current State

真实 token 的基础 live provider 与隔离 live sync 都已跑通，VIP 财务也不再卡在“全体股票必须共用同一报告期”。当前 live 财务覆盖已经达到 `3/3`，下一步转向全量历史回补与官方披露源接入。

## Last Completed

1. 本机安装了 `tushare` 依赖。
2. 新增 `scripts/tushare_live_smoke.py`，可在真 token 下输出成功 summary 或结构化失败信息。
3. 对 provider 增加了 `TushareRequestError` 封装，统一分类 `permission_denied`、`proxy_error`、`dns_error`、`connection_error`。
4. 在真实 token 下实跑 `scripts/tushare_live_smoke.py` 后，基础 canonical 数据已可用：
   - `latest_biz_date=2026-04-03`
   - `daily_bar_count=3`
   - `capital_feature_override_count=3`
5. live 验证表明最新年报期并不会同时覆盖全部股票：`300750.SZ` 在 `2025-12-31` 就有数，但 `002475.SZ` / `688017.SH` 需要回退到 `2025-09-30`。
6. provider 已改成按股票回退最近可用财报期；再次实跑 `scripts/tushare_live_smoke.py` 后：
   - `fundamental_feature_override_count=3`
   - `covered_financial_symbols=["002475.SZ","300750.SZ","688017.SH"]`
   - `vip_financials_ready=true`
   - `financial_report_period_by_symbol={"002475.SZ":"2025-09-30","300750.SZ":"2025-12-31","688017.SH":"2025-09-30"}`
7. 新增 `scripts/tushare_live_sync_smoke.py` 并实跑成功，隔离运行目录下的 live sync 已能写入：
   - `raw_snapshot_2026-04-03_close_003`
   - `snapshot_2026-04-03_ready_003`
   - `inserted_daily_bar=3`
   - `inserted_fundamental_feature_daily=3`
8. 当前 live summary 已无财务权限 warning；剩余缺口转为：
   - Tushare 全量历史回补仍未接入默认日终流水线
   - 官方披露 adapter 仍未进入主链
   - AKShare/BaoStock 仍未形成 shadow validation / gap-fill 机制

## Verification

1. `python3 scripts/tushare_provider_smoke.py`
2. `python3 scripts/tushare_live_smoke.py`
3. `python3 scripts/tushare_live_sync_smoke.py`

## Next Step

继续做 Tushare 全量历史回补，再把巨潮资讯 / 交易所披露源接进主链，并补 AKShare/BaoStock 的 shadow validation。
