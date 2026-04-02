from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class ColumnDefinition:
    name: str
    sql_type: str
    note: str
    allow_null: bool = False
    default_sql: str | None = None


@dataclass(frozen=True)
class TableDefinition:
    group: str
    name: str
    description: str
    columns: tuple[ColumnDefinition, ...]
    primary_key: tuple[str, ...]


TABLE_DEFINITIONS: tuple[TableDefinition, ...] = (
    TableDefinition(
        group="Metadata",
        name="stock_basic",
        description="最小股票主数据，供观察名单和后续日线同步复用。",
        columns=(
            ColumnDefinition("symbol", "VARCHAR", "交易所后缀证券代码"),
            ColumnDefinition("display_name", "VARCHAR", "证券简称"),
            ColumnDefinition("exchange", "VARCHAR", "交易所代码"),
            ColumnDefinition("board", "VARCHAR", "板块分类"),
            ColumnDefinition("industry", "VARCHAR", "一级行业"),
            ColumnDefinition("is_active", "BOOLEAN", "是否仍在活跃股票池中"),
            ColumnDefinition("listed_at", "DATE", "上市日期", allow_null=True),
            ColumnDefinition("updated_at", "TIMESTAMP", "最近一次同步时间"),
        ),
        primary_key=("symbol",),
    ),
    TableDefinition(
        group="Metadata",
        name="trade_calendar",
        description="交易日历，用于后续盘后任务与回测窗口判断。",
        columns=(
            ColumnDefinition("trade_date", "DATE", "交易日"),
            ColumnDefinition("market_code", "VARCHAR", "市场代码"),
            ColumnDefinition("is_open", "BOOLEAN", "是否开市"),
            ColumnDefinition("updated_at", "TIMESTAMP", "最近一次同步时间"),
        ),
        primary_key=("trade_date", "market_code"),
    ),
    TableDefinition(
        group="Metadata",
        name="raw_snapshot",
        description="不可变原始数据快照元数据。",
        columns=(
            ColumnDefinition("raw_snapshot_id", "VARCHAR", "原始快照标识"),
            ColumnDefinition("snapshot_seq", "BIGINT", "原始快照序号"),
            ColumnDefinition("biz_date", "DATE", "业务日期"),
            ColumnDefinition("status", "VARCHAR", "原始快照状态"),
            ColumnDefinition(
                "required_datasets_json",
                "VARCHAR",
                "当前原始快照依赖的数据集 JSON",
            ),
            ColumnDefinition(
                "completeness_json",
                "VARCHAR",
                "完整性与校验结果 JSON",
            ),
            ColumnDefinition(
                "source_watermark_json",
                "VARCHAR",
                "外部数据源水位与来源说明 JSON",
            ),
            ColumnDefinition("created_at", "TIMESTAMP", "快照生成时间"),
            ColumnDefinition("attempt_no", "INTEGER", "生成尝试次数"),
        ),
        primary_key=("raw_snapshot_id",),
    ),
    TableDefinition(
        group="Metadata",
        name="artifact_publish",
        description="页面与标准查询读取的发布快照门禁。",
        columns=(
            ColumnDefinition("snapshot_id", "VARCHAR", "发布快照标识"),
            ColumnDefinition("publish_seq", "BIGINT", "发布序号"),
            ColumnDefinition("biz_date", "DATE", "业务日期"),
            ColumnDefinition("raw_snapshot_id", "VARCHAR", "关联原始快照"),
            ColumnDefinition("status", "VARCHAR", "发布状态"),
            ColumnDefinition("price_basis", "VARCHAR", "价格口径"),
            ColumnDefinition(
                "required_artifacts_json",
                "VARCHAR",
                "当前快照依赖的产物列表 JSON",
            ),
            ColumnDefinition(
                "artifact_status_json",
                "VARCHAR",
                "各产物 READY/BLOCKED 状态 JSON",
            ),
            ColumnDefinition("published_at", "TIMESTAMP", "发布时间"),
            ColumnDefinition("attempt_no", "INTEGER", "发布尝试次数"),
        ),
        primary_key=("snapshot_id",),
    ),
    TableDefinition(
        group="Market Data",
        name="daily_bar",
        description="原始日线行情增量表，后续按 raw_snapshot_id 做 as-of 解析。",
        columns=(
            ColumnDefinition("raw_snapshot_id", "VARCHAR", "原始快照标识"),
            ColumnDefinition("symbol", "VARCHAR", "证券代码"),
            ColumnDefinition("trade_date", "DATE", "交易日"),
            ColumnDefinition("open_raw", "DOUBLE", "原始开盘价", allow_null=True),
            ColumnDefinition("high_raw", "DOUBLE", "原始最高价", allow_null=True),
            ColumnDefinition("low_raw", "DOUBLE", "原始最低价", allow_null=True),
            ColumnDefinition("close_raw", "DOUBLE", "原始收盘价", allow_null=True),
            ColumnDefinition("pre_close_raw", "DOUBLE", "原始前收价", allow_null=True),
            ColumnDefinition("volume", "DOUBLE", "成交量", allow_null=True),
            ColumnDefinition("amount", "DOUBLE", "成交额", allow_null=True),
            ColumnDefinition("turnover_rate", "DOUBLE", "换手率", allow_null=True),
            ColumnDefinition("high_limit", "DOUBLE", "涨停价", allow_null=True),
            ColumnDefinition("low_limit", "DOUBLE", "跌停价", allow_null=True),
            ColumnDefinition("limit_rule_code", "VARCHAR", "涨跌停规则编码", allow_null=True),
            ColumnDefinition("is_suspended", "BOOLEAN", "是否停牌", allow_null=True),
            ColumnDefinition("source", "VARCHAR", "数据来源", allow_null=True),
            ColumnDefinition("updated_at", "TIMESTAMP", "写入更新时间"),
        ),
        primary_key=("raw_snapshot_id", "symbol", "trade_date"),
    ),
    TableDefinition(
        group="Derived Data",
        name="price_series_daily",
        description="复权价格序列，后续供分析与回测读取。",
        columns=(
            ColumnDefinition("symbol", "VARCHAR", "证券代码"),
            ColumnDefinition("trade_date", "DATE", "交易日"),
            ColumnDefinition("price_basis", "VARCHAR", "价格口径"),
            ColumnDefinition("open", "DOUBLE", "开盘价", allow_null=True),
            ColumnDefinition("high", "DOUBLE", "最高价", allow_null=True),
            ColumnDefinition("low", "DOUBLE", "最低价", allow_null=True),
            ColumnDefinition("close", "DOUBLE", "收盘价", allow_null=True),
            ColumnDefinition("pre_close", "DOUBLE", "前收价", allow_null=True),
            ColumnDefinition("adj_factor", "DOUBLE", "复权因子", allow_null=True),
            ColumnDefinition("snapshot_id", "VARCHAR", "发布快照标识"),
            ColumnDefinition("volume", "DOUBLE", "成交量", allow_null=True),
            ColumnDefinition("amount", "DOUBLE", "成交额", allow_null=True),
            ColumnDefinition("updated_at", "TIMESTAMP", "写入更新时间"),
        ),
        primary_key=("snapshot_id", "symbol", "trade_date", "price_basis"),
    ),
    TableDefinition(
        group="Derived Data",
        name="indicator_daily",
        description="技术指标日级结果，供个股页、选股和回测信号读取。",
        columns=(
            ColumnDefinition("symbol", "VARCHAR", "证券代码"),
            ColumnDefinition("trade_date", "DATE", "交易日"),
            ColumnDefinition("snapshot_id", "VARCHAR", "发布快照标识"),
            ColumnDefinition("price_basis", "VARCHAR", "价格口径"),
            ColumnDefinition("ma5", "DOUBLE", "5 日均线", allow_null=True),
            ColumnDefinition("ma10", "DOUBLE", "10 日均线", allow_null=True),
            ColumnDefinition("ma20", "DOUBLE", "20 日均线", allow_null=True),
            ColumnDefinition("ma60", "DOUBLE", "60 日均线", allow_null=True),
            ColumnDefinition("macd_dif", "DOUBLE", "MACD DIF", allow_null=True),
            ColumnDefinition("macd_dea", "DOUBLE", "MACD DEA", allow_null=True),
            ColumnDefinition("macd_hist", "DOUBLE", "MACD HIST", allow_null=True),
            ColumnDefinition("kdj_k", "DOUBLE", "KDJ K", allow_null=True),
            ColumnDefinition("kdj_d", "DOUBLE", "KDJ D", allow_null=True),
            ColumnDefinition("kdj_j", "DOUBLE", "KDJ J", allow_null=True),
            ColumnDefinition("rsi6", "DOUBLE", "RSI6", allow_null=True),
            ColumnDefinition("rsi12", "DOUBLE", "RSI12", allow_null=True),
            ColumnDefinition("boll_upper", "DOUBLE", "布林上轨", allow_null=True),
            ColumnDefinition("boll_mid", "DOUBLE", "布林中轨", allow_null=True),
            ColumnDefinition("boll_lower", "DOUBLE", "布林下轨", allow_null=True),
            ColumnDefinition("volume_ratio", "DOUBLE", "量比", allow_null=True),
            ColumnDefinition("updated_at", "TIMESTAMP", "写入更新时间"),
        ),
        primary_key=("symbol", "trade_date", "price_basis", "snapshot_id"),
    ),
    TableDefinition(
        group="Derived Data",
        name="pattern_signal_daily",
        description="量价与形态信号，一行一个信号，允许同日多信号并存。",
        columns=(
            ColumnDefinition("symbol", "VARCHAR", "证券代码"),
            ColumnDefinition("trade_date", "DATE", "交易日"),
            ColumnDefinition("snapshot_id", "VARCHAR", "发布快照标识"),
            ColumnDefinition("price_basis", "VARCHAR", "价格口径"),
            ColumnDefinition("signal_code", "VARCHAR", "信号编码"),
            ColumnDefinition("signal_type", "VARCHAR", "信号类型"),
            ColumnDefinition("direction", "VARCHAR", "方向"),
            ColumnDefinition("is_triggered", "BOOLEAN", "是否触发"),
            ColumnDefinition("signal_score", "DOUBLE", "信号强度分"),
            ColumnDefinition("payload_json", "VARCHAR", "信号细节 JSON"),
            ColumnDefinition("updated_at", "TIMESTAMP", "写入更新时间"),
        ),
        primary_key=("symbol", "trade_date", "price_basis", "snapshot_id", "signal_code"),
    ),
    TableDefinition(
        group="Derived Data",
        name="capital_feature_daily",
        description="股票日级资金特征聚合结果，供个股页和选股读取。",
        columns=(
            ColumnDefinition("symbol", "VARCHAR", "证券代码"),
            ColumnDefinition("trade_date", "DATE", "交易日"),
            ColumnDefinition("snapshot_id", "VARCHAR", "发布快照标识"),
            ColumnDefinition("main_net_inflow", "DOUBLE", "主力净流入", allow_null=True),
            ColumnDefinition(
                "main_net_inflow_ratio",
                "DOUBLE",
                "主力净流入占成交额比例",
                allow_null=True,
            ),
            ColumnDefinition(
                "super_large_order_inflow",
                "DOUBLE",
                "超大单净流入",
                allow_null=True,
            ),
            ColumnDefinition(
                "large_order_inflow",
                "DOUBLE",
                "大单净流入",
                allow_null=True,
            ),
            ColumnDefinition(
                "northbound_net_inflow",
                "DOUBLE",
                "北向净流入",
                allow_null=True,
            ),
            ColumnDefinition("has_dragon_tiger", "BOOLEAN", "是否带龙虎榜标签"),
            ColumnDefinition("updated_at", "TIMESTAMP", "写入更新时间"),
        ),
        primary_key=("symbol", "trade_date", "snapshot_id"),
    ),
    TableDefinition(
        group="Derived Data",
        name="fundamental_feature_daily",
        description="股票日级财务特征聚合结果，供选股读取 canonical 财务侧信号。",
        columns=(
            ColumnDefinition("symbol", "VARCHAR", "证券代码"),
            ColumnDefinition("trade_date", "DATE", "交易日"),
            ColumnDefinition("snapshot_id", "VARCHAR", "发布快照标识"),
            ColumnDefinition("report_period", "DATE", "财报报告期", allow_null=True),
            ColumnDefinition("ann_date", "DATE", "公告日期", allow_null=True),
            ColumnDefinition("roe_dt", "DOUBLE", "扣非 ROE", allow_null=True),
            ColumnDefinition(
                "grossprofit_margin",
                "DOUBLE",
                "毛利率",
                allow_null=True,
            ),
            ColumnDefinition(
                "debt_to_assets",
                "DOUBLE",
                "资产负债率",
                allow_null=True,
            ),
            ColumnDefinition(
                "total_revenue",
                "DOUBLE",
                "营业总收入",
                allow_null=True,
            ),
            ColumnDefinition(
                "net_profit_attr_p",
                "DOUBLE",
                "归母净利润",
                allow_null=True,
            ),
            ColumnDefinition(
                "n_cashflow_act",
                "DOUBLE",
                "经营活动现金流净额",
                allow_null=True,
            ),
            ColumnDefinition("total_assets", "DOUBLE", "总资产", allow_null=True),
            ColumnDefinition("total_liab", "DOUBLE", "总负债", allow_null=True),
            ColumnDefinition(
                "cash_to_profit",
                "DOUBLE",
                "经营现金流与归母净利润比",
                allow_null=True,
            ),
            ColumnDefinition(
                "fundamental_score",
                "DOUBLE",
                "财务综合分",
                allow_null=True,
            ),
            ColumnDefinition("updated_at", "TIMESTAMP", "写入更新时间"),
        ),
        primary_key=("symbol", "trade_date", "snapshot_id"),
    ),
    TableDefinition(
        group="Derived Data",
        name="market_regime_daily",
        description="市场概览页读取的聚合市场状态。",
        columns=(
            ColumnDefinition("snapshot_id", "VARCHAR", "发布快照标识"),
            ColumnDefinition("trade_date", "DATE", "交易日"),
            ColumnDefinition("summary", "VARCHAR", "市场摘要"),
            ColumnDefinition("regime_label", "VARCHAR", "市场阶段标签"),
            ColumnDefinition("snapshot_source", "VARCHAR", "快照来源说明"),
            ColumnDefinition("indices_json", "VARCHAR", "指数概览 JSON"),
            ColumnDefinition("breadth_json", "VARCHAR", "市场宽度 JSON"),
            ColumnDefinition("highlights_json", "VARCHAR", "重点提示 JSON"),
        ),
        primary_key=("snapshot_id", "trade_date"),
    ),
    TableDefinition(
        group="Runs And Outputs",
        name="screener_run",
        description="选股运行摘要。",
        columns=(
            ColumnDefinition("run_id", "VARCHAR", "运行标识"),
            ColumnDefinition("trade_date", "DATE", "交易日"),
            ColumnDefinition("snapshot_id", "VARCHAR", "发布快照标识"),
            ColumnDefinition("strategy_name", "VARCHAR", "策略名称"),
            ColumnDefinition("strategy_version", "VARCHAR", "策略版本"),
            ColumnDefinition("signal_price_basis", "VARCHAR", "信号价格口径"),
            ColumnDefinition("universe_size", "INTEGER", "股票池规模"),
            ColumnDefinition("result_count", "INTEGER", "结果条数"),
            ColumnDefinition("status", "VARCHAR", "运行状态"),
            ColumnDefinition("as_of_date", "DATE", "结果口径日期"),
            ColumnDefinition("started_at", "TIMESTAMP", "开始时间"),
            ColumnDefinition("finished_at", "TIMESTAMP", "结束时间"),
        ),
        primary_key=("run_id",),
    ),
    TableDefinition(
        group="Runs And Outputs",
        name="screener_result",
        description="选股结果明细。",
        columns=(
            ColumnDefinition("run_id", "VARCHAR", "关联 screener_run"),
            ColumnDefinition("symbol", "VARCHAR", "证券代码"),
            ColumnDefinition("trade_date", "DATE", "交易日"),
            ColumnDefinition("strategy_name", "VARCHAR", "策略名称"),
            ColumnDefinition("snapshot_id", "VARCHAR", "发布快照标识"),
            ColumnDefinition("signal_price_basis", "VARCHAR", "信号价格口径"),
            ColumnDefinition("total_score", "INTEGER", "总分"),
            ColumnDefinition("trend_score", "DOUBLE", "趋势分", allow_null=True),
            ColumnDefinition("price_volume_score", "DOUBLE", "量价分", allow_null=True),
            ColumnDefinition("capital_score", "DOUBLE", "资金分", allow_null=True),
            ColumnDefinition("fundamental_score", "DOUBLE", "基础过滤分", allow_null=True),
            ColumnDefinition("display_name", "VARCHAR", "证券简称"),
            ColumnDefinition("thesis", "VARCHAR", "投资主线摘要"),
            ColumnDefinition("matched_rules_json", "VARCHAR", "命中信号 JSON"),
            ColumnDefinition("risk_flags_json", "VARCHAR", "风险标签 JSON"),
            ColumnDefinition("rank_no", "INTEGER", "排序名次"),
        ),
        primary_key=("run_id", "symbol"),
    ),
    TableDefinition(
        group="Runs And Outputs",
        name="backtest_request",
        description="持久化回测请求，当前作为本地 durable queue 的最小载体。",
        columns=(
            ColumnDefinition("backtest_id", "VARCHAR", "回测标识"),
            ColumnDefinition("requested_at", "TIMESTAMP", "请求创建时间"),
            ColumnDefinition("snapshot_id", "VARCHAR", "发布快照标识"),
            ColumnDefinition("raw_snapshot_id", "VARCHAR", "原始快照标识"),
            ColumnDefinition("strategy_version", "VARCHAR", "策略版本"),
            ColumnDefinition("signal_price_basis", "VARCHAR", "信号价格口径"),
            ColumnDefinition("payload_json", "VARCHAR", "请求负载 JSON"),
            ColumnDefinition("status", "VARCHAR", "请求状态"),
            ColumnDefinition("retry_count", "INTEGER", "重试次数"),
            ColumnDefinition("last_error", "VARCHAR", "最近错误信息", allow_null=True),
        ),
        primary_key=("backtest_id",),
    ),
    TableDefinition(
        group="Runs And Outputs",
        name="backtest_run",
        description="回测运行摘要。",
        columns=(
            ColumnDefinition("backtest_id", "VARCHAR", "回测标识"),
            ColumnDefinition("strategy_name", "VARCHAR", "策略名称"),
            ColumnDefinition("strategy_version", "VARCHAR", "策略版本"),
            ColumnDefinition("param_json", "VARCHAR", "策略参数 JSON"),
            ColumnDefinition("snapshot_id", "VARCHAR", "发布快照标识"),
            ColumnDefinition("raw_snapshot_id", "VARCHAR", "原始快照标识"),
            ColumnDefinition("signal_price_basis", "VARCHAR", "信号价格口径"),
            ColumnDefinition("execution_price_basis", "VARCHAR", "成交价格口径"),
            ColumnDefinition("cost_model_json", "VARCHAR", "成本模型 JSON"),
            ColumnDefinition("engine_version", "VARCHAR", "回测引擎版本"),
            ColumnDefinition("start_date", "DATE", "回测起始日"),
            ColumnDefinition("end_date", "DATE", "回测结束日"),
            ColumnDefinition("benchmark", "VARCHAR", "基准指数"),
            ColumnDefinition("total_return", "DOUBLE", "总收益率", allow_null=True),
            ColumnDefinition("annual_return", "DOUBLE", "年化收益率"),
            ColumnDefinition("max_drawdown", "DOUBLE", "最大回撤"),
            ColumnDefinition("win_rate", "DOUBLE", "胜率"),
            ColumnDefinition("profit_loss_ratio", "DOUBLE", "盈亏比"),
            ColumnDefinition("status", "VARCHAR", "运行状态"),
            ColumnDefinition("created_at", "TIMESTAMP", "创建时间"),
            ColumnDefinition("notes_json", "VARCHAR", "说明与备注 JSON"),
        ),
        primary_key=("backtest_id",),
    ),
    TableDefinition(
        group="Runs And Outputs",
        name="backtest_trade",
        description="回测成交明细。",
        columns=(
            ColumnDefinition("backtest_id", "VARCHAR", "关联回测标识"),
            ColumnDefinition("symbol", "VARCHAR", "证券代码"),
            ColumnDefinition("trade_date", "DATE", "成交日期"),
            ColumnDefinition("side", "VARCHAR", "买卖方向"),
            ColumnDefinition("price_basis", "VARCHAR", "成交价格口径"),
            ColumnDefinition("trade_price", "DOUBLE", "成交价"),
            ColumnDefinition("quantity", "INTEGER", "成交股数"),
            ColumnDefinition("notional", "DOUBLE", "成交额"),
            ColumnDefinition("fee", "DOUBLE", "手续费"),
            ColumnDefinition("tax", "DOUBLE", "印花税", allow_null=True),
            ColumnDefinition("pnl", "DOUBLE", "单笔盈亏", allow_null=True),
            ColumnDefinition("holding_days", "INTEGER", "持有天数", allow_null=True),
            ColumnDefinition("reason", "VARCHAR", "成交原因说明"),
            ColumnDefinition("rank_no", "INTEGER", "候选排名"),
        ),
        primary_key=("backtest_id", "symbol", "trade_date", "side"),
    ),
    TableDefinition(
        group="Runs And Outputs",
        name="backtest_equity_curve",
        description="回测资金曲线。",
        columns=(
            ColumnDefinition("backtest_id", "VARCHAR", "关联回测标识"),
            ColumnDefinition("trade_date", "DATE", "交易日"),
            ColumnDefinition("position_count", "INTEGER", "持仓数量"),
            ColumnDefinition("cash", "DOUBLE", "现金"),
            ColumnDefinition("market_value", "DOUBLE", "持仓市值"),
            ColumnDefinition("equity", "DOUBLE", "总权益"),
            ColumnDefinition("drawdown", "DOUBLE", "回撤比例", allow_null=True),
            ColumnDefinition("daily_return", "DOUBLE", "单日收益率", allow_null=True),
            ColumnDefinition("benchmark_close", "DOUBLE", "基准收盘价", allow_null=True),
            ColumnDefinition("updated_at", "TIMESTAMP", "写入更新时间"),
        ),
        primary_key=("backtest_id", "trade_date"),
    ),
    TableDefinition(
        group="Runs And Outputs",
        name="task_run_log",
        description="最小任务运行日志，供页面展示运行状态与最近执行时间。",
        columns=(
            ColumnDefinition("task_id", "VARCHAR", "任务运行标识"),
            ColumnDefinition("task_name", "VARCHAR", "任务名称"),
            ColumnDefinition("biz_date", "DATE", "业务日期"),
            ColumnDefinition("snapshot_id", "VARCHAR", "关联发布快照"),
            ColumnDefinition("attempt_no", "INTEGER", "尝试次数"),
            ColumnDefinition("status", "VARCHAR", "运行状态"),
            ColumnDefinition("error_code", "VARCHAR", "错误码", allow_null=True),
            ColumnDefinition("error_message", "VARCHAR", "错误信息", allow_null=True),
            ColumnDefinition("started_at", "TIMESTAMP", "开始时间"),
            ColumnDefinition("finished_at", "TIMESTAMP", "结束时间"),
            ColumnDefinition("detail_json", "VARCHAR", "补充信息 JSON", allow_null=True),
        ),
        primary_key=("task_id",),
    ),
)


