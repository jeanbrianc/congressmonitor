from __future__ import annotations

import argparse
import logging
import sys
from datetime import datetime, timedelta, timezone
from typing import Optional, Sequence

from .monitor import DEFAULT_MEMBERS, TradeRecord, fetch_trades
from .report import write_report


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Generate a report of congressional stock trade disclosures.",
    )
    parser.add_argument(
        "--members",
        "-m",
        nargs="*",
        help=(
            "Names of legislators to monitor. Provide multiple names separated by spaces."
            " Use the literal 'all' to disable filtering."
        ),
    )
    parser.add_argument(
        "--lookback-hours",
        type=float,
        default=24.0,
        help="Number of hours to look back when --since is omitted (default: 24).",
    )
    parser.add_argument(
        "--since",
        type=str,
        help="Optional ISO 8601 timestamp marking the inclusive start of the reporting window.",
    )
    parser.add_argument(
        "--until",
        type=str,
        help="Optional ISO 8601 timestamp marking the exclusive end of the reporting window (defaults to now).",
    )
    parser.add_argument(
        "--output-dir",
        default="~/Desktop",
        help="Directory where the generated report should be written (default: ~/Desktop).",
    )
    parser.add_argument(
        "--output-format",
        choices=("csv", "txt"),
        default="csv",
        help="File format for the generated report (default: csv).",
    )
    parser.add_argument(
        "--filename-prefix",
        default="congress_trades",
        help="Prefix to use for the output filename (default: congress_trades).",
    )
    parser.add_argument(
        "--skip-house",
        action="store_true",
        help="Skip fetching U.S. House of Representatives disclosures.",
    )
    parser.add_argument(
        "--skip-senate",
        action="store_true",
        help="Skip fetching U.S. Senate disclosures.",
    )
    parser.add_argument(
        "--max-records",
        type=int,
        help="Optional cap on the number of records written to the report (after sorting).",
    )
    parser.add_argument(
        "--verbose",
        action="store_true",
        help="Enable verbose logging for debugging purposes.",
    )
    parser.add_argument(
        "--quiet",
        action="store_true",
        help="Suppress informational console output.",
    )
    return parser


def main(argv: Optional[Sequence[str]] = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)

    if args.lookback_hours <= 0:
        parser.error("--lookback-hours must be greater than zero")

    members = _resolve_members(args.members)
    start, end = _resolve_interval(args.since, args.until, lookback_hours=args.lookback_hours)

    logging.basicConfig(level=logging.DEBUG if args.verbose else logging.INFO)
    if args.quiet:
        logging.getLogger().setLevel(logging.WARNING)

    try:
        records = fetch_trades(
            members=members,
            since=start,
            until=end,
            include_house=not args.skip_house,
            include_senate=not args.skip_senate,
        )
    except Exception as exc:  # pragma: no cover - fatal fallback
        logging.getLogger(__name__).exception("Failed to retrieve trade data: %s", exc)
        return 1

    if args.max_records is not None and args.max_records >= 0:
        records = records[: args.max_records]

    output_path = write_report(
        records,
        args.output_dir,
        output_format=args.output_format,
        filename_prefix=args.filename_prefix,
        start=start,
        end=end,
    )

    if not args.quiet:
        _print_summary(records, output_path)

    return 0


def _resolve_members(value: Optional[Sequence[str]]) -> Optional[Sequence[str]]:
    if value is None or len(value) == 0:
        return DEFAULT_MEMBERS
    flattened: list[str] = []
    for entry in value:
        if not entry:
            continue
        flattened.extend(part.strip() for part in entry.split(",") if part.strip())
    if not flattened:
        return DEFAULT_MEMBERS
    if any(part.lower() == "all" for part in flattened):
        return None
    return flattened


def _resolve_interval(
    since_text: Optional[str],
    until_text: Optional[str],
    *,
    lookback_hours: float,
) -> tuple[datetime, datetime]:
    end = _parse_cli_datetime(until_text) or datetime.now(tz=timezone.utc)
    start = _parse_cli_datetime(since_text)
    if start is None:
        start = end - timedelta(hours=lookback_hours)
    if start >= end:
        raise SystemExit("The start of the reporting window must be earlier than the end.")
    return start, end


def _parse_cli_datetime(value: Optional[str]) -> Optional[datetime]:
    if not value:
        return None
    text = value.strip()
    if not text:
        return None
    for fmt in (
        "%Y-%m-%dT%H:%M:%S%z",
        "%Y-%m-%dT%H:%M:%S",
        "%Y-%m-%dT%H:%M",
        "%Y-%m-%d",
        "%m/%d/%Y",
    ):
        try:
            dt = datetime.strptime(text, fmt)
            if dt.tzinfo is None:
                dt = dt.replace(tzinfo=timezone.utc)
            return dt.astimezone(timezone.utc)
        except ValueError:
            continue
    try:
        dt = datetime.fromisoformat(text)
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        return dt.astimezone(timezone.utc)
    except ValueError:
        raise SystemExit(f"Unable to parse datetime value: {value!r}") from None


def _print_summary(records: Sequence[TradeRecord], output_path) -> None:
    count = len(records)
    message = f"Wrote {count} trade{'s' if count != 1 else ''} to {output_path}"
    print(message)


if __name__ == "__main__":  # pragma: no cover
    sys.exit(main())
