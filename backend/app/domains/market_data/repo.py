from __future__ import annotations

from datetime import datetime, timedelta, timezone
import json
from typing import Any

from backend.app.app_wiring.settings import AppSettings
from backend.app.shared.providers.duckdb import connect_duckdb
from backend.app.shared.telemetry.alerts import load_recent_alerts, summarize_recent_alerts


CN_TZ = timezone(timedelta(hours=8))


def _decode_json_text(raw_value: str | None, fallback: Any) -> Any:
    if not raw_value:
        return fallback
    return json.loads(raw_value)


def _isoformat(value: object) -> str:
    if isinstance(value, datetime):
        normalized = value if value.tzinfo is not None else value.replace(tzinfo=CN_TZ)
        return normalized.isoformat()
    if hasattr(value, "isoformat"):
        return str(value.isoformat())
    return str(value)


def _open_connection(settings: AppSettings):
    return connect_duckdb(settings.duckdb_path, read_only=True)


def _fetch_published_snapshot_meta(
    connection,
    snapshot_id: str | None = None,
) -> dict[str, object]:
    if snapshot_id:
        row = connection.execute(
            """
            SELECT
              snapshot_id,
              publish_seq,
              biz_date,
              raw_snapshot_id,
              status,
              published_at,
              price_basis
            FROM artifact_publish
            WHERE snapshot_id = ?
            LIMIT 1
            """,
            [snapshot_id],
        ).fetchone()
    else:
        row = connection.execute(
            """
            SELECT
              snapshot_id,
              publish_seq,
              biz_date,
              raw_snapshot_id,
              status,
              published_at,
              price_basis
            FROM artifact_publish
            WHERE status = 'READY'
            ORDER BY published_at DESC, publish_seq DESC
            LIMIT 1
            """
        ).fetchone()

    if row is None:
        raise LookupError(f"Unknown snapshot_id: {snapshot_id or 'latest READY'}")

    (
        resolved_snapshot_id,
        publish_seq,
        biz_date,
        raw_snapshot_id,
        status,
        published_at,
        price_basis,
    ) = row
    return {
        "snapshot_id": str(resolved_snapshot_id),
        "publish_seq": int(publish_seq),
        "biz_date": _isoformat(biz_date),
        "raw_snapshot_id": str(raw_snapshot_id),
        "status": str(status),
        "published_at": _isoformat(published_at),
        "price_basis": str(price_basis),
    }


def _fetch_published_snapshot_meta_by_raw_snapshot(
    connection,
    raw_snapshot_id: str,
) -> dict[str, object]:
    row = connection.execute(
        """
        SELECT
          snapshot_id,
          publish_seq,
          biz_date,
          raw_snapshot_id,
          status,
          published_at,
          price_basis
        FROM artifact_publish
        WHERE raw_snapshot_id = ?
        ORDER BY publish_seq DESC
        LIMIT 1
        """,
        [raw_snapshot_id],
    ).fetchone()
    if row is None:
        raise LookupError(f"No published snapshot linked to raw_snapshot_id={raw_snapshot_id}")

    (
        resolved_snapshot_id,
        publish_seq,
        biz_date,
        resolved_raw_snapshot_id,
        status,
        published_at,
        price_basis,
    ) = row
    return {
        "snapshot_id": str(resolved_snapshot_id),
        "publish_seq": int(publish_seq),
        "biz_date": _isoformat(biz_date),
        "raw_snapshot_id": str(resolved_raw_snapshot_id),
        "status": str(status),
        "published_at": _isoformat(published_at),
        "price_basis": str(price_basis),
    }


def _fetch_raw_snapshot_meta(
    connection,
    raw_snapshot_id: str,
) -> dict[str, object]:
    row = connection.execute(
        """
        SELECT
          raw_snapshot_id,
          snapshot_seq,
          biz_date,
          status,
          source_watermark_json,
          created_at
        FROM raw_snapshot
        WHERE raw_snapshot_id = ?
        LIMIT 1
        """,
        [raw_snapshot_id],
    ).fetchone()
    if row is None:
        raise LookupError(f"Unknown raw_snapshot_id: {raw_snapshot_id}")

    (
        resolved_raw_snapshot_id,
        snapshot_seq,
        biz_date,
        status,
        source_watermark_json,
        created_at,
    ) = row
    return {
        "raw_snapshot_id": str(resolved_raw_snapshot_id),
        "snapshot_seq": int(snapshot_seq),
        "biz_date": _isoformat(biz_date),
        "status": str(status),
        "source_watermark": _decode_json_text(source_watermark_json, {}),
        "created_at": _isoformat(created_at),
    }


def _fetch_stock_profile(connection, symbol: str) -> dict[str, object]:
    row = connection.execute(
        """
        SELECT
          symbol,
          display_name,
          exchange,
          board,
          industry
        FROM stock_basic
        WHERE symbol = ?
        LIMIT 1
        """,
        [symbol],
    ).fetchone()
    if row is None:
        raise LookupError(f"Unknown symbol: {symbol}")

    resolved_symbol, display_name, exchange, board, industry = row
    return {
        "symbol": str(resolved_symbol),
        "display_name": str(display_name),
        "exchange": str(exchange),
        "board": str(board),
        "industry": str(industry),
    }


def _query_daily_bar_asof_rows(
    connection,
    *,
    raw_snapshot_id: str,
    symbol: str,
    date_from: str | None,
    date_to: str | None,
) -> list[dict[str, object]]:
    rows = connection.execute(
        """
        WITH target AS (
          SELECT snapshot_seq
          FROM raw_snapshot
          WHERE raw_snapshot_id = ?
        ),
        ranked AS (
          SELECT
            db.trade_date,
            db.open_raw,
            db.high_raw,
            db.low_raw,
            db.close_raw,
            db.pre_close_raw,
            db.volume,
            db.amount,
            db.turnover_rate,
            db.high_limit,
            db.low_limit,
            db.limit_rule_code,
            db.is_suspended,
            db.source,
            db.updated_at,
            db.raw_snapshot_id AS effective_raw_snapshot_id,
            rs.snapshot_seq AS effective_snapshot_seq,
            ROW_NUMBER() OVER (
              PARTITION BY db.symbol, db.trade_date
              ORDER BY rs.snapshot_seq DESC
            ) AS row_num
          FROM daily_bar db
          JOIN raw_snapshot rs
            ON rs.raw_snapshot_id = db.raw_snapshot_id
          JOIN target
            ON rs.snapshot_seq <= target.snapshot_seq
          WHERE db.symbol = ?
            AND (? IS NULL OR db.trade_date >= CAST(? AS DATE))
            AND (? IS NULL OR db.trade_date <= CAST(? AS DATE))
        )
        SELECT
          trade_date,
          open_raw,
          high_raw,
          low_raw,
          close_raw,
          pre_close_raw,
          volume,
          amount,
          turnover_rate,
          high_limit,
          low_limit,
          limit_rule_code,
          is_suspended,
          source,
          updated_at,
          effective_raw_snapshot_id,
          effective_snapshot_seq
        FROM ranked
        WHERE row_num = 1
        ORDER BY trade_date ASC
        """,
        [
            raw_snapshot_id,
            symbol,
            date_from,
            date_from,
            date_to,
            date_to,
        ],
    ).fetchall()

    return [
        {
            "trade_date": _isoformat(trade_date),
            "open_raw": float(open_raw),
            "high_raw": float(high_raw),
            "low_raw": float(low_raw),
            "close_raw": float(close_raw),
            "pre_close_raw": float(pre_close_raw),
            "volume": float(volume) if volume is not None else None,
            "amount": float(amount) if amount is not None else None,
            "turnover_rate": float(turnover_rate) if turnover_rate is not None else None,
            "high_limit": float(high_limit) if high_limit is not None else None,
            "low_limit": float(low_limit) if low_limit is not None else None,
            "limit_rule_code": str(limit_rule_code) if limit_rule_code is not None else None,
            "is_suspended": bool(is_suspended) if is_suspended is not None else None,
            "source": str(source) if source is not None else None,
            "updated_at": _isoformat(updated_at),
            "effective_raw_snapshot_id": str(effective_raw_snapshot_id),
            "effective_snapshot_seq": int(effective_snapshot_seq),
        }
        for (
            trade_date,
            open_raw,
            high_raw,
            low_raw,
            close_raw,
            pre_close_raw,
            volume,
            amount,
            turnover_rate,
            high_limit,
            low_limit,
            limit_rule_code,
            is_suspended,
            source,
            updated_at,
            effective_raw_snapshot_id,
            effective_snapshot_seq,
        ) in rows
    ]


