# M12 Tushare Live Validation

## Goal

在真实 `Tushare` token 下验证 QuantA 的 canonical provider 不只是离线映射正确，而是能真正拉到 live 数据并进入后续历史回补阶段。

## Scope

本计划聚焦：

1. 安装 `tushare` 依赖并补一条独立 live smoke 命令。
2. 在真实 token 下验证 `trade_cal`、日线、资金流和财务 sidecar 的最小拉取能力。
3. 把 live 验证结果写回计划和 README。

## Non-Goals

本计划不包含：

1. 在 token 权限未开通前强行做真实历史回补。
2. 修改 Tushare 官方积分或权限策略。
3. 继续扩产品功能而忽略 live provider 阻塞。

## Done When

1. `scripts/tushare_live_smoke.py` 能在真 token 下返回成功 summary。
2. `scripts/tushare_live_sync_smoke.py` 能在隔离运行目录里完成最小 live sync。
3. `tushare` provider 能在真实披露错位下按股票回退到最近可用财报期，而不是把财务 sidecar 锁死在单一季度。
4. live smoke / live sync 的结果被写回系统记录，明确当前 live 覆盖率和下一步缺口。

## Verify By

1. `python3 scripts/tushare_live_smoke.py`
2. `python3 scripts/tushare_live_sync_smoke.py`

## Tasks

- [x] 安装 `tushare` Python 依赖
- [x] 新增 `scripts/tushare_live_smoke.py`
- [x] 在真 token 下完成 live smoke 尝试
- [x] 新增隔离运行目录下的 live sync smoke
- [x] 把 VIP 财务从统一报告期改成按股票回退最近可用报告期
- [x] 把 live 结果和当前剩余缺口写回系统记录

## Decisions

1. live smoke 优先做只读 provider 验证，不直接写库，避免在权限未明前污染本地发布链。
2. 对 Tushare 官方异常做结构化分类，至少区分 `permission_denied`、代理错误和 DNS/连接错误。

## Status

当前状态：M12 已完成。真实 token 下，基础 live smoke 与隔离 live sync 都已通过；`tushare` provider 也已改成按股票回退最近可用财报期，当前 live 路径已达到 `3/3` 财务覆盖，并能在隔离 DuckDB 中写出 `fundamental_feature_daily`。下一步进入全量历史回补与官方披露源接入。
