# DB Schema Snapshot

This file is generated from `backend/app/domains/market_data/schema.py`.

当前内容表示仓库里已经落地到 DuckDB 的最小表结构，不再是纯规划态列表。

## Metadata

### `stock_basic`

最小股票主数据，供观察名单和后续日线同步复用。

| Column | Type | Notes |
| --- | --- | --- |
| `symbol` | `VARCHAR` | 交易所后缀证券代码; required |
| `display_name` | `VARCHAR` | 证券简称; required |
| `exchange` | `VARCHAR` | 交易所代码; required |
| `board` | `VARCHAR` | 板块分类; required |
| `industry` | `VARCHAR` | 一级行业; required |
| `is_active` | `BOOLEAN` | 是否仍在活跃股票池中; required |
| `listed_at` | `DATE` | 上市日期; nullable |
| `updated_at` | `TIMESTAMP` | 最近一次同步时间; required |
| `PRIMARY KEY` | `constraint` | symbol |

### `trade_calendar`

交易日历，用于后续盘后任务与回测窗口判断。

| Column | Type | Notes |
| --- | --- | --- |
| `trade_date` | `DATE` | 交易日; required |
| `market_code` | `VARCHAR` | 市场代码; required |
| `is_open` | `BOOLEAN` | 是否开市; required |
| `updated_at` | `TIMESTAMP` | 最近一次同步时间; required |
| `PRIMARY KEY` | `constraint` | trade_date, market_code |

### `raw_snapshot`

不可变原始数据快照元数据。

| Column | Type | Notes |
| --- | --- | --- |
| `raw_snapshot_id` | `VARCHAR` | 原始快照标识; required |
| `snapshot_seq` | `BIGINT` | 原始快照序号; required |
| `biz_date` | `DATE` | 业务日期; required |
| `status` | `VARCHAR` | 原始快照状态; required |
| `required_datasets_json` | `VARCHAR` | 当前原始快照依赖的数据集 JSON; required |
| `completeness_json` | `VARCHAR` | 完整性与校验结果 JSON; required |
| `source_watermark_json` | `VARCHAR` | 外部数据源水位与来源说明 JSON; required |
| `created_at` | `TIMESTAMP` | 快照生成时间; required |
| `attempt_no` | `INTEGER` | 生成尝试次数; required |
| `PRIMARY KEY` | `constraint` | raw_snapshot_id |

### `artifact_publish`

页面与标准查询读取的发布快照门禁。

| Column | Type | Notes |
| --- | --- | --- |
| `snapshot_id` | `VARCHAR` | 发布快照标识; required |
| `publish_seq` | `BIGINT` | 发布序号; required |
| `biz_date` | `DATE` | 业务日期; required |
| `raw_snapshot_id` | `VARCHAR` | 关联原始快照; required |
| `status` | `VARCHAR` | 发布状态; required |
| `price_basis` | `VARCHAR` | 价格口径; required |
| `required_artifacts_json` | `VARCHAR` | 当前快照依赖的产物列表 JSON; required |
| `artifact_status_json` | `VARCHAR` | 各产物 READY/BLOCKED 状态 JSON; required |
| `published_at` | `TIMESTAMP` | 发布时间; required |
| `attempt_no` | `INTEGER` | 发布尝试次数; required |
| `PRIMARY KEY` | `constraint` | snapshot_id |

## Market Data

### `daily_bar`

原始日线行情增量表，后续按 raw_snapshot_id 做 as-of 解析。

