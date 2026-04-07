from __future__ import annotations

from datetime import datetime, timedelta, timezone
import importlib
from typing import Any

from backend.app.app_wiring.settings import AppSettings
from backend.app.shared.providers.market_data_source import (
    MarketDataSnapshot,
)


CN_TZ = timezone(timedelta(hours=8))
PRICE_FIELDS = ("open_raw", "high_raw", "low_raw", "close_raw", "pre_close_raw")
SIZE_FIELDS = ("volume", "amount")


def build_shadow_validation_summary(
    settings: AppSettings,
    *,
    canonical_snapshot: MarketDataSnapshot,
) -> dict[str, object]:
    configured_providers = tuple(
        provider
        for provider in settings.source_validation_providers
        if provider and provider != "none"
    )
    if canonical_snapshot.provider == "fixture_json":
        return {
            "status": "SKIPPED",
            "canonical_provider": canonical_snapshot.provider,
            "canonical_symbol_count": len(canonical_snapshot.daily_bars),
            "providers": [],
            "message": "fixture_json canonical source skips supplementary validation",
        }
    if not configured_providers:
        return {
            "status": "SKIPPED",
            "canonical_provider": canonical_snapshot.provider,
            "canonical_symbol_count": len(canonical_snapshot.daily_bars),
            "providers": [],
            "message": "no supplementary validation providers configured",
        }

    provider_results = []
    for provider_name in configured_providers:
        if provider_name == canonical_snapshot.provider:
            continue
        if provider_name == "akshare":
            provider_results.append(
                _validate_with_akshare(settings, canonical_snapshot=canonical_snapshot)
            )
            continue
        if provider_name == "baostock":
            provider_results.append(
                _validate_with_baostock(settings, canonical_snapshot=canonical_snapshot)
            )
            continue
        provider_results.append(
            {
                "provider": provider_name,
                "status": "UNAVAILABLE",
                "message": f"unsupported supplementary validator: {provider_name}",
                "matched_symbol_count": 0,
                "mismatch_symbol_count": 0,
                "missing_symbol_count": 0,
                "covered_symbol_count": 0,
                "samples": [],
            }
        )

    statuses = {str(item["status"]) for item in provider_results}
    if not provider_results:
        status = "SKIPPED"
    elif "WARN" in statuses:
        status = "WARN"
    elif "OK" in statuses:
        status = "OK"
    elif statuses == {"UNAVAILABLE"}:
        status = "UNAVAILABLE"
    else:
        status = "SKIPPED"

    return {
        "status": status,
        "canonical_provider": canonical_snapshot.provider,
        "canonical_symbol_count": len(canonical_snapshot.daily_bars),
        "close_tolerance_bps": settings.source_validation_close_tolerance_bps,
        "field_tolerances_bps": _build_field_tolerances(settings),
        "providers": provider_results,
        "matched_provider_count": sum(
            1 for item in provider_results if item["status"] == "OK"
        ),
        "warning_provider_count": sum(
            1 for item in provider_results if item["status"] == "WARN"
        ),
        "unavailable_provider_count": sum(
            1 for item in provider_results if item["status"] == "UNAVAILABLE"
        ),
    }


