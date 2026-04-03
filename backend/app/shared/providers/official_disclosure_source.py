from __future__ import annotations

from datetime import datetime, timedelta, timezone
import json
from pathlib import Path
from typing import Protocol
from urllib.parse import urlencode
from urllib.request import Request, urlopen

from backend.app.app_wiring.settings import AppSettings
from backend.app.shared.providers.local_fixture import load_json_fixture


CN_TZ = timezone(timedelta(hours=8))
CNINFO_QUERY_URL = "https://www.cninfo.com.cn/new/hisAnnouncement/query"
CNINFO_STOCK_LOOKUP_URL = "https://www.cninfo.com.cn/new/data/szse_stock.json"
CNINFO_PDF_BASE_URL = "https://static.cninfo.com.cn"
CNINFO_DETAIL_BASE_URL = "https://www.cninfo.com.cn/new/disclosure/detail"
CNINFO_SEARCH_REFERER = (
    "https://www.cninfo.com.cn/new/commonUrl/pageOfSearch?url=disclosure/list/search"
)


class OfficialDisclosureProvider(Protocol):
    def fetch_disclosures(
        self,
        *,
        biz_date: str,
        stock_basic: tuple[dict[str, object], ...],
    ) -> tuple[dict[str, object], ...]:
        ...


class NoneOfficialDisclosureProvider:
    def fetch_disclosures(
        self,
        *,
        biz_date: str,
        stock_basic: tuple[dict[str, object], ...],
    ) -> tuple[dict[str, object], ...]:
        return ()


class FixtureJsonOfficialDisclosureProvider:
    def __init__(self, settings: AppSettings) -> None:
        self._settings = settings

    def fetch_disclosures(
        self,
        *,
        biz_date: str,
        stock_basic: tuple[dict[str, object], ...],
    ) -> tuple[dict[str, object], ...]:
        fixture_path = self._settings.disclosure_fixture_dir / f"{biz_date}.json"
        if not fixture_path.exists():
            return ()

        payload = load_json_fixture(fixture_path)
        raw_items = payload if isinstance(payload, list) else payload.get("items", [])
        items: list[dict[str, object]] = []
        for raw_item in raw_items:
            item = dict(raw_item)
            item.setdefault("trade_date", biz_date)
            item.setdefault("source", "fixture_json.official_disclosure")
            item.setdefault("updated_at", f"{biz_date}T18:00:00+08:00")
            items.append(item)
        return tuple(items)


class CninfoOfficialDisclosureProvider:
    def __init__(self, settings: AppSettings) -> None:
        self._settings = settings
        self._stock_lookup_cache: dict[str, dict[str, str]] | None = None

    def fetch_disclosures(
        self,
        *,
        biz_date: str,
        stock_basic: tuple[dict[str, object], ...],
    ) -> tuple[dict[str, object], ...]:
        lookup = self._load_stock_lookup()
        rows: list[dict[str, object]] = []
        for stock in stock_basic:
            symbol = str(stock["symbol"])
            code = _symbol_to_code(symbol)
            stock_meta = lookup.get(code)
            if stock_meta is None:
                continue
            rows.extend(
                self._fetch_symbol_announcements(
                    symbol=symbol,
                    display_name=str(stock.get("display_name", stock_meta["display_name"])),
                    code=code,
                    org_id=stock_meta["org_id"],
                    biz_date=biz_date,
                )
            )

        rows.sort(
            key=lambda item: (
                str(item["trade_date"]),
                str(item.get("announcement_time") or ""),
                str(item["announcement_id"]),
            )
        )
        return tuple(rows)

    def _load_stock_lookup(self) -> dict[str, dict[str, str]]:
        if self._stock_lookup_cache is not None:
            return self._stock_lookup_cache

        payload = _get_json(CNINFO_STOCK_LOOKUP_URL)
        stock_list = payload.get("stockList", []) if isinstance(payload, dict) else []
        lookup: dict[str, dict[str, str]] = {}
        for item in stock_list:
            if not isinstance(item, dict):
                continue
            code = str(item.get("code", "")).strip()
            org_id = str(item.get("orgId", "")).strip()
            if not code or not org_id:
                continue
            lookup[code] = {
                "org_id": org_id,
                "display_name": str(item.get("zwjc", code)),
            }

        self._stock_lookup_cache = lookup
        return lookup

    def _fetch_symbol_announcements(
        self,
        *,
        symbol: str,
        display_name: str,
        code: str,
        org_id: str,
        biz_date: str,
    ) -> list[dict[str, object]]:
        rows: list[dict[str, object]] = []
        seen_announcement_ids: set[str] = set()
        page_num = 1
        page_size = 50
        total_record_num = 0

        while True:
            body = _post_form_json(
                CNINFO_QUERY_URL,
                {
                    "pageNum": str(page_num),
                    "pageSize": str(page_size),
                    "column": "szse",
                    "tabName": "fulltext",
                    "plate": "",
                    "stock": f"{code},{org_id}",
                    "searchkey": "",
                    "secid": "",
                    "category": "",
                    "trade": "",
                    "seDate": f"{biz_date}~{biz_date}",
                    "sortName": "time",
                    "sortType": "desc",
                    "isHLtitle": "false",
                },
                headers={
                    "Referer": CNINFO_SEARCH_REFERER,
                    "X-Requested-With": "XMLHttpRequest",
                },
            )
            announcements = body.get("announcements", []) if isinstance(body, dict) else []
            total_record_num = int(body.get("totalRecordNum") or 0) if isinstance(body, dict) else 0
            if not announcements:
                break

            fetched_at = datetime.now(CN_TZ).isoformat(timespec="seconds")
            for announcement in announcements:
                if not isinstance(announcement, dict):
                    continue
                announcement_id = str(announcement.get("announcementId", "")).strip()
                if not announcement_id or announcement_id in seen_announcement_ids:
                    continue
                seen_announcement_ids.add(announcement_id)
                rows.append(
                    _normalize_cninfo_announcement(
                        symbol=symbol,
                        display_name=display_name,
                        code=code,
                        org_id=org_id,
                        biz_date=biz_date,
                        fetched_at=fetched_at,
                        payload=announcement,
                    )
                )

            if page_num * page_size >= total_record_num:
                break
            page_num += 1

        return rows