def _query_price_series_asof_rows(
    connection,
    *,
    snapshot_id: str,
    symbol: str,
    price_basis: str,
    date_from: str | None,
    date_to: str | None,
) -> list[dict[str, object]]:
    rows = connection.execute(
        """
        WITH target AS (
          SELECT publish_seq
          FROM artifact_publish
          WHERE snapshot_id = ?
        ),
        ranked AS (
          SELECT
            ps.trade_date,
            ps.open,
            ps.high,
            ps.low,
            ps.close,
            ps.pre_close,
            ps.adj_factor,
            ps.volume,
            ps.amount,
            ps.updated_at,
            ps.snapshot_id AS effective_snapshot_id,
            ap.publish_seq AS effective_publish_seq,
            ROW_NUMBER() OVER (
              PARTITION BY ps.symbol, ps.trade_date, ps.price_basis
              ORDER BY ap.publish_seq DESC
            ) AS row_num
          FROM price_series_daily ps
          JOIN artifact_publish ap
            ON ap.snapshot_id = ps.snapshot_id
          JOIN target
            ON ap.publish_seq <= target.publish_seq
          WHERE ps.symbol = ?
            AND ps.price_basis = ?
            AND (? IS NULL OR ps.trade_date >= CAST(? AS DATE))
            AND (? IS NULL OR ps.trade_date <= CAST(? AS DATE))
        )
        SELECT
          trade_date,
          open,
          high,
          low,
          close,
          pre_close,
          adj_factor,
          volume,
          amount,
          updated_at,
          effective_snapshot_id,
          effective_publish_seq
        FROM ranked
        WHERE row_num = 1
        ORDER BY trade_date ASC
        """,
        [
            snapshot_id,
            symbol,
            price_basis,
            date_from,
            date_from,
            date_to,
            date_to,
        ],
    ).fetchall()

    return [
        {
            "trade_date": _isoformat(trade_date),
            "open": float(open),
            "high": float(high),
            "low": float(low),
            "close": float(close),
            "pre_close": float(pre_close),
            "adj_factor": float(adj_factor) if adj_factor is not None else None,
            "volume": float(volume) if volume is not None else None,
            "amount": float(amount) if amount is not None else None,
            "updated_at": _isoformat(updated_at),
            "effective_snapshot_id": str(effective_snapshot_id),
            "effective_publish_seq": int(effective_publish_seq),
        }
        for (
            trade_date,
            open,
            high,
            low,
            close,
            pre_close,
            adj_factor,
            volume,
            amount,
            updated_at,
            effective_snapshot_id,
            effective_publish_seq,
        ) in rows
    ]


def _query_indicator_asof_rows(
    connection,
    *,
    snapshot_id: str,
    symbol: str,
    price_basis: str,
    date_from: str | None,
    date_to: str | None,
) -> list[dict[str, object]]:
    rows = connection.execute(
        """
        WITH target AS (
          SELECT publish_seq
          FROM artifact_publish
          WHERE snapshot_id = ?
        ),
        ranked AS (
          SELECT
            ind.trade_date,
            ind.ma5,
            ind.ma10,
            ind.ma20,
            ind.ma60,
            ind.macd_dif,
            ind.macd_dea,
            ind.macd_hist,
            ind.kdj_k,
            ind.kdj_d,
            ind.kdj_j,
            ind.rsi6,
            ind.rsi12,
            ind.boll_upper,
            ind.boll_mid,
            ind.boll_lower,
            ind.volume_ratio,
            ind.updated_at,
            ind.snapshot_id AS effective_snapshot_id,
            ap.publish_seq AS effective_publish_seq,
            ROW_NUMBER() OVER (
              PARTITION BY ind.symbol, ind.trade_date, ind.price_basis
              ORDER BY ap.publish_seq DESC
            ) AS row_num
          FROM indicator_daily ind
          JOIN artifact_publish ap
            ON ap.snapshot_id = ind.snapshot_id
          JOIN target
            ON ap.publish_seq <= target.publish_seq
          WHERE ind.symbol = ?
            AND ind.price_basis = ?
            AND (? IS NULL OR ind.trade_date >= CAST(? AS DATE))
            AND (? IS NULL OR ind.trade_date <= CAST(? AS DATE))
        )
        SELECT
          trade_date,
          ma5,
          ma10,
          ma20,
          ma60,
          macd_dif,
          macd_dea,
          macd_hist,
          kdj_k,
          kdj_d,
          kdj_j,
          rsi6,
          rsi12,
          boll_upper,
          boll_mid,
          boll_lower,
          volume_ratio,
          updated_at,
          effective_snapshot_id,
          effective_publish_seq
        FROM ranked
        WHERE row_num = 1
        ORDER BY trade_date ASC
        """,
        [
            snapshot_id,
            symbol,
            price_basis,
            date_from,
            date_from,
            date_to,
            date_to,
        ],
    ).fetchall()

    return [
        {
            "trade_date": _isoformat(trade_date),
            "ma5": float(ma5) if ma5 is not None else None,
            "ma10": float(ma10) if ma10 is not None else None,
            "ma20": float(ma20) if ma20 is not None else None,
            "ma60": float(ma60) if ma60 is not None else None,
            "macd_dif": float(macd_dif) if macd_dif is not None else None,
            "macd_dea": float(macd_dea) if macd_dea is not None else None,
            "macd_hist": float(macd_hist) if macd_hist is not None else None,
            "kdj_k": float(kdj_k) if kdj_k is not None else None,
            "kdj_d": float(kdj_d) if kdj_d is not None else None,
            "kdj_j": float(kdj_j) if kdj_j is not None else None,
            "rsi6": float(rsi6) if rsi6 is not None else None,
            "rsi12": float(rsi12) if rsi12 is not None else None,
            "boll_upper": float(boll_upper) if boll_upper is not None else None,
            "boll_mid": float(boll_mid) if boll_mid is not None else None,
            "boll_lower": float(boll_lower) if boll_lower is not None else None,
            "volume_ratio": float(volume_ratio) if volume_ratio is not None else None,
            "updated_at": _isoformat(updated_at),
            "effective_snapshot_id": str(effective_snapshot_id),
            "effective_publish_seq": int(effective_publish_seq),
        }
        for (
            trade_date,
            ma5,
            ma10,
            ma20,
            ma60,
            macd_dif,
            macd_dea,
            macd_hist,
            kdj_k,
            kdj_d,
            kdj_j,
            rsi6,
            rsi12,
            boll_upper,
            boll_mid,
            boll_lower,
            volume_ratio,
            updated_at,
            effective_snapshot_id,
            effective_publish_seq,
        ) in rows
    ]


def _query_pattern_signal_asof_rows(
    connection,
    *,
    snapshot_id: str,
    symbol: str,
    price_basis: str,
    date_from: str | None,
    date_to: str | None,
) -> list[dict[str, object]]:
    rows = connection.execute(
        """
        WITH target AS (
          SELECT publish_seq
          FROM artifact_publish
          WHERE snapshot_id = ?
        ),
        ranked AS (
          SELECT
            ps.trade_date,
            ps.signal_code,
            ps.signal_type,
            ps.direction,
            ps.is_triggered,
            ps.signal_score,
            ps.payload_json,
            ps.updated_at,
            ps.snapshot_id AS effective_snapshot_id,
            ap.publish_seq AS effective_publish_seq,
            ROW_NUMBER() OVER (
              PARTITION BY ps.symbol, ps.trade_date, ps.price_basis, ps.signal_code
              ORDER BY ap.publish_seq DESC
            ) AS row_num
          FROM pattern_signal_daily ps
          JOIN artifact_publish ap
            ON ap.snapshot_id = ps.snapshot_id
          JOIN target
            ON ap.publish_seq <= target.publish_seq
          WHERE ps.symbol = ?
            AND ps.price_basis = ?
            AND (? IS NULL OR ps.trade_date >= CAST(? AS DATE))
            AND (? IS NULL OR ps.trade_date <= CAST(? AS DATE))
        )
        SELECT
          trade_date,
          signal_code,
          signal_type,
          direction,
          is_triggered,
          signal_score,
          payload_json,
          updated_at,
          effective_snapshot_id,
          effective_publish_seq
        FROM ranked
        WHERE row_num = 1
        ORDER BY trade_date ASC, signal_code ASC
        """,
        [
            snapshot_id,
            symbol,
            price_basis,
            date_from,
            date_from,
            date_to,
            date_to,
        ],
    ).fetchall()

    return [
        {
            "trade_date": _isoformat(trade_date),
            "signal_code": str(signal_code),
            "signal_type": str(signal_type),
            "direction": str(direction),
            "is_triggered": bool(is_triggered),
            "signal_score": float(signal_score),
            "payload": _decode_json_text(payload_json, {}),
            "updated_at": _isoformat(updated_at),
            "effective_snapshot_id": str(effective_snapshot_id),
            "effective_publish_seq": int(effective_publish_seq),
        }
        for (
            trade_date,
            signal_code,
            signal_type,
            direction,
            is_triggered,
            signal_score,
            payload_json,
            updated_at,
            effective_snapshot_id,
            effective_publish_seq,
        ) in rows
    ]