def iter_ddl_statements() -> tuple[str, ...]:
    statements: list[str] = []
    for table in TABLE_DEFINITIONS:
        column_lines: list[str] = []
        for column in table.columns:
            line = f"{column.name} {column.sql_type}"
            if not column.allow_null:
                line += " NOT NULL"
            if column.default_sql is not None:
                line += f" DEFAULT {column.default_sql}"
            column_lines.append(line)
        if table.primary_key:
            column_lines.append(f"PRIMARY KEY ({', '.join(table.primary_key)})")
        statements.append(
            "CREATE TABLE IF NOT EXISTS "
            f"{table.name} (\n  " + ",\n  ".join(column_lines) + "\n)"
        )
    return tuple(statements)


def render_schema_markdown() -> str:
    lines = [
        "# DB Schema Snapshot",
        "",
        "This file is generated from `backend/app/domains/market_data/schema.py`.",
        "",
        "当前内容表示仓库里已经落地到 DuckDB 的最小表结构，不再是纯规划态列表。",
        "",
    ]

    grouped_tables: dict[str, list[TableDefinition]] = {}
    for table in TABLE_DEFINITIONS:
        grouped_tables.setdefault(table.group, []).append(table)

    for group, tables in grouped_tables.items():
        lines.append(f"## {group}")
        lines.append("")
        for table in tables:
            lines.append(f"### `{table.name}`")
            lines.append("")
            lines.append(table.description)
            lines.append("")
            lines.append("| Column | Type | Notes |")
            lines.append("| --- | --- | --- |")
            for column in table.columns:
                nullability = "nullable" if column.allow_null else "required"
                lines.append(
                    f"| `{column.name}` | `{column.sql_type}` | {column.note}; {nullability} |"
                )
            if table.primary_key:
                lines.append(
                    f"| `PRIMARY KEY` | `constraint` | {', '.join(table.primary_key)} |"
                )
            lines.append("")

    lines.extend(
        [
            "## Refresh Rule",
            "",
            "修改 schema 后，重新运行 `python3 scripts/render_db_schema.py` 刷新本文件。",
        ]
    )
    return "\n".join(lines) + "\n"