def build_official_disclosure_provider(
    settings: AppSettings,
) -> OfficialDisclosureProvider:
    provider_name = settings.disclosure_provider
    if provider_name == "auto":
        provider_name = (
            "fixture_json"
            if settings.source_provider == "fixture_json"
            else "cninfo"
        )

    if provider_name == "none":
        return NoneOfficialDisclosureProvider()
    if provider_name == "fixture_json":
        return FixtureJsonOfficialDisclosureProvider(settings)
    if provider_name == "cninfo":
        return CninfoOfficialDisclosureProvider(settings)
    raise ValueError(f"Unsupported disclosure provider: {provider_name}")


def _normalize_cninfo_announcement(
    *,
    symbol: str,
    display_name: str,
    code: str,
    org_id: str,
    biz_date: str,
    fetched_at: str,
    payload: dict[str, object],
) -> dict[str, object]:
    announcement_time_ms = payload.get("announcementTime")
    announcement_time = _announcement_time_to_iso(announcement_time_ms)
    announcement_date = (
        announcement_time[:10]
        if announcement_time is not None
        else biz_date
    )
    announcement_id = str(payload.get("announcementId", "")).strip()
    adjunct_url = str(payload.get("adjunctUrl", "")).strip()

    return {
        "symbol": symbol,
        "display_name": display_name,
        "trade_date": announcement_date,
        "announcement_id": announcement_id,
        "org_id": org_id,
        "title": str(payload.get("announcementTitle", "")).strip(),
        "short_title": str(payload.get("shortTitle", "")).strip() or None,
        "announcement_time": announcement_time,
        "announcement_type": str(payload.get("announcementType", "")).strip() or None,
        "announcement_type_name": str(payload.get("announcementTypeName", "")).strip() or None,
        "page_column": str(payload.get("pageColumn", "")).strip() or None,
        "adjunct_type": str(payload.get("adjunctType", "")).strip() or None,
        "pdf_url": f"{CNINFO_PDF_BASE_URL}/{adjunct_url}" if adjunct_url else None,
        "detail_url": (
            f"{CNINFO_DETAIL_BASE_URL}?{urlencode({'stockCode': code, 'announcementId': announcement_id, 'orgId': org_id, 'announcementTime': announcement_date})}"
            if announcement_id
            else None
        ),
        "source": "cninfo.hisAnnouncement.query",
        "updated_at": fetched_at,
    }


def _symbol_to_code(symbol: str) -> str:
    return symbol.split(".", 1)[0]


def _announcement_time_to_iso(raw_value: object) -> str | None:
    if raw_value in (None, "", 0):
        return None
    timestamp_ms = int(raw_value)
    return datetime.fromtimestamp(timestamp_ms / 1000, tz=CN_TZ).isoformat(
        timespec="seconds"
    )


def _get_json(url: str) -> dict[str, object]:
    request = Request(
        url,
        headers={"User-Agent": "QuantA/0.1 (+official-disclosure-sync)"},
        method="GET",
    )
    with urlopen(request, timeout=30) as response:
        return json.loads(response.read().decode("utf-8"))


def _post_form_json(
    url: str,
    data: dict[str, str],
    *,
    headers: dict[str, str] | None = None,
) -> dict[str, object]:
    request_headers = {
        "User-Agent": "Mozilla/5.0 QuantA/0.1",
        "Content-Type": "application/x-www-form-urlencoded; charset=UTF-8",
        "Accept": "application/json, text/javascript, */*; q=0.01",
    }
    if headers:
        request_headers.update(headers)

    request = Request(
        url,
        data=urlencode(data).encode("utf-8"),
        headers=request_headers,
        method="POST",
    )
    with urlopen(request, timeout=30) as response:
        return json.loads(response.read().decode("utf-8"))
