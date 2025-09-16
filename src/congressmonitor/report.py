from __future__ import annotations

import csv
from datetime import datetime
from pathlib import Path
from typing import Iterable, Sequence

from .monitor import TradeRecord


CSV_FIELDS = [
    "chamber",
    "legislator",
    "reported_date",
    "transaction_date",
    "ticker",
    "asset_description",
    "transaction_type",
    "amount",
    "owner",
    "link",
    "source",
]


def write_report(
    records: Sequence[TradeRecord],
    output_dir: Path | str,
    *,
    output_format: str = "csv",
    filename_prefix: str = "congress_trades",
    start: datetime,
    end: datetime,
) -> Path:
    """Serialize the trade records to disk in the requested format."""

    output_dir = Path(output_dir).expanduser()
    output_dir.mkdir(parents=True, exist_ok=True)

    ext = "csv" if output_format == "csv" else "txt"
    timestamp = datetime.now().strftime("%Y%m%d-%H%M%S")
    path = output_dir / f"{filename_prefix}_{timestamp}.{ext}"

    if output_format == "csv":
        _write_csv(records, path)
    else:
        _write_text(records, path, start=start, end=end)

    return path


def _write_csv(records: Sequence[TradeRecord], path: Path) -> None:
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=CSV_FIELDS)
        writer.writeheader()
        for record in records:
            writer.writerow(record.to_dict())


def _write_text(records: Sequence[TradeRecord], path: Path, *, start: datetime, end: datetime) -> None:
    lines = [
        f"Congressional stock trades from {start.isoformat()} to {end.isoformat()} (UTC)",
        "",
    ]

    if not records:
        lines.append("No matching trades were found in the selected interval.")
    else:
        for record in records:
            lines.extend(_format_text_record(record))
            lines.append("")

    contents = "\n".join(lines).rstrip() + "\n"
    path.write_text(contents, encoding="utf-8")


def _format_text_record(record: TradeRecord) -> Iterable[str]:
    header = f"{record.chamber} | {record.legislator}"
    if record.ticker:
        header += f" | {record.ticker}"
    details = [
        header,
        f"  Reported: {record.reported.date().isoformat()}  Transaction: {(record.transaction_date.date().isoformat() if record.transaction_date else 'Unknown')}",
        f"  Type: {record.transaction_type or 'Unknown'}  Amount: {record.amount or 'Unknown'}  Owner: {record.owner or 'Unknown'}",
    ]
    if record.asset_description:
        details.append(f"  Asset: {record.asset_description}")
    if record.link:
        details.append(f"  Link: {record.link}")
    return details


__all__ = ["write_report"]
