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
| `biz_date` | `DATE` | 业务日期; required |
| `status` | `VARCHAR` | 原始快照状态; required |
| `source_name` | `VARCHAR` | 当前快照来源; required |
| `created_at` | `TIMESTAMP` | 快照生成时间; required |
| `notes_json` | `VARCHAR` | 补充信息 JSON; nullable |
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
| `open_price` | `DOUBLE` | 开盘价; nullable |
| `high_price` | `DOUBLE` | 最高价; nullable |
| `low_price` | `DOUBLE` | 最低价; nullable |
| `close_price` | `DOUBLE` | 收盘价; nullable |
| `pre_close_price` | `DOUBLE` | 前收价; nullable |
| `volume` | `DOUBLE` | 成交量; nullable |
| `amount` | `DOUBLE` | 成交额; nullable |
| `turnover_rate` | `DOUBLE` | 换手率; nullable |
| `is_suspended` | `BOOLEAN` | 是否停牌; nullable |
| `PRIMARY KEY` | `constraint` | raw_snapshot_id, symbol, trade_date |

## Derived Data

### `price_series_daily`

复权价格序列，后续供分析与回测读取。

| Column | Type | Notes |
| --- | --- | --- |
| `snapshot_id` | `VARCHAR` | 发布快照标识; required |
| `symbol` | `VARCHAR` | 证券代码; required |
| `trade_date` | `DATE` | 交易日; required |
| `price_basis` | `VARCHAR` | 价格口径; required |
| `open_price` | `DOUBLE` | 开盘价; nullable |
| `high_price` | `DOUBLE` | 最高价; nullable |
| `low_price` | `DOUBLE` | 最低价; nullable |
| `close_price` | `DOUBLE` | 收盘价; nullable |
| `volume` | `DOUBLE` | 成交量; nullable |
| `amount` | `DOUBLE` | 成交额; nullable |
| `PRIMARY KEY` | `constraint` | snapshot_id, symbol, trade_date, price_basis |

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
| `display_name` | `VARCHAR` | 证券简称; required |
| `thesis` | `VARCHAR` | 投资主线摘要; required |
| `matched_rules_json` | `VARCHAR` | 命中信号 JSON; required |
| `risk_flags_json` | `VARCHAR` | 风险标签 JSON; required |
| `rank_no` | `INTEGER` | 排序名次; required |
| `PRIMARY KEY` | `constraint` | run_id, symbol |

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