def _query_capital_feature_asof_rows(
    connection,
    *,
    snapshot_id: str,
    symbol: str,
    date_from: str | None,
    date_to: str | None,
) -> list[dict[str, object]]:
    rows = connection.execute(
        """
        WITH target AS (
          SELECT publish_seq
          FROM artifact_publish
          WHERE snapshot_id = ?
        ),
        ranked AS (
          SELECT
            cf.trade_date,
            cf.main_net_inflow,
            cf.main_net_inflow_ratio,
            cf.super_large_order_inflow,
            cf.large_order_inflow,
            cf.northbound_net_inflow,
            cf.has_dragon_tiger,
            cf.updated_at,
            cf.snapshot_id AS effective_snapshot_id,
            ap.publish_seq AS effective_publish_seq,
            ROW_NUMBER() OVER (
              PARTITION BY cf.symbol, cf.trade_date
              ORDER BY ap.publish_seq DESC
            ) AS row_num
          FROM capital_feature_daily cf
          JOIN artifact_publish ap
            ON ap.snapshot_id = cf.snapshot_id
          JOIN target
            ON ap.publish_seq <= target.publish_seq
          WHERE cf.symbol = ?
            AND (? IS NULL OR cf.trade_date >= CAST(? AS DATE))
            AND (? IS NULL OR cf.trade_date <= CAST(? AS DATE))
        )
        SELECT
          trade_date,
          main_net_inflow,
          main_net_inflow_ratio,
          super_large_order_inflow,
          large_order_inflow,
          northbound_net_inflow,
          has_dragon_tiger,
          updated_at,
          effective_snapshot_id,
          effective_publish_seq
        FROM ranked
        WHERE row_num = 1
        ORDER BY trade_date ASC
        """,
        [
            snapshot_id,
            symbol,
            date_from,
            date_from,
            date_to,
            date_to,
        ],
    ).fetchall()

    return [
        {
            "trade_date": _isoformat(trade_date),
            "main_net_inflow": float(main_net_inflow) if main_net_inflow is not None else None,
            "main_net_inflow_ratio": float(main_net_inflow_ratio)
            if main_net_inflow_ratio is not None
            else None,
            "super_large_order_inflow": float(super_large_order_inflow)
            if super_large_order_inflow is not None
            else None,
            "large_order_inflow": float(large_order_inflow)
            if large_order_inflow is not None
            else None,
            "northbound_net_inflow": float(northbound_net_inflow)
            if northbound_net_inflow is not None
            else None,
            "has_dragon_tiger": bool(has_dragon_tiger),
            "updated_at": _isoformat(updated_at),
            "effective_snapshot_id": str(effective_snapshot_id),
            "effective_publish_seq": int(effective_publish_seq),
        }
        for (
            trade_date,
            main_net_inflow,
            main_net_inflow_ratio,
            super_large_order_inflow,
            large_order_inflow,
            northbound_net_inflow,
            has_dragon_tiger,
            updated_at,
            effective_snapshot_id,
            effective_publish_seq,
        ) in rows
    ]


def _query_fundamental_feature_asof_rows(
    connection,
    *,
    snapshot_id: str,
    symbol: str,
    date_from: str | None,
    date_to: str | None,
) -> list[dict[str, object]]:
    rows = connection.execute(
        """
        WITH target AS (
          SELECT publish_seq
          FROM artifact_publish
          WHERE snapshot_id = ?
        ),
        ranked AS (
          SELECT
            ff.trade_date,
            ff.report_period,
            ff.ann_date,
            ff.roe_dt,
            ff.grossprofit_margin,
            ff.debt_to_assets,
            ff.total_revenue,
            ff.net_profit_attr_p,
            ff.n_cashflow_act,
            ff.total_assets,
            ff.total_liab,
            ff.cash_to_profit,
            ff.fundamental_score,
            ff.updated_at,
            ff.snapshot_id AS effective_snapshot_id,
            ap.publish_seq AS effective_publish_seq,
            ROW_NUMBER() OVER (
              PARTITION BY ff.symbol, ff.trade_date
              ORDER BY ap.publish_seq DESC
            ) AS row_num
          FROM fundamental_feature_daily ff
          JOIN artifact_publish ap
            ON ap.snapshot_id = ff.snapshot_id
          JOIN target
            ON ap.publish_seq <= target.publish_seq
          WHERE ff.symbol = ?
            AND (? IS NULL OR ff.trade_date >= CAST(? AS DATE))
            AND (? IS NULL OR ff.trade_date <= CAST(? AS DATE))
        )
        SELECT
          trade_date,
          report_period,
          ann_date,
          roe_dt,
          grossprofit_margin,
          debt_to_assets,
          total_revenue,
          net_profit_attr_p,
          n_cashflow_act,
          total_assets,
          total_liab,
          cash_to_profit,
          fundamental_score,
          updated_at,
          effective_snapshot_id,
          effective_publish_seq
        FROM ranked
        WHERE row_num = 1
        ORDER BY trade_date ASC
        """,
        [
            snapshot_id,
            symbol,
            date_from,
            date_from,
            date_to,
            date_to,
        ],
    ).fetchall()

    return [
        {
            "trade_date": _isoformat(trade_date),
            "report_period": _isoformat(report_period),
            "ann_date": _isoformat(ann_date),
            "roe_dt": float(roe_dt) if roe_dt is not None else None,
            "grossprofit_margin": float(grossprofit_margin)
            if grossprofit_margin is not None
            else None,
            "debt_to_assets": float(debt_to_assets)
            if debt_to_assets is not None
            else None,
            "total_revenue": float(total_revenue) if total_revenue is not None else None,
            "net_profit_attr_p": float(net_profit_attr_p)
            if net_profit_attr_p is not None
            else None,
            "n_cashflow_act": float(n_cashflow_act)
            if n_cashflow_act is not None
            else None,
            "total_assets": float(total_assets) if total_assets is not None else None,
            "total_liab": float(total_liab) if total_liab is not None else None,
            "cash_to_profit": float(cash_to_profit)
            if cash_to_profit is not None
            else None,
            "fundamental_score": float(fundamental_score)
            if fundamental_score is not None
            else None,
            "updated_at": _isoformat(updated_at),
            "effective_snapshot_id": str(effective_snapshot_id),
            "effective_publish_seq": int(effective_publish_seq),
        }
        for (
            trade_date,
            report_period,
            ann_date,
            roe_dt,
            grossprofit_margin,
            debt_to_assets,
            total_revenue,
            net_profit_attr_p,
            n_cashflow_act,
            total_assets,
            total_liab,
            cash_to_profit,
            fundamental_score,
            updated_at,
            effective_snapshot_id,
            effective_publish_seq,
        ) in rows
    ]