def _validate_with_akshare(
    settings: AppSettings,
    *,
    canonical_snapshot: MarketDataSnapshot,
) -> dict[str, object]:
    try:
        ak = importlib.import_module("akshare")
    except Exception as exc:
        return _unavailable_validation_result(
            provider="akshare",
            message=str(exc).strip() or exc.__class__.__name__,
        )

    shadow_rows = []
    query_error_symbols: list[str] = []
    empty_symbols: list[str] = []
    first_error_message: str | None = None

    for item in canonical_snapshot.daily_bars:
        symbol = str(item["symbol"])
        try:
            frame = ak.stock_zh_a_hist(
                symbol=_to_akshare_hist_symbol(symbol),
                period="daily",
                start_date=canonical_snapshot.biz_date.replace("-", ""),
                end_date=canonical_snapshot.biz_date.replace("-", ""),
                adjust="",
            )
        except Exception as exc:
            query_error_symbols.append(symbol)
            if first_error_message is None:
                first_error_message = str(exc).strip() or exc.__class__.__name__
            continue

        if getattr(frame, "empty", False):
            empty_symbols.append(symbol)
            continue

        row = frame.iloc[-1]
        shadow_rows.append(
            {
                "symbol": symbol,
                "trade_date": str(row["日期"]),
                "open_raw": _float_or_none(row["开盘"]),
                "high_raw": _float_or_none(row["最高"]),
                "low_raw": _float_or_none(row["最低"]),
                "close_raw": _float_or_none(row["收盘"]),
                "pre_close_raw": _float_or_none(row["收盘"]) - _float_or_none(row["涨跌额"])
                if _float_or_none(row["收盘"]) is not None and _float_or_none(row["涨跌额"]) is not None
                else None,
                "volume": _float_or_none(row["成交量"]),
                "amount": _float_or_none(row["成交额"]),
            }
        )

    if not shadow_rows:
        return _unavailable_validation_result(
            provider="akshare",
            message=first_error_message or "akshare returned no validation rows",
        )

    shadow_snapshot = MarketDataSnapshot(
        provider="akshare",
        source="akshare.stock_zh_a_hist",
        biz_date=canonical_snapshot.biz_date,
        fetched_at=datetime.now(CN_TZ).isoformat(timespec="seconds"),
        price_basis="raw",
        stock_basic=canonical_snapshot.stock_basic,
        trade_calendar=canonical_snapshot.trade_calendar,
        daily_bars=tuple(shadow_rows),
        market_overview={},
        source_watermark={},
    )

    result = _compare_daily_bar_snapshots(
        provider="akshare",
        settings=settings,
        canonical_snapshot=canonical_snapshot,
        shadow_snapshot=shadow_snapshot,
    )
    return _attach_partial_coverage_notes(
        result,
        query_error_symbols=query_error_symbols,
        empty_symbols=empty_symbols,
    )


def _validate_with_baostock(
    settings: AppSettings,
    *,
    canonical_snapshot: MarketDataSnapshot,
) -> dict[str, object]:
    try:
        bs = importlib.import_module("baostock")
    except Exception as exc:
        return _unavailable_validation_result(
            provider="baostock",
            message=str(exc).strip() or exc.__class__.__name__,
        )

    login_result = bs.login()
    if str(getattr(login_result, "error_code", "0")) != "0":
        return _unavailable_validation_result(
            provider="baostock",
            message=f"login_failed:{getattr(login_result, 'error_msg', '')}",
        )

    try:
        shadow_rows = []
        query_error_symbols: list[str] = []
        for item in canonical_snapshot.daily_bars:
            symbol = str(item["symbol"])
            query = bs.query_history_k_data_plus(
                _to_baostock_code(symbol),
                "date,code,open,high,low,close,preclose,volume,amount",
                start_date=canonical_snapshot.biz_date,
                end_date=canonical_snapshot.biz_date,
                frequency="d",
                adjustflag="3",
            )
            if str(getattr(query, "error_code", "0")) != "0":
                query_error_symbols.append(symbol)
                continue

            while query.next():
                date_value, _code, open_raw, high_raw, low_raw, close_raw, pre_close_raw, volume, amount = query.get_row_data()
                shadow_rows.append(
                    {
                        "symbol": symbol,
                        "trade_date": str(date_value),
                        "open_raw": _float_or_none(open_raw),
                        "high_raw": _float_or_none(high_raw),
                        "low_raw": _float_or_none(low_raw),
                        "close_raw": _float_or_none(close_raw),
                        "pre_close_raw": _float_or_none(pre_close_raw),
                        "volume": _float_or_none(volume),
                        "amount": _float_or_none(amount),
                    }
                )
        shadow_snapshot = MarketDataSnapshot(
            provider="baostock",
            source="baostock.query_history_k_data_plus",
            biz_date=canonical_snapshot.biz_date,
            fetched_at=datetime.now(CN_TZ).isoformat(timespec="seconds"),
            price_basis="raw",
            stock_basic=canonical_snapshot.stock_basic,
            trade_calendar=canonical_snapshot.trade_calendar,
            daily_bars=tuple(shadow_rows),
            market_overview={},
            source_watermark={},
        )
    except Exception as exc:
        return _unavailable_validation_result(
            provider="baostock",
            message=str(exc).strip() or exc.__class__.__name__,
        )
    finally:
        try:
            bs.logout()
        except Exception:
            pass

    if not shadow_rows:
        return _unavailable_validation_result(
            provider="baostock",
            message="baostock returned no validation rows",
        )

    result = _compare_daily_bar_snapshots(
        provider="baostock",
        settings=settings,
        canonical_snapshot=canonical_snapshot,
        shadow_snapshot=shadow_snapshot,
    )
    return _attach_partial_coverage_notes(
        result,
        query_error_symbols=query_error_symbols,
        empty_symbols=[],
    )


