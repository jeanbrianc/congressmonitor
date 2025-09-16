from __future__ import annotations

import logging
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from typing import List, Optional, Sequence, Tuple

from .http import HTTPError, SimpleHttpClient

logger = logging.getLogger(__name__)

HOUSE_DATA_URL = "https://house-stock-watcher-data.s3-us-west-2.amazonaws.com/data/all_transactions.json"
SENATE_DATA_URL_TEMPLATE = "https://senate-stock-watcher-data.s3-us-west-2.amazonaws.com/transaction_report_for_{year}.json"
DEFAULT_MEMBERS: Tuple[str, ...] = (
    "Nancy Pelosi",
    "David Rouzer",
    "Debbie Wasserman Schultz",
    "Ron Wyden",
)


@dataclass(frozen=True)
class TradeRecord:
    """Normalized representation of a single congressional stock trade."""

    chamber: str
    legislator: str
    reported: datetime
    transaction_date: Optional[datetime]
    ticker: Optional[str]
    asset_description: Optional[str]
    transaction_type: Optional[str]
    amount: Optional[str]
    owner: Optional[str]
    link: Optional[str]
    source: str

    def to_dict(self) -> dict:
        """Return a CSV-friendly dictionary representation."""

        def _format(dt: Optional[datetime]) -> str:
            if not dt:
                return ""
            return dt.date().isoformat()

        return {
            "chamber": self.chamber,
            "legislator": self.legislator,
            "reported_date": _format(self.reported),
            "transaction_date": _format(self.transaction_date),
            "ticker": self.ticker or "",
            "asset_description": self.asset_description or "",
            "transaction_type": self.transaction_type or "",
            "amount": self.amount or "",
            "owner": self.owner or "",
            "link": self.link or "",
            "source": self.source,
        }


def fetch_trades(
    *,
    members: Optional[Sequence[str]] = None,
    since: Optional[datetime] = None,
    until: Optional[datetime] = None,
    lookback: timedelta = timedelta(hours=24),
    session: Optional[SimpleHttpClient] = None,
    include_house: bool = True,
    include_senate: bool = True,
) -> List[TradeRecord]:
    """Fetch trades from available public data sources.

    Args:
        members: Optional iterable of member names to filter on. Names are
            matched case-insensitively. If omitted or ``None`` all trades are
            returned.
        since: Optional inclusive lower bound timestamp. If omitted the bound
            defaults to ``now - lookback``.
        until: Optional exclusive upper bound timestamp. Defaults to ``now``.
        lookback: Time delta used when ``since`` is omitted. Defaults to
            24 hours.
        session: Optional HTTP client with a ``get`` method. A default
            :class:`~congressmonitor.http.SimpleHttpClient` is created when
            omitted.
        include_house: Whether to include U.S. House of Representatives trades.
        include_senate: Whether to include U.S. Senate trades.

    Returns:
        List of ``TradeRecord`` instances sorted by reported date (descending).
    """

    if not include_house and not include_senate:
        return []

    http = session or SimpleHttpClient()
    end = until or _now()
    start = since or (end - lookback)

    normalized_members = _normalize_members(members)

    records: List[TradeRecord] = []
    if include_house:
        records.extend(_load_house_records(http=http, start=start, end=end))
    if include_senate:
        records.extend(_load_senate_records(http=http, start=start, end=end))

    if normalized_members is not None:
        records = [
            record
            for record in records
            if _normalize_name(record.legislator) in normalized_members
        ]

    records.sort(key=lambda record: (record.reported, record.transaction_date or record.reported), reverse=True)
    return records


def _normalize_members(members: Optional[Sequence[str]]) -> Optional[set[str]]:
    if members is None:
        return None
    normalized = {_normalize_name(name) for name in members if name}
    if not normalized:
        return None
    if {"all"} & normalized:
        return None
    return normalized


def _normalize_name(name: str) -> str:
    return " ".join(name.strip().lower().split())


def _now() -> datetime:
    return datetime.now(tz=timezone.utc)


DATE_FORMATS = (
    "%Y-%m-%d",
    "%m/%d/%Y",
    "%Y/%m/%d",
    "%Y-%m-%dT%H:%M:%S",
    "%Y-%m-%dT%H:%M:%S.%f",
    "%Y-%m-%dT%H:%M:%SZ",
    "%Y-%m-%d %H:%M:%S",
)


def _parse_datetime(value: Optional[str]) -> Optional[datetime]:
    if value is None:
        return None
    text = value.strip()
    if not text or text in {"0000-00-00", "N/A"}:
        return None
    for fmt in DATE_FORMATS:
        try:
            dt = datetime.strptime(text, fmt)
            return dt.replace(tzinfo=timezone.utc) if dt.tzinfo is None else dt.astimezone(timezone.utc)
        except ValueError:
            continue
    try:
        # Attempt ISO-8601 parsing using fromisoformat when available
        dt = datetime.fromisoformat(text)
        return dt if dt.tzinfo else dt.replace(tzinfo=timezone.utc)
    except ValueError:
        logger.debug("Unable to parse datetime value %s", value)
        return None


def _within_window(value: datetime, start: datetime, end: datetime) -> bool:
    return start <= value < end


