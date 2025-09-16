from __future__ import annotations

import csv
import tempfile
import unittest
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, List
from unittest import mock

from congressmonitor import cli
from congressmonitor.http import HTTPError
from congressmonitor.monitor import TradeRecord, fetch_trades


class DummyResponse:
    def __init__(self, payload, status_code: int = 200):
        self._payload = payload
        self.status_code = status_code

    def json(self):
        return self._payload

    def raise_for_status(self):
        if 400 <= self.status_code:
            raise HTTPError(f"HTTP {self.status_code}", status=self.status_code)


class StubSession:
    def __init__(self, house_payload: List[dict], senate_payloads: Dict[int, List[dict]]):
        self.house_payload = house_payload
        self.senate_payloads = senate_payloads
        self.requested_urls: List[str] = []

    def get(self, url: str, timeout: int = 60):  # pragma: no cover - straightforward
        self.requested_urls.append(url)
        if "house-stock-watcher" in url:
            return DummyResponse(self.house_payload)
        if "senate-stock-watcher" in url:
            for year, payload in self.senate_payloads.items():
                if str(year) in url:
                    return DummyResponse(payload)
            return DummyResponse([], status_code=404)
        raise AssertionError(f"Unexpected URL requested: {url}")


HOUSE_SAMPLE = [
    {
        "disclosure_date": "2024-05-10",
        "transaction_date": "2024-05-09",
        "representative": "Nancy Pelosi",
        "ticker": "AAPL",
        "asset_description": "Apple Inc.",
        "type": "Purchase",
        "amount": "$15,001 - $50,000",
        "owner": "Spouse",
        "ptr_link": "https://house.example/1.pdf",
    },
    {
        "disclosure_date": "2024-05-04",
        "transaction_date": "2024-05-02",
        "representative": "Nancy Pelosi",
        "ticker": "MSFT",
        "asset_description": "Microsoft Corp.",
        "type": "Sale",
        "amount": "$15,001 - $50,000",
        "owner": "Spouse",
        "ptr_link": "https://house.example/old.pdf",
    },
]


SENATE_SAMPLE = [
    {
        "report_date": "2024-05-10",
        "transaction_date": "2024-05-09",
        "senator": "Ron Wyden",
        "ticker": "MSFT",
        "asset_description": "Microsoft Corp.",
        "type": "Sale (Partial)",
        "amount": "$50,001 - $100,000",
        "owner": "Self",
        "ptr_link": "https://senate.example/1",
    },
    {
        "report_date": "2023-12-31",
        "transaction_date": "2023-12-15",
        "senator": "Ron Wyden",
        "ticker": "AAPL",
        "asset_description": "Apple Inc.",
        "type": "Purchase",
        "amount": "$1,001 - $15,000",
        "owner": "Self",
        "ptr_link": "https://senate.example/old",
    },
]


class FetchTradesTests(unittest.TestCase):
    def test_filters_by_member_and_interval(self):
        session = StubSession(HOUSE_SAMPLE, senate_payloads={2024: SENATE_SAMPLE})
        start = datetime(2024, 5, 8, tzinfo=timezone.utc)
        end = datetime(2024, 5, 11, tzinfo=timezone.utc)

        records = fetch_trades(
            members=["Nancy Pelosi", "Ron Wyden"],
            since=start,
            until=end,
            session=session,
        )

        self.assertEqual({record.legislator for record in records}, {"Nancy Pelosi", "Ron Wyden"})
        for record in records:
            self.assertLess(start, record.reported)
            self.assertLess(record.reported, end)
            self.assertTrue(record.link)
            self.assertNotEqual(record.link, "https://house.example/old.pdf")
            self.assertNotEqual(record.link, "https://senate.example/old")

    def test_without_member_filter_returns_recent(self):
        session = StubSession(HOUSE_SAMPLE, senate_payloads={2024: SENATE_SAMPLE})
        start = datetime(2024, 5, 8, tzinfo=timezone.utc)
        end = datetime(2024, 5, 11, tzinfo=timezone.utc)

        records = fetch_trades(
            members=None,
            since=start,
            until=end,
            session=session,
        )

        self.assertEqual(len(records), 2)
        self.assertEqual({record.chamber for record in records}, {"House", "Senate"})


class CLITests(unittest.TestCase):
    def test_cli_writes_csv_report(self):
        sample_records = [
            TradeRecord(
                chamber="House",
                legislator="Nancy Pelosi",
                reported=datetime(2024, 5, 10, tzinfo=timezone.utc),
                transaction_date=datetime(2024, 5, 9, tzinfo=timezone.utc),
                ticker="AAPL",
                asset_description="Apple Inc.",
                transaction_type="Purchase",
                amount="$15,001 - $50,000",
                owner="Spouse",
                link="https://house.example/1.pdf",
                source="house",
            )
        ]

        with mock.patch.object(cli, "fetch_trades", return_value=sample_records):
            with tempfile.TemporaryDirectory() as tmp_dir:
                args = [
                    "--output-dir",
                    tmp_dir,
                    "--output-format",
                    "csv",
                    "--since",
                    "2024-05-01",
                    "--until",
                    "2024-05-11T00:00:00",
                    "--members",
                    "all",
                    "--quiet",
                ]

                exit_code = cli.main(args)
                self.assertEqual(exit_code, 0)

                paths = list(Path(tmp_dir).iterdir())
                self.assertEqual(len(paths), 1)
                with paths[0].open(newline="", encoding="utf-8") as handle:
                    reader = csv.DictReader(handle)
                    rows = list(reader)

                self.assertEqual(rows[0]["legislator"], "Nancy Pelosi")
                self.assertEqual(rows[0]["link"], "https://house.example/1.pdf")
                self.assertEqual(rows[0]["transaction_type"], "Purchase")


if __name__ == "__main__":  # pragma: no cover
    unittest.main()
