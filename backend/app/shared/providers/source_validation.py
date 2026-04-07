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
    canonical_checks = _build_canonical_quality_checks(
        settings,
        canonical_snapshot=canonical_snapshot,
    )
    canonical_check_status = _merge_check_status(
        check["status"] for check in canonical_checks.values()
    )
    configured_providers = tuple(
        provider
        for provider in settings.source_validation_providers
        if provider and provider != "none"
    )
    if canonical_snapshot.provider == "fixture_json":
        return {
            "status": "SKIPPED" if canonical_check_status == "SKIPPED" else canonical_check_status,
            "canonical_provider": canonical_snapshot.provider,
            "canonical_symbol_count": len(canonical_snapshot.daily_bars),
            "canonical_check_status": canonical_check_status,
            "canonical_checks": canonical_checks,
            "providers": [],
            "message": "fixture_json canonical source skips supplementary validation",
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
                "degradation_category": "unsupported",
                "samples": [],
            }
        )

    statuses = {str(item["status"]) for item in provider_results}
    degraded_providers = [
        {
            "provider": str(item["provider"]),
            "status": str(item["status"]),
            "degradation_category": str(item.get("degradation_category", "unknown")),
            "message": str(item["message"]),
        }
        for item in provider_results
        if item["status"] in {"WARN", "UNAVAILABLE"}
    ]
    if canonical_check_status == "WARN":
        status = "WARN"
    elif not provider_results:
        status = canonical_check_status
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
        "field_tolerances_bps": _build_field_tolerances(
            settings,
            include_adj_factor=True,
        ),
        "canonical_check_status": canonical_check_status,
        "canonical_checks": canonical_checks,
        "degradation_status": "DEGRADED" if degraded_providers else "HEALTHY",
        "degraded_provider_count": len(degraded_providers),
        "degraded_providers": degraded_providers,
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
                adj_factor = _load_baostock_adjust_factor_for_date(
                    bs,
                    symbol=symbol,
                    biz_date=canonical_snapshot.biz_date,
                )
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
                        "adj_factor": adj_factor,
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
        include_adj_factor=True,
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
    include_adj_factor: bool = False,
) -> dict[str, object]:
    field_tolerances = _build_field_tolerances(
        settings,
        include_adj_factor=include_adj_factor,
    )
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
            sample_fields = ("close_raw", "volume", "amount")
            if "adj_factor" in field_results:
                sample_fields = (*sample_fields, "adj_factor")
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
                        for field_name in sample_fields
                    },
                }
            )

    status = "OK" if not mismatch_symbols and not missing_symbols else "WARN"
    degradation_category = "field_mismatch" if mismatch_symbols or missing_symbols else None
    message = (
        f"{provider} fully matched {len(matched_symbols)}/{len(canonical_by_symbol)} symbols"
    )
    if missing_symbols:
        message += f"; missing {len(missing_symbols)}"
    if mismatch_symbols:
        message += f"; mismatched {len(mismatch_symbols)}"

    if _is_adj_factor_only_degradation(field_summary):
        adj_factor_summary = field_summary["adj_factor"]
        raw_fields = PRICE_FIELDS + SIZE_FIELDS
        raw_match_count = min(
            field_summary[field_name]["matched_symbol_count"]
            for field_name in raw_fields
            if field_name in field_summary
        )
        message = (
            f"{provider} matched raw bars {raw_match_count}/{len(canonical_by_symbol)} symbols; "
            f"adj_factor mismatched {adj_factor_summary['mismatch_symbol_count']}"
        )
        degradation_category = "adj_factor_semantics_mismatch"

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
        "validated_fields": list(field_tolerances),
        "degradation_category": degradation_category,
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
        "degradation_category": _categorize_validation_degradation(
            provider=provider,
            message=message,
        ),
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
    result["degradation_category"] = "partial_coverage"
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


def _build_field_tolerances(
    settings: AppSettings,
    *,
    include_adj_factor: bool = False,
) -> dict[str, int]:
    field_tolerances = {
        **{
            field_name: settings.source_validation_close_tolerance_bps
            for field_name in PRICE_FIELDS
        },
        "volume": settings.source_validation_volume_tolerance_bps,
        "amount": settings.source_validation_amount_tolerance_bps,
    }
    if include_adj_factor:
        field_tolerances["adj_factor"] = settings.source_validation_close_tolerance_bps
    return field_tolerances


def _is_adj_factor_only_degradation(
    field_summary: dict[str, dict[str, int]],
) -> bool:
    if "adj_factor" not in field_summary:
        return False

    adj_factor_summary = field_summary["adj_factor"]
    if adj_factor_summary["mismatch_symbol_count"] <= 0:
        return False
    if adj_factor_summary["missing_symbol_count"] > 0:
        return False

    for field_name, summary in field_summary.items():
        if field_name == "adj_factor":
            continue
        if summary["mismatch_symbol_count"] > 0 or summary["missing_symbol_count"] > 0:
            return False
    return True