| Column | Type | Notes |
| --- | --- | --- |
| `raw_snapshot_id` | `VARCHAR` | 原始快照标识; required |
| `symbol` | `VARCHAR` | 证券代码; required |
| `trade_date` | `DATE` | 交易日; required |
| `open_raw` | `DOUBLE` | 原始开盘价; nullable |
| `high_raw` | `DOUBLE` | 原始最高价; nullable |
| `low_raw` | `DOUBLE` | 原始最低价; nullable |
| `close_raw` | `DOUBLE` | 原始收盘价; nullable |
| `pre_close_raw` | `DOUBLE` | 原始前收价; nullable |
| `volume` | `DOUBLE` | 成交量; nullable |
| `amount` | `DOUBLE` | 成交额; nullable |
| `turnover_rate` | `DOUBLE` | 换手率; nullable |
| `high_limit` | `DOUBLE` | 涨停价; nullable |
| `low_limit` | `DOUBLE` | 跌停价; nullable |
| `limit_rule_code` | `VARCHAR` | 涨跌停规则编码; nullable |
| `is_suspended` | `BOOLEAN` | 是否停牌; nullable |
| `source` | `VARCHAR` | 数据来源; nullable |
| `updated_at` | `TIMESTAMP` | 写入更新时间; required |
| `PRIMARY KEY` | `constraint` | raw_snapshot_id, symbol, trade_date |

## Derived Data

### `price_series_daily`

复权价格序列，后续供分析与回测读取。

| Column | Type | Notes |
| --- | --- | --- |
| `symbol` | `VARCHAR` | 证券代码; required |
| `trade_date` | `DATE` | 交易日; required |
| `price_basis` | `VARCHAR` | 价格口径; required |
| `open` | `DOUBLE` | 开盘价; nullable |
| `high` | `DOUBLE` | 最高价; nullable |
| `low` | `DOUBLE` | 最低价; nullable |
| `close` | `DOUBLE` | 收盘价; nullable |
| `pre_close` | `DOUBLE` | 前收价; nullable |
| `adj_factor` | `DOUBLE` | 复权因子; nullable |
| `snapshot_id` | `VARCHAR` | 发布快照标识; required |
| `volume` | `DOUBLE` | 成交量; nullable |
| `amount` | `DOUBLE` | 成交额; nullable |
| `updated_at` | `TIMESTAMP` | 写入更新时间; required |
| `PRIMARY KEY` | `constraint` | snapshot_id, symbol, trade_date, price_basis |

### `indicator_daily`

技术指标日级结果，供个股页、选股和回测信号读取。

| Column | Type | Notes |
| --- | --- | --- |
| `symbol` | `VARCHAR` | 证券代码; required |
| `trade_date` | `DATE` | 交易日; required |
| `snapshot_id` | `VARCHAR` | 发布快照标识; required |
| `price_basis` | `VARCHAR` | 价格口径; required |
| `ma5` | `DOUBLE` | 5 日均线; nullable |
| `ma10` | `DOUBLE` | 10 日均线; nullable |
| `ma20` | `DOUBLE` | 20 日均线; nullable |
| `ma60` | `DOUBLE` | 60 日均线; nullable |
| `macd_dif` | `DOUBLE` | MACD DIF; nullable |
| `macd_dea` | `DOUBLE` | MACD DEA; nullable |
| `macd_hist` | `DOUBLE` | MACD HIST; nullable |
| `kdj_k` | `DOUBLE` | KDJ K; nullable |
| `kdj_d` | `DOUBLE` | KDJ D; nullable |
| `kdj_j` | `DOUBLE` | KDJ J; nullable |
| `rsi6` | `DOUBLE` | RSI6; nullable |
| `rsi12` | `DOUBLE` | RSI12; nullable |
| `boll_upper` | `DOUBLE` | 布林上轨; nullable |
| `boll_mid` | `DOUBLE` | 布林中轨; nullable |
| `boll_lower` | `DOUBLE` | 布林下轨; nullable |
| `volume_ratio` | `DOUBLE` | 量比; nullable |
| `updated_at` | `TIMESTAMP` | 写入更新时间; required |
| `PRIMARY KEY` | `constraint` | symbol, trade_date, price_basis, snapshot_id |

### `pattern_signal_daily`

量价与形态信号，一行一个信号，允许同日多信号并存。