def _query_official_disclosure_asof_rows(
    connection,
    *,
    snapshot_id: str,
    symbol: str,
    date_from: str | None,
    date_to: str | None,
) -> list[dict[str, object]]:
    rows = connection.execute(
        """
        WITH target AS (
          SELECT publish_seq
          FROM artifact_publish
          WHERE snapshot_id = ?
        ),
        ranked AS (
          SELECT
            od.trade_date,
            od.announcement_id,
            od.org_id,
            od.title,
            od.short_title,
            od.announcement_time,
            od.announcement_type,
            od.announcement_type_name,
            od.page_column,
            od.adjunct_type,
            od.pdf_url,
            od.detail_url,
            od.source,
            od.updated_at,
            od.snapshot_id AS effective_snapshot_id,
            ap.publish_seq AS effective_publish_seq,
            ROW_NUMBER() OVER (
              PARTITION BY od.symbol, od.announcement_id
              ORDER BY ap.publish_seq DESC
            ) AS row_num
          FROM official_disclosure_item od
          JOIN artifact_publish ap
            ON ap.snapshot_id = od.snapshot_id
          JOIN target
            ON ap.publish_seq <= target.publish_seq
          WHERE od.symbol = ?
            AND (? IS NULL OR od.trade_date >= CAST(? AS DATE))
            AND (? IS NULL OR od.trade_date <= CAST(? AS DATE))
        )
        SELECT
          trade_date,
          announcement_id,
          org_id,
          title,
          short_title,
          announcement_time,
          announcement_type,
          announcement_type_name,
          page_column,
          adjunct_type,
          pdf_url,
          detail_url,
          source,
          updated_at,
          effective_snapshot_id,
          effective_publish_seq
        FROM ranked
        WHERE row_num = 1
        ORDER BY trade_date ASC, announcement_time ASC, announcement_id ASC
        """,
        [
            snapshot_id,
            symbol,
            date_from,
            date_from,
            date_to,
            date_to,
        ],
    ).fetchall()

    return [
        {
            "trade_date": _isoformat(trade_date),
            "announcement_id": str(announcement_id),
            "org_id": str(org_id),
            "title": str(title),
            "short_title": str(short_title) if short_title else None,
            "announcement_time": _isoformat(announcement_time)
            if announcement_time is not None
            else None,
            "announcement_type": str(announcement_type)
            if announcement_type
            else None,
            "announcement_type_name": str(announcement_type_name)
            if announcement_type_name
            else None,
            "page_column": str(page_column) if page_column else None,
            "adjunct_type": str(adjunct_type) if adjunct_type else None,
            "pdf_url": str(pdf_url) if pdf_url else None,
            "detail_url": str(detail_url) if detail_url else None,
            "source": str(source),
            "updated_at": _isoformat(updated_at),
            "effective_snapshot_id": str(effective_snapshot_id),
            "effective_publish_seq": int(effective_publish_seq),
        }
        for (
            trade_date,
            announcement_id,
            org_id,
            title,
            short_title,
            announcement_time,
            announcement_type,
            announcement_type_name,
            page_column,
            adjunct_type,
            pdf_url,
            detail_url,
            source,
            updated_at,
            effective_snapshot_id,
            effective_publish_seq,
        ) in rows
    ]


def _query_corporate_action_asof_rows(
    connection,
    *,
    snapshot_id: str,
    symbol: str,
    date_from: str | None,
    date_to: str | None,
) -> list[dict[str, object]]:
    rows = connection.execute(
        """
        WITH target AS (
          SELECT publish_seq
          FROM artifact_publish
          WHERE snapshot_id = ?
        ),
        ranked AS (
          SELECT
            ca.trade_date,
            ca.action_id,
            ca.report_period,
            ca.knowledge_date,
            ca.ann_date,
            ca.imp_ann_date,
            ca.record_date,
            ca.ex_date,
            ca.pay_date,
            ca.div_listdate,
            ca.stock_div,
            ca.cash_div_tax,
            ca.action_stage,
            ca.action_summary,
            ca.source,
            ca.updated_at,
            ca.snapshot_id AS effective_snapshot_id,
            ap.publish_seq AS effective_publish_seq,
            ROW_NUMBER() OVER (
              PARTITION BY ca.symbol, ca.action_id
              ORDER BY ap.publish_seq DESC
            ) AS row_num
          FROM corporate_action_item ca
          JOIN artifact_publish ap
            ON ap.snapshot_id = ca.snapshot_id
          JOIN target
            ON ap.publish_seq <= target.publish_seq
          WHERE ca.symbol = ?
            AND (? IS NULL OR ca.trade_date >= CAST(? AS DATE))
            AND (? IS NULL OR ca.trade_date <= CAST(? AS DATE))
        )
        SELECT
          trade_date,
          action_id,
          report_period,
          knowledge_date,
          ann_date,
          imp_ann_date,
          record_date,
          ex_date,
          pay_date,
          div_listdate,
          stock_div,
          cash_div_tax,
          action_stage,
          action_summary,
          source,
          updated_at,
          effective_snapshot_id,
          effective_publish_seq
        FROM ranked
        WHERE row_num = 1
        ORDER BY trade_date ASC, knowledge_date ASC, action_id ASC
        """,
        [
            snapshot_id,
            symbol,
            date_from,
            date_from,
            date_to,
            date_to,
        ],
    ).fetchall()

    return [
        {
            "trade_date": _isoformat(trade_date),
            "action_id": str(action_id),
            "report_period": _isoformat(report_period) if report_period is not None else None,
            "knowledge_date": _isoformat(knowledge_date) if knowledge_date is not None else None,
            "ann_date": _isoformat(ann_date) if ann_date is not None else None,
            "imp_ann_date": _isoformat(imp_ann_date) if imp_ann_date is not None else None,
            "record_date": _isoformat(record_date) if record_date is not None else None,
            "ex_date": _isoformat(ex_date) if ex_date is not None else None,
            "pay_date": _isoformat(pay_date) if pay_date is not None else None,
            "div_listdate": _isoformat(div_listdate) if div_listdate is not None else None,
            "stock_div": float(stock_div) if stock_div is not None else None,
            "cash_div_tax": float(cash_div_tax) if cash_div_tax is not None else None,
            "action_stage": str(action_stage) if action_stage else None,
            "action_summary": str(action_summary) if action_summary else None,
            "source": str(source),
            "updated_at": _isoformat(updated_at),
            "effective_snapshot_id": str(effective_snapshot_id),
            "effective_publish_seq": int(effective_publish_seq),
        }
        for (
            trade_date,
            action_id,
            report_period,
            knowledge_date,
            ann_date,
            imp_ann_date,
            record_date,
            ex_date,
            pay_date,
            div_listdate,
            stock_div,
            cash_div_tax,
            action_stage,
            action_summary,
            source,
            updated_at,
            effective_snapshot_id,
            effective_publish_seq,
        ) in rows
    ]


def _build_range_summary(items: list[dict[str, object]]) -> dict[str, object]:
    if not items:
        return {"row_count": 0, "date_from": None, "date_to": None}
    return {
        "row_count": len(items),
        "date_from": items[0]["trade_date"],
        "date_to": items[-1]["trade_date"],
    }