def _build_canonical_quality_checks(
    settings: AppSettings,
    *,
    canonical_snapshot: MarketDataSnapshot,
) -> dict[str, dict[str, object]]:
    if canonical_snapshot.provider == "fixture_json":
        return {
            "adj_factor": _skipped_canonical_check("fixture_json skips canonical quality checks"),
            "limit_price": _skipped_canonical_check("fixture_json skips canonical quality checks"),
            "suspension": _skipped_canonical_check("fixture_json skips canonical quality checks"),
        }

    return {
        "adj_factor": _validate_canonical_adj_factor(canonical_snapshot=canonical_snapshot),
        "limit_price": _validate_canonical_limit_price(
            settings,
            canonical_snapshot=canonical_snapshot,
        ),
        "suspension": _validate_canonical_suspension(canonical_snapshot=canonical_snapshot),
    }


def _validate_canonical_adj_factor(
    *,
    canonical_snapshot: MarketDataSnapshot,
) -> dict[str, object]:
    tracked_symbols = {str(item["symbol"]) for item in canonical_snapshot.stock_basic}
    adj_factor_by_symbol = {
        str(item["symbol"]): _float_or_none(item.get("adj_factor"))
        for item in canonical_snapshot.adj_factor_overrides
        if item.get("symbol") is not None
    }
    missing_symbols = sorted(tracked_symbols.difference(adj_factor_by_symbol))
    invalid_symbols = sorted(
        symbol
        for symbol, adj_factor in adj_factor_by_symbol.items()
        if adj_factor in (None, 0.0) or (adj_factor is not None and adj_factor < 0.0)
    )
    status = "OK" if not missing_symbols and not invalid_symbols else "WARN"
    message = (
        f"adj_factor available for {len(adj_factor_by_symbol)}/{len(tracked_symbols)} symbols"
    )
    if missing_symbols:
        message += f"; missing {len(missing_symbols)}"
    if invalid_symbols:
        message += f"; invalid {len(invalid_symbols)}"
    return {
        "status": status,
        "message": message,
        "tracked_symbol_count": len(tracked_symbols),
        "available_symbol_count": len(adj_factor_by_symbol),
        "missing_symbol_count": len(missing_symbols),
        "invalid_symbol_count": len(invalid_symbols),
        "missing_symbols": missing_symbols[:10],
        "invalid_symbols": invalid_symbols[:10],
    }


def _validate_canonical_limit_price(
    settings: AppSettings,
    *,
    canonical_snapshot: MarketDataSnapshot,
) -> dict[str, object]:
    board_by_symbol = {
        str(item["symbol"]): str(item.get("board") or "")
        for item in canonical_snapshot.stock_basic
    }
    checked_symbol_count = 0
    matched_symbol_count = 0
    missing_symbol_count = 0
    mismatch_symbol_count = 0
    samples = []

    for row in canonical_snapshot.daily_bars:
        symbol = str(row["symbol"])
        if row.get("pre_close_raw") is None:
            continue
        expected_rule_code = _expected_limit_rule_code(
            symbol=symbol,
            board=board_by_symbol.get(symbol, ""),
        )
        if expected_rule_code is None:
            continue

        checked_symbol_count += 1
        expected_high, expected_low = _expected_limit_prices(
            pre_close=_float_or_none(row.get("pre_close_raw")),
            rule_code=expected_rule_code,
        )
        actual_high = _float_or_none(row.get("high_limit"))
        actual_low = _float_or_none(row.get("low_limit"))
        actual_rule_code = str(row.get("limit_rule_code") or "")
        high_diff_bps = _diff_bps(expected_high, actual_high)
        low_diff_bps = _diff_bps(expected_low, actual_low)

        if actual_high is None or actual_low is None:
            missing_symbol_count += 1
            if len(samples) < 5:
                samples.append(
                    {
                        "symbol": symbol,
                        "reason": "missing_limit_price",
                        "expected_rule_code": expected_rule_code,
                    }
                )
            continue

        if (
            actual_rule_code != expected_rule_code
            or high_diff_bps is None
            or low_diff_bps is None
            or high_diff_bps > settings.source_validation_close_tolerance_bps
            or low_diff_bps > settings.source_validation_close_tolerance_bps
        ):
            mismatch_symbol_count += 1
            if len(samples) < 5:
                samples.append(
                    {
                        "symbol": symbol,
                        "expected_rule_code": expected_rule_code,
                        "actual_rule_code": actual_rule_code,
                        "expected_high_limit": expected_high,
                        "actual_high_limit": actual_high,
                        "expected_low_limit": expected_low,
                        "actual_low_limit": actual_low,
                        "high_diff_bps": round(high_diff_bps, 2) if high_diff_bps is not None else None,
                        "low_diff_bps": round(low_diff_bps, 2) if low_diff_bps is not None else None,
                    }
                )
            continue

        matched_symbol_count += 1

    status = "OK" if not missing_symbol_count and not mismatch_symbol_count else "WARN"
    message = f"limit price validated on {matched_symbol_count}/{checked_symbol_count} symbols"
    if missing_symbol_count:
        message += f"; missing {missing_symbol_count}"
    if mismatch_symbol_count:
        message += f"; mismatched {mismatch_symbol_count}"
    return {
        "status": status,
        "message": message,
        "checked_symbol_count": checked_symbol_count,
        "matched_symbol_count": matched_symbol_count,
        "missing_symbol_count": missing_symbol_count,
        "mismatch_symbol_count": mismatch_symbol_count,
        "samples": samples,
    }


