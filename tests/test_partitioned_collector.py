"""Tests for restartable date-partitioned collection."""

from __future__ import annotations

import tempfile
import unittest
from datetime import date
from pathlib import Path

from src.database import connect
from src.partitioned_collector import DatePeriod, ServiceHistoryCollector


class FakeClient:
    """Return deterministic XML responses keyed by the requested date period."""

    def __init__(self, responses: dict[str, str]) -> None:
        self.responses = responses
        self.calls: list[str] = []

    def search(self, **kwargs: object) -> str:
        period = str(kwargs["cft_issue_date"])
        self.calls.append(period)
        return self.responses[period]


def _response(search_hits: int, key: str | None = None) -> str:
    result = ""
    if key is not None:
        result = (
            "<SearchResult>"
            f"<ResultId>1</ResultId><Key>{key}</Key>"
            "<ProjectName>test notice</ProjectName><Category>役務</Category>"
            "</SearchResult>"
        )
    return (
        "<Results><Version>1</Version><SearchResults>"
        f"<SearchHits>{search_hits}</SearchHits>{result}"
        "</SearchResults></Results>"
    )


class DatePeriodTest(unittest.TestCase):
    def test_split_is_inclusive_and_non_overlapping(self) -> None:
        period = DatePeriod(date(2025, 1, 1), date(2025, 1, 4))

        left, right = period.split()

        self.assertEqual(left, DatePeriod(date(2025, 1, 1), date(2025, 1, 2)))
        self.assertEqual(right, DatePeriod(date(2025, 1, 3), date(2025, 1, 4)))


class ServiceHistoryCollectorTest(unittest.TestCase):
    def test_splits_oversized_period_and_skips_completed_children(self) -> None:
        responses = {
            "2025-01-01/2025-01-02": _response(3),
            "2025-01-01/2025-01-01": _response(1, "first"),
            "2025-01-02/2025-01-02": _response(1, "second"),
        }
        client = FakeClient(responses)
        period = DatePeriod(date(2025, 1, 1), date(2025, 1, 2))

        with tempfile.TemporaryDirectory() as directory:
            database = Path(directory) / "notices.sqlite"
            with connect(database) as connection:
                collector = ServiceHistoryCollector(
                    client=client,  # type: ignore[arg-type]
                    connection=connection,
                    request_delay=0,
                    max_count=2,
                )
                collector.collect(lg_code="13", period=period)
                collector.collect(lg_code="13", period=period)

                statuses = connection.execute(
                    """
                    SELECT period_start, period_end, status
                    FROM collection_periods
                    ORDER BY period_start, period_end
                    """
                ).fetchall()
                notice_count = connection.execute(
                    "SELECT COUNT(*) FROM notices"
                ).fetchone()[0]

        self.assertEqual(len(client.calls), 3)
        self.assertEqual(notice_count, 2)
        self.assertEqual(collector.summary.completed_periods, 2)
        self.assertEqual(collector.summary.skipped_periods, 2)
        self.assertEqual(
            statuses,
            [
                ("2025-01-01", "2025-01-01", "completed"),
                ("2025-01-01", "2025-01-02", "split"),
                ("2025-01-02", "2025-01-02", "completed"),
            ],
        )


if __name__ == "__main__":
    unittest.main()