def _load_house_records(*, http: SimpleHttpClient, start: datetime, end: datetime) -> List[TradeRecord]:
    try:
        response = http.get(HOUSE_DATA_URL, timeout=60)
        response.raise_for_status()
        payload = response.json()
    except HTTPError as exc:
        logger.warning("Unable to load House trade data: %s", exc)
        return []
    except ValueError as exc:  # pragma: no cover - unexpected response
        logger.warning("House trade feed was not valid JSON: %s", exc)
        return []

    records: List[TradeRecord] = []
    if not isinstance(payload, list):
        logger.warning("Unexpected response when loading House trades: %s", type(payload))
        return records

    for item in payload:
        record = _parse_house_item(item)
        if not record:
            continue
        if not _within_window(record.reported, start, end):
            continue
        records.append(record)
    return records


def _parse_house_item(item: object) -> Optional[TradeRecord]:
    if not isinstance(item, dict):
        return None

    reported = _parse_datetime(
        item.get("disclosure_date")
        or item.get("report_date")
        or item.get("filed_date")
    )
    if reported is None:
        return None

    transaction_date = _parse_datetime(item.get("transaction_date"))
    legislator = item.get("representative") or item.get("member") or ""
    if not legislator:
        return None

    link = _first_non_empty(
        item.get("ptr_link"),
        item.get("disclosure_url"),
        item.get("report_link"),
        item.get("link"),
        _build_house_pdf_url(item, reported),
    )

    return TradeRecord(
        chamber="House",
        legislator=legislator,
        reported=reported,
        transaction_date=transaction_date,
        ticker=item.get("ticker") or item.get("symbol"),
        asset_description=item.get("asset_description") or item.get("asset"),
        transaction_type=item.get("type") or item.get("transaction"),
        amount=item.get("amount"),
        owner=item.get("owner"),
        link=link,
        source="house",
    )


def _build_house_pdf_url(item: dict, reported: datetime) -> Optional[str]:
    doc_id = item.get("document_id") or item.get("doc_id") or item.get("filing_id") or item.get("pdf")
    if not doc_id:
        return None
    doc_id = str(doc_id).strip()
    if not doc_id:
        return None
    if doc_id.lower().endswith(".pdf"):
        return f"https://disclosures-clerk.house.gov/public_disc/ptr-pdfs/{reported.year}/{doc_id}"
    return f"https://disclosures-clerk.house.gov/public_disc/ptr-pdfs/{reported.year}/{doc_id}.pdf"


def _load_senate_records(*, http: SimpleHttpClient, start: datetime, end: datetime) -> List[TradeRecord]:
    years_to_check = {start.year, end.year}
    if (end - start).days > 365:
        years_to_check.update({start.year - 1, end.year + 1})

    records: List[TradeRecord] = []
    for year in sorted(years_to_check):
        url = SENATE_DATA_URL_TEMPLATE.format(year=year)
        try:
            response = http.get(url, timeout=60)
            if response.status_code == 404:
                continue
            response.raise_for_status()
            payload = response.json()
        except HTTPError as exc:
            logger.warning("Unable to load Senate trade data for %s: %s", year, exc)
            continue
        except ValueError as exc:  # pragma: no cover - unexpected response
            logger.warning("Senate trade feed for %s was not valid JSON: %s", year, exc)
            continue

        if not isinstance(payload, list):
            logger.warning("Unexpected Senate response for %s: %s", year, type(payload))
            continue

        for item in payload:
            record = _parse_senate_item(item)
            if not record:
                continue
            if not _within_window(record.reported, start, end):
                continue
            records.append(record)
    return records


def _parse_senate_item(item: object) -> Optional[TradeRecord]:
    if not isinstance(item, dict):
        return None

    reported = _parse_datetime(
        item.get("report_date")
        or item.get("disclosure_date")
        or item.get("filed_date")
    )
    if reported is None:
        return None

    transaction_date = _parse_datetime(item.get("transaction_date"))
    legislator = item.get("senator") or item.get("member") or item.get("representative") or ""
    if not legislator:
        return None

    link = _first_non_empty(
        item.get("ptr_link"),
        item.get("url"),
        item.get("disclosure_url"),
        _build_senate_ptr_link(item),
    )

    return TradeRecord(
        chamber="Senate",
        legislator=legislator,
        reported=reported,
        transaction_date=transaction_date,
        ticker=item.get("ticker") or item.get("symbol"),
        asset_description=item.get("asset_description") or item.get("asset"),
        transaction_type=item.get("type") or item.get("transaction"),
        amount=item.get("amount"),
        owner=item.get("owner"),
        link=link,
        source="senate",
    )


def _build_senate_ptr_link(item: dict) -> Optional[str]:
    ptr_id = item.get("ptr_link_id") or item.get("report_id") or item.get("doc_id")
    if ptr_id:
        ptr_id = str(ptr_id).strip()
        if ptr_id:
            return f"https://efdsearch.senate.gov/search/view/ptr/{ptr_id}"
    return None


def _first_non_empty(*values: Optional[str]) -> Optional[str]:
    for value in values:
        if value:
            text = str(value).strip()
            if text:
                return text
    return None


__all__ = [
    "TradeRecord",
    "fetch_trades",
    "DEFAULT_MEMBERS",
]