def load_latest_published_snapshot(settings: AppSettings) -> dict[str, object]:
    connection = _open_connection(settings)
    try:
        latest_snapshot = _fetch_published_snapshot_meta(connection)
        raw_snapshot = _fetch_raw_snapshot_meta(
            connection,
            str(latest_snapshot["raw_snapshot_id"]),
        )

        market_row = connection.execute(
            """
            SELECT
              trade_date,
              summary,
              regime_label,
              snapshot_source,
              indices_json,
              breadth_json,
              highlights_json
            FROM market_regime_daily
            WHERE snapshot_id = ?
            ORDER BY trade_date DESC
            LIMIT 1
            """,
            [latest_snapshot["snapshot_id"]],
        ).fetchone()
        if market_row is None:
            raise RuntimeError(
                f"No market overview row found for snapshot_id={latest_snapshot['snapshot_id']}"
            )

        (
            trade_date,
            market_summary,
            regime_label,
            snapshot_source,
            indices_json,
            breadth_json,
            highlights_json,
        ) = market_row

        screener_run_row = connection.execute(
            """
            SELECT
              run_id,
              strategy_name,
              as_of_date,
              signal_price_basis
            FROM screener_run
            WHERE snapshot_id = ?
            ORDER BY finished_at DESC, started_at DESC
            LIMIT 1
            """,
            [latest_snapshot["snapshot_id"]],
        ).fetchone()
        if screener_run_row is None:
            raise RuntimeError(
                f"No screener run found for snapshot_id={latest_snapshot['snapshot_id']}"
            )

        (
            screener_run_id,
            screener_strategy_name,
            screener_as_of_date,
            screener_signal_price_basis,
        ) = screener_run_row

        screener_rows = connection.execute(
            """
            SELECT
              symbol,
              display_name,
              strategy_name,
              total_score,
              trend_score,
              price_volume_score,
              capital_score,
              fundamental_score,
              thesis,
              matched_rules_json,
              risk_flags_json
            FROM screener_result
            WHERE run_id = ?
            ORDER BY rank_no ASC, symbol ASC
            """,
            [screener_run_id],
        ).fetchall()

        backtest_row = connection.execute(
            """
            SELECT
              strategy_name,
              start_date,
              end_date,
              annual_return,
              max_drawdown,
              win_rate,
              profit_loss_ratio,
              notes_json
            FROM backtest_run
            WHERE snapshot_id = ?
            ORDER BY created_at DESC
            LIMIT 1
            """,
            [latest_snapshot["snapshot_id"]],
        ).fetchone()
        if backtest_row is None:
            raise RuntimeError(
                f"No backtest run found for snapshot_id={latest_snapshot['snapshot_id']}"
            )

        (
            backtest_strategy_name,
            backtest_start_date,
            backtest_end_date,
            annual_return,
            max_drawdown,
            win_rate,
            profit_loss_ratio,
            backtest_notes_json,
        ) = backtest_row

        task_rows = connection.execute(
            """
            SELECT
              task_name,
              status,
              finished_at,
              detail_json
            FROM task_run_log
            WHERE snapshot_id = ?
            ORDER BY finished_at DESC, task_name ASC
            """,
            [latest_snapshot["snapshot_id"]],
        ).fetchall()

        task_status: dict[str, object] = {}
        last_run = None
        next_window = None
        for task_name, task_state, finished_at, detail_json in task_rows:
            task_status[str(task_name)] = str(task_state)
            if last_run is None and finished_at is not None:
                last_run = _isoformat(finished_at)
            detail = _decode_json_text(detail_json, {})
            if isinstance(detail, dict) and not next_window:
                detail_next_window = detail.get("next_window")
                if isinstance(detail_next_window, str) and detail_next_window:
                    next_window = detail_next_window

        if last_run is not None:
            task_status["last_run"] = last_run
        if next_window is not None:
            task_status["next_window"] = next_window

        return {
            "snapshot_id": latest_snapshot["snapshot_id"],
            "raw_snapshot_id": latest_snapshot["raw_snapshot_id"],
            "status": latest_snapshot["status"],
            "generated_at": latest_snapshot["published_at"],
            "price_basis": latest_snapshot["price_basis"],
            "source_watermark": raw_snapshot["source_watermark"],
            "shadow_validation": raw_snapshot["source_watermark"].get(
                "shadow_validation",
                {
                    "status": "UNKNOWN",
                    "providers": [],
                },
            ),
            "market_overview": {
                "trade_date": _isoformat(trade_date),
                "summary": str(market_summary),
                "regime_label": str(regime_label),
                "snapshot_source": str(snapshot_source),
                "indices": _decode_json_text(indices_json, []),
                "breadth": _decode_json_text(breadth_json, {}),
                "highlights": _decode_json_text(highlights_json, []),
            },
            "screener": {
                "strategy_name": str(screener_strategy_name),
                "as_of_date": _isoformat(screener_as_of_date),
                "signal_price_basis": str(screener_signal_price_basis),
                "top_candidates": [
                    {
                        "symbol": str(symbol),
                        "name": str(display_name),
                        "strategy_name": str(result_strategy_name),
                        "score": int(total_score),
                        "trend_score": float(trend_score) if trend_score is not None else None,
                        "price_volume_score": float(price_volume_score)
                        if price_volume_score is not None
                        else None,
                        "capital_score": float(capital_score)
                        if capital_score is not None
                        else None,
                        "fundamental_score": float(fundamental_score)
                        if fundamental_score is not None
                        else None,
                        "thesis": str(thesis),
                        "signals": _decode_json_text(matched_rules_json, []),
                        "risks": _decode_json_text(risk_flags_json, []),
                    }
                    for (
                        symbol,
                        display_name,
                        result_strategy_name,
                        total_score,
                        trend_score,
                        price_volume_score,
                        capital_score,
                        fundamental_score,
                        thesis,
                        matched_rules_json,
                        risk_flags_json,
                    ) in screener_rows
                ],
            },
            "backtest": {
                "strategy_name": str(backtest_strategy_name),
                "window": f"{_isoformat(backtest_start_date)} to {_isoformat(backtest_end_date)}",
                "metrics": {
                    "cagr_pct": float(annual_return),
                    "max_drawdown_pct": float(max_drawdown),
                    "win_rate_pct": float(win_rate),
                    "profit_factor": float(profit_loss_ratio),
                },
                "notes": _decode_json_text(backtest_notes_json, []),
            },
            "task_status": task_status,
        }
    finally:
        connection.close()


def load_stock_snapshot(
    settings: AppSettings,
    *,
    symbol: str,
    snapshot_id: str | None = None,
    raw_snapshot_id: str | None = None,
    price_basis: str | None = None,
) -> dict[str, object]:
    connection = _open_connection(settings)
    try:
        stock = _fetch_stock_profile(connection, symbol)
        published_snapshot = _fetch_published_snapshot_meta(connection, snapshot_id)
        resolved_raw_snapshot_id = raw_snapshot_id or str(published_snapshot["raw_snapshot_id"])
        if (
            raw_snapshot_id is not None
            and str(published_snapshot["raw_snapshot_id"]) != raw_snapshot_id
        ):
            raise ValueError(
                "snapshot_id and raw_snapshot_id must point to the same published snapshot"
            )

        raw_snapshot = _fetch_raw_snapshot_meta(connection, resolved_raw_snapshot_id)
        resolved_price_basis = price_basis or str(published_snapshot["price_basis"])

        daily_bar_items = _query_daily_bar_asof_rows(
            connection,
            raw_snapshot_id=resolved_raw_snapshot_id,
            symbol=symbol,
            date_from=None,
            date_to=None,
        )
        price_series_items = _query_price_series_asof_rows(
            connection,
            snapshot_id=str(published_snapshot["snapshot_id"]),
            symbol=symbol,
            price_basis=resolved_price_basis,
            date_from=None,
            date_to=None,
        )

        return {
            "symbol": stock["symbol"],
            "display_name": stock["display_name"],
            "exchange": stock["exchange"],
            "board": stock["board"],
            "industry": stock["industry"],
            "as_of": {
                "snapshot_id": published_snapshot["snapshot_id"],
                "publish_seq": published_snapshot["publish_seq"],
                "raw_snapshot_id": raw_snapshot["raw_snapshot_id"],
                "snapshot_seq": raw_snapshot["snapshot_seq"],
                "price_basis": resolved_price_basis,
                "published_at": published_snapshot["published_at"],
                "raw_created_at": raw_snapshot["created_at"],
            },
            "available_series": {
                "daily_bar": _build_range_summary(daily_bar_items),
                "price_series": _build_range_summary(price_series_items),
                "fundamental_feature": _build_range_summary(
                    _query_fundamental_feature_asof_rows(
                        connection,
                        snapshot_id=str(published_snapshot["snapshot_id"]),
                        symbol=symbol,
                        date_from=None,
                        date_to=None,
                    )
                ),
                "official_disclosure": _build_range_summary(
                    _query_official_disclosure_asof_rows(
                        connection,
                        snapshot_id=str(published_snapshot["snapshot_id"]),
                        symbol=symbol,
                        date_from=None,
                        date_to=None,
                    )
                ),
                "corporate_action": _build_range_summary(
                    _query_corporate_action_asof_rows(
                        connection,
                        snapshot_id=str(published_snapshot["snapshot_id"]),
                        symbol=symbol,
                        date_from=None,
                        date_to=None,
                    )
                ),
            },
            "latest_daily_bar": daily_bar_items[-1] if daily_bar_items else None,
            "latest_price_bar": price_series_items[-1] if price_series_items else None,
        }
    finally:
        connection.close()


def load_stock_kline_asof(
    settings: AppSettings,
    *,
    symbol: str,
    dataset: str,
    snapshot_id: str | None = None,
    raw_snapshot_id: str | None = None,
    price_basis: str | None = None,
    date_from: str | None = None,
    date_to: str | None = None,
) -> dict[str, object]:
    connection = _open_connection(settings)
    try:
        stock = _fetch_stock_profile(connection, symbol)

        if dataset == "daily_bar":
            if raw_snapshot_id is not None:
                published_snapshot = (
                    _fetch_published_snapshot_meta(connection, snapshot_id)
                    if snapshot_id is not None
                    else _fetch_published_snapshot_meta_by_raw_snapshot(
                        connection,
                        raw_snapshot_id,
                    )
                )
                resolved_raw_snapshot_id = raw_snapshot_id
            else:
                published_snapshot = _fetch_published_snapshot_meta(connection, snapshot_id)
                resolved_raw_snapshot_id = str(published_snapshot["raw_snapshot_id"])

            raw_snapshot = _fetch_raw_snapshot_meta(connection, resolved_raw_snapshot_id)
            items = _query_daily_bar_asof_rows(
                connection,
                raw_snapshot_id=resolved_raw_snapshot_id,
                symbol=symbol,
                date_from=date_from,
                date_to=date_to,
            )
            return {
                "symbol": stock["symbol"],
                "display_name": stock["display_name"],
                "dataset": dataset,
                "as_of": {
                    "raw_snapshot_id": raw_snapshot["raw_snapshot_id"],
                    "snapshot_seq": raw_snapshot["snapshot_seq"],
                    "linked_snapshot_id": published_snapshot["snapshot_id"],
                },
                "range": _build_range_summary(items),
                "items": items,
            }

        published_snapshot = _fetch_published_snapshot_meta(connection, snapshot_id)
        if dataset == "price_series":
            resolved_price_basis = price_basis or str(published_snapshot["price_basis"])
            items = _query_price_series_asof_rows(
                connection,
                snapshot_id=str(published_snapshot["snapshot_id"]),
                symbol=symbol,
                price_basis=resolved_price_basis,
                date_from=date_from,
                date_to=date_to,
            )
            return {
                "symbol": stock["symbol"],
                "display_name": stock["display_name"],
                "dataset": dataset,
                "as_of": {
                    "snapshot_id": published_snapshot["snapshot_id"],
                    "publish_seq": published_snapshot["publish_seq"],
                    "raw_snapshot_id": published_snapshot["raw_snapshot_id"],
                    "price_basis": resolved_price_basis,
                },
                "range": _build_range_summary(items),
                "items": items,
            }

        raise ValueError(f"Unsupported dataset: {dataset}")
    finally:
        connection.close()


