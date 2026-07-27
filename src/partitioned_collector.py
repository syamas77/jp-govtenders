"""Restartable date-partitioned collection for historical KKJ service notices."""

from __future__ import annotations

import calendar
import logging
import sqlite3
import time
from dataclasses import dataclass
from datetime import UTC, date, datetime, timedelta
from pathlib import Path

from src.client import KkjClient
from src.database import connect, insert_notices
from src.models import SearchResponse
from src.parser import parse_search_response

LOGGER = logging.getLogger(__name__)
MAX_KKJ_COUNT = 1000
DEFAULT_LG_CODES = ("01", "13", "14", "23", "27", "40")


@dataclass(frozen=True, order=True)
class DatePeriod:
    """Inclusive date period used with the KKJ ``CFT_Issue_Date`` filter."""

    start: date
    end: date

    def __post_init__(self) -> None:
        if self.end < self.start:
            raise ValueError("period end must be on or after period start")

    @property
    def api_value(self) -> str:
        """Return the period in the format documented by the KKJ API."""

        return f"{self.start.isoformat()}/{self.end.isoformat()}"

    def split(self) -> tuple[DatePeriod, DatePeriod]:
        """Split a multi-day period into two non-overlapping inclusive periods."""

        if self.start == self.end:
            raise ValueError("a one-day period cannot be split")
        midpoint = self.start + timedelta(days=(self.end - self.start).days // 2)
        return (
            DatePeriod(self.start, midpoint),
            DatePeriod(midpoint + timedelta(days=1), self.end),
        )


@dataclass
class PartitionedCollectionSummary:
    """Aggregated result counters for one historical collection run."""

    requests: int = 0
    completed_periods: int = 0
    skipped_periods: int = 0
    split_periods: int = 0
    failed_periods: int = 0
    expected_notices: int = 0
    returned_notices: int = 0
    inserted_notices: int = 0


class ServiceHistoryCollector:
    """Collect category 3 notices and recursively split oversized periods."""

    def __init__(
        self,
        *,
        client: KkjClient,
        connection: sqlite3.Connection,
        request_delay: float = 0.2,
        max_count: int = MAX_KKJ_COUNT,
    ) -> None:
        if request_delay < 0:
            raise ValueError("request_delay must be non-negative")
        if not 1 <= max_count <= MAX_KKJ_COUNT:
            raise ValueError(f"max_count must be between 1 and {MAX_KKJ_COUNT}")
        self.client = client
        self.connection = connection
        self.request_delay = request_delay
        self.max_count = max_count
        self.summary = PartitionedCollectionSummary()
        self._last_request_time: float | None = None

    def collect(self, *, lg_code: str, period: DatePeriod) -> None:
        """Collect one period, recursively splitting it when it exceeds the cap."""

        status = _period_status(
            self.connection,
            lg_code=lg_code,
            category=3,
            period=period,
        )
        if status == "completed":
            self.summary.skipped_periods += 1
            LOGGER.info("skipping completed period %s %s", lg_code, period.api_value)
            return
        if status == "split":
            self.summary.split_periods += 1
            for child in period.split():
                self.collect(lg_code=lg_code, period=child)
            return

        search_hits: int | None = None
        returned_count: int | None = None
        try:
            response = self._request(lg_code=lg_code, period=period)
            search_hits = response.search_hits
            if search_hits is None:
                raise ValueError("KKJ response did not contain SearchHits")

            returned_count = len(response.notices)
            if search_hits > self.max_count:
                if period.start == period.end:
                    raise ValueError(
                        f"one-day period has {search_hits} hits, above the "
                        f"documented {self.max_count}-notice return cap"
                    )
                _save_period(
                    self.connection,
                    lg_code=lg_code,
                    category=3,
                    period=period,
                    status="split",
                    search_hits=search_hits,
                    returned_count=returned_count,
                )
                self.summary.split_periods += 1
                for child in period.split():
                    self.collect(lg_code=lg_code, period=child)
                return

            if returned_count != search_hits:
                raise ValueError(
                    f"expected {search_hits} notices but KKJ returned {returned_count}"
                )

            inserted_count = insert_notices(self.connection, response.notices)
            _save_period(
                self.connection,
                lg_code=lg_code,
                category=3,
                period=period,
                status="completed",
                search_hits=search_hits,
                returned_count=returned_count,
                inserted_count=inserted_count,
            )
            self.summary.completed_periods += 1
            self.summary.expected_notices += search_hits
            self.summary.returned_notices += returned_count
            self.summary.inserted_notices += inserted_count
            LOGGER.info(
                "completed %s %s: hits=%d returned=%d inserted=%d",
                lg_code,
                period.api_value,
                search_hits,
                returned_count,
                inserted_count,
            )
        except Exception as exc:  # noqa: BLE001 -- record failure and continue periods
            _save_period(
                self.connection,
                lg_code=lg_code,
                category=3,
                period=period,
                status="failed",
                search_hits=search_hits,
                returned_count=returned_count,
                error=str(exc),
            )
            self.summary.failed_periods += 1
            LOGGER.error("failed %s %s: %s", lg_code, period.api_value, exc)

    def _request(self, *, lg_code: str, period: DatePeriod) -> SearchResponse:
        """Rate-limit and execute one KKJ request."""

        if self._last_request_time is not None:
            elapsed = time.monotonic() - self._last_request_time
            if elapsed < self.request_delay:
                time.sleep(self.request_delay - elapsed)
        try:
            xml_text = self.client.search(
                count=self.max_count,
                lg_code=lg_code,
                category=3,
                cft_issue_date=period.api_value,
            )
        finally:
            self._last_request_time = time.monotonic()
            self.summary.requests += 1
        return parse_search_response(xml_text)


def collect_service_history(
    *,
    database_path: Path,
    start_year: int = 2022,
    end_year: int = 2025,
    lg_codes: tuple[str, ...] = DEFAULT_LG_CODES,
    request_delay: float = 0.2,
) -> PartitionedCollectionSummary:
    """Collect monthly service notices for inclusive years and prefecture codes."""

    if end_year < start_year:
        raise ValueError("end_year must be on or after start_year")
    periods = list(_monthly_periods(start_year=start_year, end_year=end_year))

    with KkjClient() as client, connect(database_path) as connection:
        collector = ServiceHistoryCollector(
            client=client,
            connection=connection,
            request_delay=request_delay,
        )
        for lg_code in lg_codes:
            for period in periods:
                collector.collect(lg_code=lg_code, period=period)
        return collector.summary


def _monthly_periods(*, start_year: int, end_year: int):
    """Yield inclusive calendar-month periods for an inclusive year range."""

    for year in range(start_year, end_year + 1):
        for month in range(1, 13):
            last_day = calendar.monthrange(year, month)[1]
            yield DatePeriod(date(year, month, 1), date(year, month, last_day))


def _period_status(
    connection: sqlite3.Connection,
    *,
    lg_code: str,
    category: int,
    period: DatePeriod,
) -> str | None:
    row = connection.execute(
        """
        SELECT status
        FROM collection_periods
        WHERE lg_code = ? AND category = ?
          AND period_start = ? AND period_end = ?
        """,
        (lg_code, category, period.start.isoformat(), period.end.isoformat()),
    ).fetchone()
    return row[0] if row is not None else None


def _save_period(
    connection: sqlite3.Connection,
    *,
    lg_code: str,
    category: int,
    period: DatePeriod,
    status: str,
    search_hits: int | None = None,
    returned_count: int | None = None,
    inserted_count: int | None = None,
    error: str | None = None,
) -> None:
    """Insert or update collection state for one period."""

    now = datetime.now(UTC).isoformat()
    completed_at = now if status == "completed" else None
    connection.execute(
        """
        INSERT INTO collection_periods (
            lg_code, category, period_start, period_end, status,
            search_hits, returned_count, inserted_count, error,
            attempted_at, completed_at
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        ON CONFLICT (lg_code, category, period_start, period_end) DO UPDATE SET
            status = excluded.status,
            search_hits = excluded.search_hits,
            returned_count = excluded.returned_count,
            inserted_count = excluded.inserted_count,
            error = excluded.error,
            attempted_at = excluded.attempted_at,
            completed_at = excluded.completed_at
        """,
        (
            lg_code,
            category,
            period.start.isoformat(),
            period.end.isoformat(),
            status,
            search_hits,
            returned_count,
            inserted_count,
            error,
            now,
            completed_at,
        ),
    )
    connection.commit()
