# DB Schema Snapshot

这是未来由 DDL 或脚本生成的摘要文件。

当前仍处于规划态，暂以目标表结构为准。

## Planned Tables

### Metadata

1. `stock_basic`
2. `trade_calendar`
3. `industry_membership`
4. `raw_snapshot`
5. `artifact_publish`

### Market Data

1. `daily_bar`
2. `realtime_quote`
3. `northbound_flow_daily`
4. `dragon_tiger_daily`

### Derived Data

1. `price_series_daily`
2. `capital_feature_daily`
3. `indicator_daily`
4. `pattern_signal_daily`
5. `market_regime_daily`

### Runs And Outputs

1. `screener_run`
2. `screener_result`
3. `backtest_run`
4. `backtest_trade`
5. `backtest_equity_curve`
6. `task_run_log`

## Refresh Rule

当 DDL 首次落地后，这个文件应从“手工规划态”切换为“脚本生成态”，避免文档和真实表结构漂移。