def _validate_canonical_suspension(
    *,
    canonical_snapshot: MarketDataSnapshot,
) -> dict[str, object]:
    reported_suspended_symbols = {
        str(item)
        for item in canonical_snapshot.source_watermark.get("suspended_symbols", [])
    }
    flagged_suspended_symbols = {
        str(row["symbol"])
        for row in canonical_snapshot.daily_bars
        if bool(row.get("is_suspended"))
    }
    missing_flag_symbols = sorted(reported_suspended_symbols.difference(flagged_suspended_symbols))
    unexpected_flag_symbols = sorted(flagged_suspended_symbols.difference(reported_suspended_symbols))
    nonzero_volume_symbols = sorted(
        symbol
        for symbol in flagged_suspended_symbols
        for row in canonical_snapshot.daily_bars
        if str(row["symbol"]) == symbol and (_float_or_none(row.get("volume")) or 0.0) > 0.0
    )
    status = (
        "OK"
        if not missing_flag_symbols and not unexpected_flag_symbols and not nonzero_volume_symbols
        else "WARN"
    )
    message = f"reported suspended symbols: {len(reported_suspended_symbols)}"
    if missing_flag_symbols:
        message += f"; missing flags {len(missing_flag_symbols)}"
    if unexpected_flag_symbols:
        message += f"; unexpected flags {len(unexpected_flag_symbols)}"
    if nonzero_volume_symbols:
        message += f"; nonzero volume {len(nonzero_volume_symbols)}"
    return {
        "status": status,
        "message": message,
        "reported_suspended_symbol_count": len(reported_suspended_symbols),
        "flagged_suspended_symbol_count": len(flagged_suspended_symbols),
        "missing_flag_symbol_count": len(missing_flag_symbols),
        "unexpected_flag_symbol_count": len(unexpected_flag_symbols),
        "nonzero_volume_symbol_count": len(nonzero_volume_symbols),
        "missing_flag_symbols": missing_flag_symbols[:10],
        "unexpected_flag_symbols": unexpected_flag_symbols[:10],
        "nonzero_volume_symbols": nonzero_volume_symbols[:10],
    }


def _skipped_canonical_check(message: str) -> dict[str, object]:
    return {
        "status": "SKIPPED",
        "message": message,
    }


def _merge_check_status(statuses) -> str:
    normalized = {str(status) for status in statuses if str(status) != "SKIPPED"}
    if not normalized:
        return "SKIPPED"
    if "WARN" in normalized:
        return "WARN"
    return "OK"


def _expected_limit_rule_code(*, symbol: str, board: str) -> str | None:
    normalized_board = board.strip()
    if normalized_board in {"主板", "A股", ""}:
        return "10pct"
    if normalized_board in {"创业板", "科创板"}:
        return "20pct"
    if normalized_board == "北交所":
        return "30pct"
    if symbol.startswith(("300", "301", "688")):
        return "20pct"
    return "10pct"


def _expected_limit_prices(
    *,
    pre_close: float | None,
    rule_code: str,
) -> tuple[float | None, float | None]:
    if pre_close is None:
        return None, None
    if rule_code == "20pct":
        ratio = 0.20
    elif rule_code == "30pct":
        ratio = 0.30
    else:
        ratio = 0.10
    return round(pre_close * (1.0 + ratio), 2), round(pre_close * (1.0 - ratio), 2)


def _categorize_validation_degradation(*, provider: str, message: str) -> str:
    normalized = message.lower()
    if "unsupported supplementary validator" in normalized:
        return "unsupported"
    if "proxy" in normalized or "remote end closed" in normalized:
        return f"{provider}_upstream_connectivity"
    if "eastmoney" in normalized or "push2his" in normalized:
        return f"{provider}_upstream_connectivity"
    if "login_failed" in normalized:
        return f"{provider}_login_failed"
    return f"{provider}_request_failed"


def _load_baostock_adjust_factor_for_date(
    baostock_module: Any,
    *,
    symbol: str,
    biz_date: str,
) -> float | None:
    query = baostock_module.query_adjust_factor(
        code=_to_baostock_code(symbol),
        start_date="2000-01-01",
        end_date=biz_date,
    )
    if str(getattr(query, "error_code", "0")) != "0":
        return None

    rows = []
    while query.next():
        rows.append(query.get_row_data())
    if not rows:
        return None
    latest_row = rows[-1]
    if len(latest_row) < 5:
        return None
    return _float_or_none(latest_row[4])


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