| Column | Type | Notes |
| --- | --- | --- |
| `symbol` | `VARCHAR` | 证券代码; required |
| `trade_date` | `DATE` | 交易日; required |
| `snapshot_id` | `VARCHAR` | 发布快照标识; required |
| `price_basis` | `VARCHAR` | 价格口径; required |
| `signal_code` | `VARCHAR` | 信号编码; required |
| `signal_type` | `VARCHAR` | 信号类型; required |
| `direction` | `VARCHAR` | 方向; required |
| `is_triggered` | `BOOLEAN` | 是否触发; required |
| `signal_score` | `DOUBLE` | 信号强度分; required |
| `payload_json` | `VARCHAR` | 信号细节 JSON; required |
| `updated_at` | `TIMESTAMP` | 写入更新时间; required |
| `PRIMARY KEY` | `constraint` | symbol, trade_date, price_basis, snapshot_id, signal_code |

### `capital_feature_daily`

股票日级资金特征聚合结果，供个股页和选股读取。

| Column | Type | Notes |
| --- | --- | --- |
| `symbol` | `VARCHAR` | 证券代码; required |
| `trade_date` | `DATE` | 交易日; required |
| `snapshot_id` | `VARCHAR` | 发布快照标识; required |
| `main_net_inflow` | `DOUBLE` | 主力净流入; nullable |
| `main_net_inflow_ratio` | `DOUBLE` | 主力净流入占成交额比例; nullable |
| `super_large_order_inflow` | `DOUBLE` | 超大单净流入; nullable |
| `large_order_inflow` | `DOUBLE` | 大单净流入; nullable |
| `northbound_net_inflow` | `DOUBLE` | 北向净流入; nullable |
| `has_dragon_tiger` | `BOOLEAN` | 是否带龙虎榜标签; required |
| `updated_at` | `TIMESTAMP` | 写入更新时间; required |
| `PRIMARY KEY` | `constraint` | symbol, trade_date, snapshot_id |

### `fundamental_feature_daily`

股票日级财务特征聚合结果，供选股读取 canonical 财务侧信号。

| Column | Type | Notes |
| --- | --- | --- |
| `symbol` | `VARCHAR` | 证券代码; required |
| `trade_date` | `DATE` | 交易日; required |
| `snapshot_id` | `VARCHAR` | 发布快照标识; required |
| `report_period` | `DATE` | 财报报告期; nullable |
| `ann_date` | `DATE` | 公告日期; nullable |
| `roe_dt` | `DOUBLE` | 扣非 ROE; nullable |
| `grossprofit_margin` | `DOUBLE` | 毛利率; nullable |
| `debt_to_assets` | `DOUBLE` | 资产负债率; nullable |
| `total_revenue` | `DOUBLE` | 营业总收入; nullable |
| `net_profit_attr_p` | `DOUBLE` | 归母净利润; nullable |
| `n_cashflow_act` | `DOUBLE` | 经营活动现金流净额; nullable |
| `total_assets` | `DOUBLE` | 总资产; nullable |
| `total_liab` | `DOUBLE` | 总负债; nullable |
| `cash_to_profit` | `DOUBLE` | 经营现金流与归母净利润比; nullable |
| `fundamental_score` | `DOUBLE` | 财务综合分; nullable |
| `updated_at` | `TIMESTAMP` | 写入更新时间; required |
| `PRIMARY KEY` | `constraint` | symbol, trade_date, snapshot_id |

### `market_regime_daily`

市场概览页读取的聚合市场状态。

| Column | Type | Notes |
| --- | --- | --- |
| `snapshot_id` | `VARCHAR` | 发布快照标识; required |
| `trade_date` | `DATE` | 交易日; required |
| `summary` | `VARCHAR` | 市场摘要; required |
| `regime_label` | `VARCHAR` | 市场阶段标签; required |
| `snapshot_source` | `VARCHAR` | 快照来源说明; required |
| `indices_json` | `VARCHAR` | 指数概览 JSON; required |
| `breadth_json` | `VARCHAR` | 市场宽度 JSON; required |
| `highlights_json` | `VARCHAR` | 重点提示 JSON; required |
| `PRIMARY KEY` | `constraint` | snapshot_id, trade_date |

