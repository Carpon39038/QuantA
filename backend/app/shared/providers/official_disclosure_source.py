from __future__ import annotations

from datetime import datetime, timedelta, timezone
import hashlib
import json
from pathlib import Path
import re
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
            classification = _classify_disclosure(
                title=str(item.get("title", "")),
                announcement_type_name=str(item.get("announcement_type_name", "")),
            )
            event_type = str(item.get("disclosure_event_type") or classification["event_type"])
            item["disclosure_event_type"] = event_type
            if not item.get("disclosure_event_id"):
                item["disclosure_event_id"] = _derive_disclosure_event_id(
                    symbol=str(item.get("symbol", "")),
                    trade_date=str(item.get("trade_date", biz_date)),
                    title=str(item.get("title", "")),
                    event_type=event_type,
                )
            if not item.get("classification_explanation"):
                item["classification_explanation"] = classification["classification_explanation"]
            if not item.get("body_summary"):
                item["body_summary"] = _build_body_summary(item)
            if not item.get("inquiry_status"):
                item["inquiry_status"] = classification["inquiry_status"]
            if not item.get("reply_status"):
                item["reply_status"] = classification["reply_status"]
            if "related_announcement_id" not in item:
                item["related_announcement_id"] = None
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
    title = str(payload.get("announcementTitle", "")).strip()
    announcement_type_name = str(payload.get("announcementTypeName", "")).strip() or None
    classification = _classify_disclosure(
        title=title,
        announcement_type_name=announcement_type_name or "",
    )
    body_summary = _build_body_summary(
        {
            "display_name": display_name,
            "title": title,
            "announcement_type_name": announcement_type_name,
            "classification_explanation": classification["classification_explanation"],
            "announcement_content": payload.get("announcementContent"),
        }
    )

    return {
        "symbol": symbol,
        "display_name": display_name,
        "trade_date": announcement_date,
        "announcement_id": announcement_id,
        "disclosure_event_id": _derive_disclosure_event_id(
            symbol=symbol,
            trade_date=announcement_date,
            title=title,
            event_type=classification["event_type"],
        ),
        "disclosure_event_type": classification["event_type"],
        "org_id": org_id,
        "title": title,
        "short_title": str(payload.get("shortTitle", "")).strip() or None,
        "announcement_time": announcement_time,
        "announcement_type": str(payload.get("announcementType", "")).strip() or None,
        "announcement_type_name": announcement_type_name,
        "classification_explanation": classification["classification_explanation"],
        "body_summary": body_summary,
        "inquiry_status": classification["inquiry_status"],
        "reply_status": classification["reply_status"],
        "related_announcement_id": None,
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


def _classify_disclosure(
    *,
    title: str,
    announcement_type_name: str,
) -> dict[str, str | None]:
    haystack = f"{title} {announcement_type_name}"
    if any(keyword in haystack for keyword in ("问询函回复", "回复问询函", "问询函的回复")):
        return {
            "event_type": "INQUIRY_REPLY",
            "classification_explanation": "问询回复类披露，用于确认公司是否已对监管问题给出正式说明。",
            "inquiry_status": "REPLIED",
            "reply_status": "REPLY_DISCLOSED",
        }
    if any(keyword in haystack for keyword in ("问询函", "关注函", "监管函")):
        return {
            "event_type": "INQUIRY",
            "classification_explanation": "交易所问询类披露，代表监管侧要求公司进一步解释事项，盘后计划应跟踪回复状态。",
            "inquiry_status": "OPEN",
            "reply_status": "AWAITING_REPLY",
        }
    if "回购" in haystack:
        return {
            "event_type": "BUYBACK",
            "classification_explanation": "股份回购类公告，通常影响资本结构、股东回报预期和短期情绪验证。",
            "inquiry_status": None,
            "reply_status": None,
        }
    if any(keyword in haystack for keyword in ("董事会", "监事会", "公司治理", "工商变更")):
        return {
            "event_type": "GOVERNANCE",
            "classification_explanation": "公司治理类公告，通常用于解释主体资质、章程或治理结构变化。",
            "inquiry_status": None,
            "reply_status": None,
        }
    if any(keyword in haystack for keyword in ("业绩说明会", "投资者关系", "调研")):
        return {
            "event_type": "INVESTOR_RELATIONS",
            "classification_explanation": "投资者关系类公告，主要用于跟踪业绩说明会、调研和沟通安排。",
            "inquiry_status": None,
            "reply_status": None,
        }
    return {
        "event_type": "DISCLOSURE",
        "classification_explanation": "一般官方披露事件，盘后研究可作为公司事实更新来源。",
        "inquiry_status": None,
        "reply_status": None,
    }


def _derive_disclosure_event_id(
    *,
    symbol: str,
    trade_date: str,
    title: str,
    event_type: str,
) -> str:
    normalized_title = re.sub(r"\s+", "", title).lower()
    fingerprint = "|".join([symbol, trade_date, event_type, normalized_title])
    digest = hashlib.sha1(fingerprint.encode("utf-8")).hexdigest()[:16]
    return f"od_evt_{digest}"


def _build_body_summary(item: dict[str, object]) -> str | None:
    existing = item.get("body_summary")
    if isinstance(existing, str) and existing.strip():
        return existing.strip()

    raw_body = item.get("announcement_content") or item.get("body")
    if isinstance(raw_body, str) and raw_body.strip():
        return _truncate_summary(_clean_text(raw_body), limit=180)

    title = str(item.get("title", "")).strip()
    if not title:
        return None
    display_name = str(item.get("display_name", "")).strip()
    prefix = f"{display_name}披露" if display_name else "公司披露"
    return _truncate_summary(f"{prefix}《{title}》。", limit=180)


def _clean_text(value: str) -> str:
    return re.sub(r"\s+", " ", value).strip()


def _truncate_summary(value: str, *, limit: int) -> str:
    if len(value) <= limit:
        return value
    return value[: limit - 1].rstrip() + "…"


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