def _compare_daily_bar_snapshots(
    *,
    provider: str,
    settings: AppSettings,
    canonical_snapshot: MarketDataSnapshot,
    shadow_snapshot: MarketDataSnapshot,
) -> dict[str, object]:
    field_tolerances = _build_field_tolerances(settings)
    canonical_by_symbol = {
        str(item["symbol"]): dict(item)
        for item in canonical_snapshot.daily_bars
    }
    shadow_by_symbol = {
        str(item["symbol"]): dict(item)
        for item in shadow_snapshot.daily_bars
    }

    matched_symbols = []
    mismatch_symbols = []
    missing_symbols = []
    samples = []
    field_summary = {
        field_name: {
            "tolerance_bps": tolerance_bps,
            "matched_symbol_count": 0,
            "mismatch_symbol_count": 0,
            "missing_symbol_count": 0,
        }
        for field_name, tolerance_bps in field_tolerances.items()
    }

    for symbol, canonical_row in canonical_by_symbol.items():
        shadow_row = shadow_by_symbol.get(symbol)
        if shadow_row is None:
            missing_symbols.append(symbol)
            for summary in field_summary.values():
                summary["missing_symbol_count"] += 1
            continue

        field_results = {}
        mismatch_fields = []
        for field_name, tolerance_bps in field_tolerances.items():
            result = _compare_numeric_field(
                canonical_value=_float_or_none(canonical_row.get(field_name)),
                shadow_value=_float_or_none(shadow_row.get(field_name)),
                tolerance_bps=tolerance_bps,
            )
            field_results[field_name] = result
            field_summary[field_name][result["summary_key"]] += 1
            if result["status"] != "MATCH":
                mismatch_fields.append(field_name)

        if mismatch_fields:
            mismatch_symbols.append(symbol)
            if len(samples) < 5:
                samples.append(
                    {
                        "symbol": symbol,
                        "mismatch_fields": mismatch_fields,
                        "field_results": {
                            field_name: {
                                "status": field_results[field_name]["status"],
                                "canonical": field_results[field_name]["canonical"],
                                "shadow": field_results[field_name]["shadow"],
                                "diff_bps": field_results[field_name]["diff_bps"],
                            }
                            for field_name in mismatch_fields
                        },
                    }
                )
            continue

        matched_symbols.append(symbol)
        if len(samples) < 3:
            samples.append(
                {
                    "symbol": symbol,
                    "mismatch_fields": [],
                    "field_results": {
                        field_name: {
                            "status": field_results[field_name]["status"],
                            "canonical": field_results[field_name]["canonical"],
                            "shadow": field_results[field_name]["shadow"],
                            "diff_bps": field_results[field_name]["diff_bps"],
                        }
                        for field_name in ("close_raw", "volume", "amount")
                    },
                }
            )

    status = "OK" if not mismatch_symbols and not missing_symbols else "WARN"
    message = (
        f"{provider} fully matched {len(matched_symbols)}/{len(canonical_by_symbol)} symbols"
    )
    if missing_symbols:
        message += f"; missing {len(missing_symbols)}"
    if mismatch_symbols:
        message += f"; mismatched {len(mismatch_symbols)}"

    return {
        "provider": provider,
        "status": status,
        "message": message,
        "matched_symbol_count": len(matched_symbols),
        "mismatch_symbol_count": len(mismatch_symbols),
        "missing_symbol_count": len(missing_symbols),
        "covered_symbol_count": len(shadow_by_symbol),
        "matched_symbols": matched_symbols[:10],
        "mismatch_symbols": mismatch_symbols[:10],
        "missing_symbols": missing_symbols[:10],
        "field_summary": field_summary,
        "samples": samples,
    }


