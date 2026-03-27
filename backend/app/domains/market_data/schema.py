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
            ColumnDefinition("biz_date", "DATE", "业务日期"),
            ColumnDefinition("status", "VARCHAR", "原始快照状态"),
            ColumnDefinition("source_name", "VARCHAR", "当前快照来源"),
            ColumnDefinition("created_at", "TIMESTAMP", "快照生成时间"),
            ColumnDefinition("notes_json", "VARCHAR", "补充信息 JSON", allow_null=True),
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
            ColumnDefinition("open_price", "DOUBLE", "开盘价", allow_null=True),
            ColumnDefinition("high_price", "DOUBLE", "最高价", allow_null=True),
            ColumnDefinition("low_price", "DOUBLE", "最低价", allow_null=True),
            ColumnDefinition("close_price", "DOUBLE", "收盘价", allow_null=True),
            ColumnDefinition("pre_close_price", "DOUBLE", "前收价", allow_null=True),
            ColumnDefinition("volume", "DOUBLE", "成交量", allow_null=True),
            ColumnDefinition("amount", "DOUBLE", "成交额", allow_null=True),
            ColumnDefinition("turnover_rate", "DOUBLE", "换手率", allow_null=True),
            ColumnDefinition("is_suspended", "BOOLEAN", "是否停牌", allow_null=True),
        ),
        primary_key=("raw_snapshot_id", "symbol", "trade_date"),
    ),
    TableDefinition(
        group="Derived Data",
        name="price_series_daily",
        description="复权价格序列，后续供分析与回测读取。",
        columns=(
            ColumnDefinition("snapshot_id", "VARCHAR", "发布快照标识"),
            ColumnDefinition("symbol", "VARCHAR", "证券代码"),
            ColumnDefinition("trade_date", "DATE", "交易日"),
            ColumnDefinition("price_basis", "VARCHAR", "价格口径"),
            ColumnDefinition("open_price", "DOUBLE", "开盘价", allow_null=True),
            ColumnDefinition("high_price", "DOUBLE", "最高价", allow_null=True),
            ColumnDefinition("low_price", "DOUBLE", "最低价", allow_null=True),
            ColumnDefinition("close_price", "DOUBLE", "收盘价", allow_null=True),
            ColumnDefinition("volume", "DOUBLE", "成交量", allow_null=True),
            ColumnDefinition("amount", "DOUBLE", "成交额", allow_null=True),
        ),
        primary_key=("snapshot_id", "symbol", "trade_date", "price_basis"),
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