def load_stock_indicators(
    settings: AppSettings,
    *,
    symbol: str,
    snapshot_id: str | None = None,
    price_basis: str | None = None,
    date_from: str | None = None,
    date_to: str | None = None,
) -> dict[str, object]:
    connection = _open_connection(settings)
    try:
        stock = _fetch_stock_profile(connection, symbol)
        published_snapshot = _fetch_published_snapshot_meta(connection, snapshot_id)
        resolved_price_basis = price_basis or str(published_snapshot["price_basis"])

        indicator_items = _query_indicator_asof_rows(
            connection,
            snapshot_id=str(published_snapshot["snapshot_id"]),
            symbol=symbol,
            price_basis=resolved_price_basis,
            date_from=date_from,
            date_to=date_to,
        )
        pattern_items = _query_pattern_signal_asof_rows(
            connection,
            snapshot_id=str(published_snapshot["snapshot_id"]),
            symbol=symbol,
            price_basis=resolved_price_basis,
            date_from=date_from,
            date_to=date_to,
        )

        latest_trade_date = indicator_items[-1]["trade_date"] if indicator_items else None
        latest_patterns = [
            item for item in pattern_items if item["trade_date"] == latest_trade_date
        ]

        return {
            "symbol": stock["symbol"],
            "display_name": stock["display_name"],
            "as_of": {
                "snapshot_id": published_snapshot["snapshot_id"],
                "publish_seq": published_snapshot["publish_seq"],
                "price_basis": resolved_price_basis,
                "raw_snapshot_id": published_snapshot["raw_snapshot_id"],
            },
            "range": _build_range_summary(indicator_items),
            "latest_indicator": indicator_items[-1] if indicator_items else None,
            "latest_patterns": latest_patterns,
            "indicator_items": indicator_items,
            "pattern_items": pattern_items,
        }
    finally:
        connection.close()


def load_stock_capital_flow(
    settings: AppSettings,
    *,
    symbol: str,
    snapshot_id: str | None = None,
    date_from: str | None = None,
    date_to: str | None = None,
) -> dict[str, object]:
    connection = _open_connection(settings)
    try:
        stock = _fetch_stock_profile(connection, symbol)
        published_snapshot = _fetch_published_snapshot_meta(connection, snapshot_id)
        items = _query_capital_feature_asof_rows(
            connection,
            snapshot_id=str(published_snapshot["snapshot_id"]),
            symbol=symbol,
            date_from=date_from,
            date_to=date_to,
        )

        return {
            "symbol": stock["symbol"],
            "display_name": stock["display_name"],
            "as_of": {
                "snapshot_id": published_snapshot["snapshot_id"],
                "publish_seq": published_snapshot["publish_seq"],
                "raw_snapshot_id": published_snapshot["raw_snapshot_id"],
            },
            "range": _build_range_summary(items),
            "latest_capital_feature": items[-1] if items else None,
            "items": items,
        }
    finally:
        connection.close()


def load_stock_fundamentals(
    settings: AppSettings,
    *,
    symbol: str,
    snapshot_id: str | None = None,
    date_from: str | None = None,
    date_to: str | None = None,
) -> dict[str, object]:
    connection = _open_connection(settings)
    try:
        stock = _fetch_stock_profile(connection, symbol)
        published_snapshot = _fetch_published_snapshot_meta(connection, snapshot_id)
        items = _query_fundamental_feature_asof_rows(
            connection,
            snapshot_id=str(published_snapshot["snapshot_id"]),
            symbol=symbol,
            date_from=date_from,
            date_to=date_to,
        )

        return {
            "symbol": stock["symbol"],
            "display_name": stock["display_name"],
            "as_of": {
                "snapshot_id": published_snapshot["snapshot_id"],
                "publish_seq": published_snapshot["publish_seq"],
                "raw_snapshot_id": published_snapshot["raw_snapshot_id"],
            },
            "range": _build_range_summary(items),
            "latest_fundamental_feature": items[-1] if items else None,
            "items": items,
        }
    finally:
        connection.close()


def load_stock_disclosures(
    settings: AppSettings,
    *,
    symbol: str,
    snapshot_id: str | None = None,
    date_from: str | None = None,
    date_to: str | None = None,
) -> dict[str, object]:
    connection = _open_connection(settings)
    try:
        stock = _fetch_stock_profile(connection, symbol)
        published_snapshot = _fetch_published_snapshot_meta(connection, snapshot_id)
        items = _query_official_disclosure_asof_rows(
            connection,
            snapshot_id=str(published_snapshot["snapshot_id"]),
            symbol=symbol,
            date_from=date_from,
            date_to=date_to,
        )

        return {
            "symbol": stock["symbol"],
            "display_name": stock["display_name"],
            "as_of": {
                "snapshot_id": published_snapshot["snapshot_id"],
                "publish_seq": published_snapshot["publish_seq"],
                "raw_snapshot_id": published_snapshot["raw_snapshot_id"],
            },
            "range": _build_range_summary(items),
            "latest_disclosure": items[-1] if items else None,
            "items": items,
        }
    finally:
        connection.close()


def load_stock_corporate_actions(
    settings: AppSettings,
    *,
    symbol: str,
    snapshot_id: str | None = None,
    date_from: str | None = None,
    date_to: str | None = None,
) -> dict[str, object]:
    connection = _open_connection(settings)
    try:
        stock = _fetch_stock_profile(connection, symbol)
        published_snapshot = _fetch_published_snapshot_meta(connection, snapshot_id)
        items = _query_corporate_action_asof_rows(
            connection,
            snapshot_id=str(published_snapshot["snapshot_id"]),
            symbol=symbol,
            date_from=date_from,
            date_to=date_to,
        )

        return {
            "symbol": stock["symbol"],
            "display_name": stock["display_name"],
            "as_of": {
                "snapshot_id": published_snapshot["snapshot_id"],
                "publish_seq": published_snapshot["publish_seq"],
                "raw_snapshot_id": published_snapshot["raw_snapshot_id"],
            },
            "range": _build_range_summary(items),
            "latest_corporate_action": items[-1] if items else None,
            "items": items,
        }
    finally:
        connection.close()


def _fetch_screener_run_meta(
    connection,
    *,
    run_id: str | None = None,
    snapshot_id: str | None = None,
) -> dict[str, object]:
    if run_id is not None:
        row = connection.execute(
            """
            SELECT
              run_id,
              trade_date,
              snapshot_id,
              strategy_name,
              strategy_version,
              signal_price_basis,
              universe_size,
              result_count,
              status,
              as_of_date,
              started_at,
              finished_at
            FROM screener_run
            WHERE run_id = ?
            LIMIT 1
            """,
            [run_id],
        ).fetchone()
    elif snapshot_id is not None:
        row = connection.execute(
            """
            SELECT
              run_id,
              trade_date,
              snapshot_id,
              strategy_name,
              strategy_version,
              signal_price_basis,
              universe_size,
              result_count,
              status,
              as_of_date,
              started_at,
              finished_at
            FROM screener_run
            WHERE snapshot_id = ?
            ORDER BY finished_at DESC, started_at DESC
            LIMIT 1
            """,
            [snapshot_id],
        ).fetchone()
    else:
        row = connection.execute(
            """
            SELECT
              run_id,
              trade_date,
              snapshot_id,
              strategy_name,
              strategy_version,
              signal_price_basis,
              universe_size,
              result_count,
              status,
              as_of_date,
              started_at,
              finished_at
            FROM screener_run
            ORDER BY finished_at DESC, started_at DESC
            LIMIT 1
            """
        ).fetchone()

    if row is None:
        raise LookupError(f"Unknown screener run: {run_id or snapshot_id or 'latest'}")

    (
        resolved_run_id,
        trade_date,
        resolved_snapshot_id,
        strategy_name,
        strategy_version,
        signal_price_basis,
        universe_size,
        result_count,
        status,
        as_of_date,
        started_at,
        finished_at,
    ) = row
    return {
        "run_id": str(resolved_run_id),
        "trade_date": _isoformat(trade_date),
        "snapshot_id": str(resolved_snapshot_id),
        "strategy_name": str(strategy_name),
        "strategy_version": str(strategy_version),
        "signal_price_basis": str(signal_price_basis),
        "universe_size": int(universe_size),
        "result_count": int(result_count),
        "status": str(status),
        "as_of_date": _isoformat(as_of_date),
        "started_at": _isoformat(started_at),
        "finished_at": _isoformat(finished_at),
    }