def _unavailable_validation_result(*, provider: str, message: str) -> dict[str, object]:
    return {
        "provider": provider,
        "status": "UNAVAILABLE",
        "message": message,
        "matched_symbol_count": 0,
        "mismatch_symbol_count": 0,
        "missing_symbol_count": 0,
        "covered_symbol_count": 0,
        "matched_symbols": [],
        "mismatch_symbols": [],
        "missing_symbols": [],
        "samples": [],
    }


def _attach_partial_coverage_notes(
    result: dict[str, object],
    *,
    query_error_symbols: list[str],
    empty_symbols: list[str],
) -> dict[str, object]:
    if not query_error_symbols and not empty_symbols:
        return result

    detail_parts = []
    if query_error_symbols:
        result["query_error_symbols"] = query_error_symbols[:10]
        detail_parts.append(f"query_errors {len(query_error_symbols)}")
    if empty_symbols:
        result["empty_symbols"] = empty_symbols[:10]
        detail_parts.append(f"empty_rows {len(empty_symbols)}")

    result["status"] = "WARN"
    result["message"] = f"{result['message']}; " + ", ".join(detail_parts)
    return result


def _diff_bps(left: float | None, right: float | None) -> float | None:
    if left in (None, 0.0) or right is None:
        return None
    return abs(right - left) / abs(left) * 10000.0


def _compare_numeric_field(
    *,
    canonical_value: float | None,
    shadow_value: float | None,
    tolerance_bps: int,
) -> dict[str, object]:
    diff_bps = _diff_bps(canonical_value, shadow_value)
    if canonical_value is None or shadow_value is None:
        status = "MISSING"
        summary_key = "missing_symbol_count"
    elif canonical_value == 0.0 and shadow_value == 0.0:
        status = "MATCH"
        summary_key = "matched_symbol_count"
        diff_bps = 0.0
    elif diff_bps is not None and diff_bps <= tolerance_bps:
        status = "MATCH"
        summary_key = "matched_symbol_count"
    else:
        status = "MISMATCH"
        summary_key = "mismatch_symbol_count"

    return {
        "status": status,
        "summary_key": summary_key,
        "canonical": canonical_value,
        "shadow": shadow_value,
        "diff_bps": round(diff_bps, 2) if diff_bps is not None else None,
    }


def _build_field_tolerances(settings: AppSettings) -> dict[str, int]:
    return {
        **{
            field_name: settings.source_validation_close_tolerance_bps
            for field_name in PRICE_FIELDS
        },
        "volume": settings.source_validation_volume_tolerance_bps,
        "amount": settings.source_validation_amount_tolerance_bps,
    }


def _to_baostock_code(symbol: str) -> str:
    code, exchange = symbol.split(".")
    exchange_prefix = "sh" if exchange.upper() == "SH" else "sz"
    return f"{exchange_prefix}.{code}"


def _to_akshare_hist_symbol(symbol: str) -> str:
    code, _exchange = symbol.split(".")
    return code


def _float_or_none(raw_value: Any) -> float | None:
    if raw_value in (None, ""):
        return None
    return float(raw_value)