## Runs And Outputs

### `screener_run`

选股运行摘要。

| Column | Type | Notes |
| --- | --- | --- |
| `run_id` | `VARCHAR` | 运行标识; required |
| `trade_date` | `DATE` | 交易日; required |
| `snapshot_id` | `VARCHAR` | 发布快照标识; required |
| `strategy_name` | `VARCHAR` | 策略名称; required |
| `strategy_version` | `VARCHAR` | 策略版本; required |
| `signal_price_basis` | `VARCHAR` | 信号价格口径; required |
| `universe_size` | `INTEGER` | 股票池规模; required |
| `result_count` | `INTEGER` | 结果条数; required |
| `status` | `VARCHAR` | 运行状态; required |
| `as_of_date` | `DATE` | 结果口径日期; required |
| `started_at` | `TIMESTAMP` | 开始时间; required |
| `finished_at` | `TIMESTAMP` | 结束时间; required |
| `PRIMARY KEY` | `constraint` | run_id |

### `screener_result`

选股结果明细。

| Column | Type | Notes |
| --- | --- | --- |
| `run_id` | `VARCHAR` | 关联 screener_run; required |
| `symbol` | `VARCHAR` | 证券代码; required |
| `trade_date` | `DATE` | 交易日; required |
| `strategy_name` | `VARCHAR` | 策略名称; required |
| `snapshot_id` | `VARCHAR` | 发布快照标识; required |
| `signal_price_basis` | `VARCHAR` | 信号价格口径; required |
| `total_score` | `INTEGER` | 总分; required |
| `trend_score` | `DOUBLE` | 趋势分; nullable |
| `price_volume_score` | `DOUBLE` | 量价分; nullable |
| `capital_score` | `DOUBLE` | 资金分; nullable |
| `fundamental_score` | `DOUBLE` | 基础过滤分; nullable |
| `display_name` | `VARCHAR` | 证券简称; required |
| `thesis` | `VARCHAR` | 投资主线摘要; required |
| `matched_rules_json` | `VARCHAR` | 命中信号 JSON; required |
| `risk_flags_json` | `VARCHAR` | 风险标签 JSON; required |
| `rank_no` | `INTEGER` | 排序名次; required |
| `PRIMARY KEY` | `constraint` | run_id, symbol |

### `backtest_request`

持久化回测请求，当前作为本地 durable queue 的最小载体。

| Column | Type | Notes |
| --- | --- | --- |
| `backtest_id` | `VARCHAR` | 回测标识; required |
| `requested_at` | `TIMESTAMP` | 请求创建时间; required |
| `snapshot_id` | `VARCHAR` | 发布快照标识; required |
| `raw_snapshot_id` | `VARCHAR` | 原始快照标识; required |
| `strategy_version` | `VARCHAR` | 策略版本; required |
| `signal_price_basis` | `VARCHAR` | 信号价格口径; required |
| `payload_json` | `VARCHAR` | 请求负载 JSON; required |
| `status` | `VARCHAR` | 请求状态; required |
| `retry_count` | `INTEGER` | 重试次数; required |
| `last_error` | `VARCHAR` | 最近错误信息; nullable |
| `PRIMARY KEY` | `constraint` | backtest_id |

### `backtest_run`

回测运行摘要。