def load_screener_run(
    settings: AppSettings,
    *,
    run_id: str | None = None,
    snapshot_id: str | None = None,
) -> dict[str, object]:
    connection = _open_connection(settings)
    try:
        resolved_snapshot_id = (
            str(_fetch_published_snapshot_meta(connection, snapshot_id)["snapshot_id"])
            if snapshot_id is not None and run_id is None
            else snapshot_id
        )
        run = _fetch_screener_run_meta(
            connection,
            run_id=run_id,
            snapshot_id=resolved_snapshot_id,
        )
        result_rows = connection.execute(
            """
            SELECT
              symbol,
              display_name,
              trade_date,
              strategy_name,
              total_score,
              trend_score,
              price_volume_score,
              capital_score,
              fundamental_score,
              thesis,
              matched_rules_json,
              risk_flags_json,
              rank_no
            FROM screener_result
            WHERE run_id = ?
            ORDER BY rank_no ASC, symbol ASC
            """,
            [run["run_id"]],
        ).fetchall()

        return {
            **run,
            "results": [
                {
                    "symbol": str(symbol),
                    "display_name": str(display_name),
                    "trade_date": _isoformat(trade_date),
                    "strategy_name": str(strategy_name),
                    "score": int(total_score),
                    "trend_score": float(trend_score) if trend_score is not None else None,
                    "price_volume_score": float(price_volume_score)
                    if price_volume_score is not None
                    else None,
                    "capital_score": float(capital_score)
                    if capital_score is not None
                    else None,
                    "fundamental_score": float(fundamental_score)
                    if fundamental_score is not None
                    else None,
                    "thesis": str(thesis),
                    "signals": _decode_json_text(matched_rules_json, []),
                    "risks": _decode_json_text(risk_flags_json, []),
                    "rank_no": int(rank_no),
                }
                for (
                    symbol,
                    display_name,
                    trade_date,
                    strategy_name,
                    total_score,
                    trend_score,
                    price_volume_score,
                    capital_score,
                    fundamental_score,
                    thesis,
                    matched_rules_json,
                    risk_flags_json,
                    rank_no,
                ) in result_rows
            ],
        }
    finally:
        connection.close()


def _fetch_backtest_run_meta(
    connection,
    *,
    backtest_id: str | None = None,
    snapshot_id: str | None = None,
) -> dict[str, object]:
    if backtest_id is not None:
        row = connection.execute(
            """
            SELECT
              backtest_id,
              strategy_name,
              strategy_version,
              param_json,
              snapshot_id,
              raw_snapshot_id,
              signal_price_basis,
              execution_price_basis,
              cost_model_json,
              engine_version,
              start_date,
              end_date,
              benchmark,
              total_return,
              annual_return,
              max_drawdown,
              win_rate,
              profit_loss_ratio,
              status,
              created_at,
              notes_json
            FROM backtest_run
            WHERE backtest_id = ?
            LIMIT 1
            """,
            [backtest_id],
        ).fetchone()
    elif snapshot_id is not None:
        row = connection.execute(
            """
            SELECT
              backtest_id,
              strategy_name,
              strategy_version,
              param_json,
              snapshot_id,
              raw_snapshot_id,
              signal_price_basis,
              execution_price_basis,
              cost_model_json,
              engine_version,
              start_date,
              end_date,
              benchmark,
              total_return,
              annual_return,
              max_drawdown,
              win_rate,
              profit_loss_ratio,
              status,
              created_at,
              notes_json
            FROM backtest_run
            WHERE snapshot_id = ?
            ORDER BY created_at DESC
            LIMIT 1
            """,
            [snapshot_id],
        ).fetchone()
    else:
        row = connection.execute(
            """
            SELECT
              backtest_id,
              strategy_name,
              strategy_version,
              param_json,
              snapshot_id,
              raw_snapshot_id,
              signal_price_basis,
              execution_price_basis,
              cost_model_json,
              engine_version,
              start_date,
              end_date,
              benchmark,
              total_return,
              annual_return,
              max_drawdown,
              win_rate,
              profit_loss_ratio,
              status,
              created_at,
              notes_json
            FROM backtest_run
            ORDER BY created_at DESC
            LIMIT 1
            """
        ).fetchone()

    if row is None:
        raise LookupError(
            f"Unknown backtest run: {backtest_id or snapshot_id or 'latest'}"
        )

    (
        resolved_backtest_id,
        strategy_name,
        strategy_version,
        param_json,
        resolved_snapshot_id,
        raw_snapshot_id,
        signal_price_basis,
        execution_price_basis,
        cost_model_json,
        engine_version,
        start_date,
        end_date,
        benchmark,
        total_return,
        annual_return,
        max_drawdown,
        win_rate,
        profit_loss_ratio,
        status,
        created_at,
        notes_json,
    ) = row
    return {
        "backtest_id": str(resolved_backtest_id),
        "strategy_name": str(strategy_name),
        "strategy_version": str(strategy_version),
        "params": _decode_json_text(param_json, {}),
        "snapshot_id": str(resolved_snapshot_id),
        "raw_snapshot_id": str(raw_snapshot_id),
        "signal_price_basis": str(signal_price_basis),
        "execution_price_basis": str(execution_price_basis),
        "cost_model": _decode_json_text(cost_model_json, {}),
        "engine_version": str(engine_version),
        "start_date": _isoformat(start_date),
        "end_date": _isoformat(end_date),
        "benchmark": str(benchmark),
        "metrics": {
            "total_return_pct": float(total_return) if total_return is not None else None,
            "annual_return_pct": float(annual_return) if annual_return is not None else None,
            "max_drawdown_pct": float(max_drawdown)
            if max_drawdown is not None
            else None,
            "win_rate_pct": float(win_rate) if win_rate is not None else None,
            "profit_factor": float(profit_loss_ratio)
            if profit_loss_ratio is not None
            else None,
        },
        "status": str(status),
        "created_at": _isoformat(created_at),
        "notes": _decode_json_text(notes_json, []),
    }


def _fetch_backtest_request_meta(
    connection,
    *,
    backtest_id: str,
) -> dict[str, object] | None:
    row = connection.execute(
        """
        SELECT
          backtest_id,
          requested_at,
          snapshot_id,
          raw_snapshot_id,
          strategy_version,
          signal_price_basis,
          payload_json,
          status,
          retry_count,
          last_error
        FROM backtest_request
        WHERE backtest_id = ?
        LIMIT 1
        """,
        [backtest_id],
    ).fetchone()
    if row is None:
        return None

    (
        resolved_backtest_id,
        requested_at,
        snapshot_id,
        raw_snapshot_id,
        strategy_version,
        signal_price_basis,
        payload_json,
        status,
        retry_count,
        last_error,
    ) = row
    payload = _decode_json_text(payload_json, {})
    return {
        "backtest_id": str(resolved_backtest_id),
        "requested_at": _isoformat(requested_at),
        "snapshot_id": str(snapshot_id),
        "raw_snapshot_id": str(raw_snapshot_id),
        "strategy_version": str(strategy_version),
        "signal_price_basis": str(signal_price_basis),
        "payload": payload if isinstance(payload, dict) else {},
        "status": str(status),
        "retry_count": int(retry_count),
        "last_error": str(last_error) if last_error is not None else None,
    }