| Column | Type | Notes |
| --- | --- | --- |
| `backtest_id` | `VARCHAR` | 回测标识; required |
| `strategy_name` | `VARCHAR` | 策略名称; required |
| `strategy_version` | `VARCHAR` | 策略版本; required |
| `param_json` | `VARCHAR` | 策略参数 JSON; required |
| `snapshot_id` | `VARCHAR` | 发布快照标识; required |
| `raw_snapshot_id` | `VARCHAR` | 原始快照标识; required |
| `signal_price_basis` | `VARCHAR` | 信号价格口径; required |
| `execution_price_basis` | `VARCHAR` | 成交价格口径; required |
| `cost_model_json` | `VARCHAR` | 成本模型 JSON; required |
| `engine_version` | `VARCHAR` | 回测引擎版本; required |
| `start_date` | `DATE` | 回测起始日; required |
| `end_date` | `DATE` | 回测结束日; required |
| `benchmark` | `VARCHAR` | 基准指数; required |
| `total_return` | `DOUBLE` | 总收益率; nullable |
| `annual_return` | `DOUBLE` | 年化收益率; required |
| `max_drawdown` | `DOUBLE` | 最大回撤; required |
| `win_rate` | `DOUBLE` | 胜率; required |
| `profit_loss_ratio` | `DOUBLE` | 盈亏比; required |
| `status` | `VARCHAR` | 运行状态; required |
| `created_at` | `TIMESTAMP` | 创建时间; required |
| `notes_json` | `VARCHAR` | 说明与备注 JSON; required |
| `PRIMARY KEY` | `constraint` | backtest_id |

### `backtest_trade`

回测成交明细。

| Column | Type | Notes |
| --- | --- | --- |
| `backtest_id` | `VARCHAR` | 关联回测标识; required |
| `symbol` | `VARCHAR` | 证券代码; required |
| `trade_date` | `DATE` | 成交日期; required |
| `side` | `VARCHAR` | 买卖方向; required |
| `price_basis` | `VARCHAR` | 成交价格口径; required |
| `trade_price` | `DOUBLE` | 成交价; required |
| `quantity` | `INTEGER` | 成交股数; required |
| `notional` | `DOUBLE` | 成交额; required |
| `fee` | `DOUBLE` | 手续费; required |
| `tax` | `DOUBLE` | 印花税; nullable |
| `pnl` | `DOUBLE` | 单笔盈亏; nullable |
| `holding_days` | `INTEGER` | 持有天数; nullable |
| `reason` | `VARCHAR` | 成交原因说明; required |
| `rank_no` | `INTEGER` | 候选排名; required |
| `PRIMARY KEY` | `constraint` | backtest_id, symbol, trade_date, side |

### `backtest_equity_curve`

回测资金曲线。

| Column | Type | Notes |
| --- | --- | --- |
| `backtest_id` | `VARCHAR` | 关联回测标识; required |
| `trade_date` | `DATE` | 交易日; required |
| `position_count` | `INTEGER` | 持仓数量; required |
| `cash` | `DOUBLE` | 现金; required |
| `market_value` | `DOUBLE` | 持仓市值; required |
| `equity` | `DOUBLE` | 总权益; required |
| `drawdown` | `DOUBLE` | 回撤比例; nullable |
| `daily_return` | `DOUBLE` | 单日收益率; nullable |
| `benchmark_close` | `DOUBLE` | 基准收盘价; nullable |
| `updated_at` | `TIMESTAMP` | 写入更新时间; required |
| `PRIMARY KEY` | `constraint` | backtest_id, trade_date |

### `task_run_log`

最小任务运行日志，供页面展示运行状态与最近执行时间。

| Column | Type | Notes |
| --- | --- | --- |
| `task_id` | `VARCHAR` | 任务运行标识; required |
| `task_name` | `VARCHAR` | 任务名称; required |
| `biz_date` | `DATE` | 业务日期; required |
| `snapshot_id` | `VARCHAR` | 关联发布快照; required |
| `attempt_no` | `INTEGER` | 尝试次数; required |
| `status` | `VARCHAR` | 运行状态; required |
| `error_code` | `VARCHAR` | 错误码; nullable |
| `error_message` | `VARCHAR` | 错误信息; nullable |
| `started_at` | `TIMESTAMP` | 开始时间; required |
| `finished_at` | `TIMESTAMP` | 结束时间; required |
| `detail_json` | `VARCHAR` | 补充信息 JSON; nullable |
| `PRIMARY KEY` | `constraint` | task_id |

## Refresh Rule

修改 schema 后，重新运行 `python3 scripts/render_db_schema.py` 刷新本文件。