def load_backtest_run(
    settings: AppSettings,
    *,
    backtest_id: str | None = None,
    snapshot_id: str | None = None,
) -> dict[str, object]:
    connection = _open_connection(settings)
    try:
        resolved_snapshot_id = (
            str(_fetch_published_snapshot_meta(connection, snapshot_id)["snapshot_id"])
            if snapshot_id is not None and backtest_id is None
            else snapshot_id
        )
        try:
            run = _fetch_backtest_run_meta(
                connection,
                backtest_id=backtest_id,
                snapshot_id=resolved_snapshot_id,
            )
        except LookupError:
            if backtest_id is None:
                raise

            request_meta = _fetch_backtest_request_meta(connection, backtest_id=backtest_id)
            if request_meta is None:
                raise

            return {
                "backtest_id": request_meta["backtest_id"],
                "strategy_name": "Queued Backtest Request",
                "strategy_version": request_meta["strategy_version"],
                "params": request_meta["payload"],
                "snapshot_id": request_meta["snapshot_id"],
                "raw_snapshot_id": request_meta["raw_snapshot_id"],
                "signal_price_basis": request_meta["signal_price_basis"],
                "execution_price_basis": "raw",
                "cost_model": {},
                "engine_version": request_meta["strategy_version"],
                "start_date": None,
                "end_date": None,
                "benchmark": "000300.SH",
                "metrics": {
                    "total_return_pct": None,
                    "annual_return_pct": None,
                    "max_drawdown_pct": None,
                    "win_rate_pct": None,
                    "profit_factor": None,
                },
                "status": request_meta["status"],
                "created_at": request_meta["requested_at"],
                "notes": ["Request queued and waiting for worker materialization."],
                "window": None,
                "request": {
                    "requested_at": request_meta["requested_at"],
                    "payload": request_meta["payload"],
                    "status": request_meta["status"],
                    "retry_count": request_meta["retry_count"],
                    "last_error": request_meta["last_error"],
                },
                "trades": [],
                "equity_curve": [],
            }

        request_row = connection.execute(
            """
            SELECT
              requested_at,
              payload_json,
              status,
              retry_count,
              last_error
            FROM backtest_request
            WHERE backtest_id = ?
            LIMIT 1
            """,
            [run["backtest_id"]],
        ).fetchone()
        trade_rows = connection.execute(
            """
            SELECT
              symbol,
              trade_date,
              side,
              price_basis,
              trade_price,
              quantity,
              notional,
              fee,
              tax,
              pnl,
              holding_days,
              reason,
              rank_no
            FROM backtest_trade
            WHERE backtest_id = ?
            ORDER BY
              trade_date ASC,
              CASE side WHEN 'BUY' THEN 0 ELSE 1 END ASC,
              rank_no ASC,
              symbol ASC
            """,
            [run["backtest_id"]],
        ).fetchall()
        equity_rows = connection.execute(
            """
            SELECT
              trade_date,
              position_count,
              cash,
              market_value,
              equity,
              drawdown,
              daily_return,
              benchmark_close,
              updated_at
            FROM backtest_equity_curve
            WHERE backtest_id = ?
            ORDER BY trade_date ASC
            """,
            [run["backtest_id"]],
        ).fetchall()

        request_payload = None
        if request_row is not None:
            requested_at, payload_json, status, retry_count, last_error = request_row
            request_payload = {
                "requested_at": _isoformat(requested_at),
                "payload": _decode_json_text(payload_json, {}),
                "status": str(status),
                "retry_count": int(retry_count),
                "last_error": str(last_error) if last_error is not None else None,
            }

        return {
            **run,
            "window": f"{run['start_date']} to {run['end_date']}",
            "request": request_payload,
            "trades": [
                {
                    "symbol": str(symbol),
                    "trade_date": _isoformat(trade_date),
                    "side": str(side),
                    "price_basis": str(price_basis),
                    "trade_price": float(trade_price),
                    "quantity": int(quantity),
                    "notional": float(notional),
                    "fee": float(fee),
                    "tax": float(tax) if tax is not None else None,
                    "pnl": float(pnl) if pnl is not None else None,
                    "holding_days": int(holding_days)
                    if holding_days is not None
                    else None,
                    "reason": str(reason),
                    "rank_no": int(rank_no),
                }
                for (
                    symbol,
                    trade_date,
                    side,
                    price_basis,
                    trade_price,
                    quantity,
                    notional,
                    fee,
                    tax,
                    pnl,
                    holding_days,
                    reason,
                    rank_no,
                ) in trade_rows
            ],
            "equity_curve": [
                {
                    "trade_date": _isoformat(trade_date),
                    "position_count": int(position_count),
                    "cash": float(cash),
                    "market_value": float(market_value),
                    "equity": float(equity),
                    "drawdown": float(drawdown) if drawdown is not None else None,
                    "daily_return": float(daily_return)
                    if daily_return is not None
                    else None,
                    "benchmark_close": float(benchmark_close)
                    if benchmark_close is not None
                    else None,
                    "updated_at": _isoformat(updated_at),
                }
                for (
                    trade_date,
                    position_count,
                    cash,
                    market_value,
                    equity,
                    drawdown,
                    daily_return,
                    benchmark_close,
                    updated_at,
                ) in equity_rows
            ],
        }
    finally:
        connection.close()


def load_task_runs(
    settings: AppSettings,
    *,
    snapshot_id: str | None = None,
) -> dict[str, object]:
    connection = _open_connection(settings)
    try:
        published_snapshot = _fetch_published_snapshot_meta(connection, snapshot_id)
        rows = connection.execute(
            """
            SELECT
              task_id,
              task_name,
              biz_date,
              snapshot_id,
              attempt_no,
              status,
              error_code,
              error_message,
              started_at,
              finished_at,
              detail_json
            FROM task_run_log
            WHERE snapshot_id = ?
            ORDER BY finished_at DESC, task_name ASC
            """,
            [published_snapshot["snapshot_id"]],
        ).fetchall()

        return {
            "snapshot_id": published_snapshot["snapshot_id"],
            "raw_snapshot_id": published_snapshot["raw_snapshot_id"],
            "items": [
                {
                    "task_id": str(task_id),
                    "task_name": str(task_name),
                    "biz_date": _isoformat(biz_date),
                    "snapshot_id": str(resolved_snapshot_id),
                    "attempt_no": int(attempt_no),
                    "status": str(status),
                    "error_code": str(error_code) if error_code is not None else None,
                    "error_message": str(error_message)
                    if error_message is not None
                    else None,
                    "started_at": _isoformat(started_at),
                    "finished_at": _isoformat(finished_at),
                    "detail": _decode_json_text(detail_json, {}),
                }
                for (
                    task_id,
                    task_name,
                    biz_date,
                    resolved_snapshot_id,
                    attempt_no,
                    status,
                    error_code,
                    error_message,
                    started_at,
                    finished_at,
                    detail_json,
                ) in rows
            ],
        }
    finally:
        connection.close()


def load_system_health(settings: AppSettings) -> dict[str, object]:
    connection = _open_connection(settings)
    try:
        latest_snapshot = _fetch_published_snapshot_meta(connection)
        raw_snapshot = _fetch_raw_snapshot_meta(
            connection,
            str(latest_snapshot["raw_snapshot_id"]),
        )
        alert_summary = summarize_recent_alerts(settings, limit=200)
        table_counts = {
            table_name: int(
                connection.execute(f"SELECT COUNT(*) FROM {table_name}").fetchone()[0]
            )
            for table_name in (
                "raw_snapshot",
                "artifact_publish",
                "daily_bar",
                "price_series_daily",
                "indicator_daily",
                "pattern_signal_daily",
                "capital_feature_daily",
                "fundamental_feature_daily",
                "official_disclosure_item",
                "corporate_action_item",
                "screener_run",
                "screener_result",
                "backtest_request",
                "backtest_run",
                "backtest_trade",
                "backtest_equity_curve",
                "task_run_log",
            )
        }
        task_count = int(
            connection.execute(
                """
                SELECT COUNT(*)
                FROM task_run_log
                WHERE snapshot_id = ?
                """,
                [latest_snapshot["snapshot_id"]],
            ).fetchone()[0]
        )
        return {
            "status": "ok",
            "snapshot_id": latest_snapshot["snapshot_id"],
            "raw_snapshot_id": latest_snapshot["raw_snapshot_id"],
            "published_at": latest_snapshot["published_at"],
            "duckdb_path": str(settings.duckdb_path),
            "alerts_path": str(settings.alerts_path),
            "table_counts": table_counts,
            "task_count": task_count,
            "alert_count": int(alert_summary["window_count"]),
            "alert_summary": alert_summary,
            "shadow_validation": raw_snapshot["source_watermark"].get(
                "shadow_validation",
                {
                    "status": "UNKNOWN",
                    "providers": [],
                },
            ),
        }
    finally:
        connection.close()
