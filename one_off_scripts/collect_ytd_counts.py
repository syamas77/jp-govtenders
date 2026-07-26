"""Collect KKJ year-to-date search-hit totals for a separate analysis."""

from __future__ import annotations

import argparse
import csv
import logging
from datetime import UTC, date, datetime
from pathlib import Path
from zoneinfo import ZoneInfo

from one_off_scripts.collect_counts import CATEGORIES, PREFECTURES
from src.client import KkjClient
from src.parser import parse_search_response

DEFAULT_OUTPUT = Path("one_off_scripts/ytd_counts.csv")
JAPAN_TIME_ZONE = ZoneInfo("Asia/Tokyo")


def main() -> None:
    """Query prefecture/category totals from January 1 through an as-of date."""

    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--as-of-date",
        type=date.fromisoformat,
        default=datetime.now(JAPAN_TIME_ZONE).date(),
        help="Final inclusive date in YYYY-MM-DD format. Defaults to today in Japan.",
    )
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    args = parser.parse_args()

    logging.basicConfig(
        level=logging.INFO, format="%(levelname)s %(name)s: %(message)s"
    )
    rows = collect_ytd_count_rows(args.as_of_date)
    write_csv(args.output, rows)
    print(f"wrote {len(rows)} rows to {args.output}")


def collect_ytd_count_rows(as_of_date: date) -> list[dict[str, str | int | bool]]:
    """Fetch year-to-date search hits for each prefecture and category."""

    client = KkjClient()
    collected_at = datetime.now(UTC).isoformat()
    year = as_of_date.year
    period_start = date(year, 1, 1)
    date_filter = f"{period_start.isoformat()}/{as_of_date.isoformat()}"
    rows: list[dict[str, str | int | bool]] = []

    for prefecture in PREFECTURES:
        for category in CATEGORIES:
            xml_text = client.search(
                lg_code=prefecture.lg_code,
                category=category.code,
                cft_issue_date=date_filter,
                count=1,
            )
            response = parse_search_response(xml_text)
            rows.append(
                {
                    "year": year,
                    "period_label": f"{year} YTD",
                    "period_start": period_start.isoformat(),
                    "period_end": as_of_date.isoformat(),
                    "is_complete_year": False,
                    "lg_code": prefecture.lg_code,
                    "prefecture_ja": prefecture.name_ja,
                    "prefecture_en": prefecture.name_en,
                    "category_code": category.code,
                    "category_ja": category.name_ja,
                    "category_en": category.name_en,
                    "search_hits": response.search_hits or 0,
                    "collected_at": collected_at,
                }
            )
            print(
                f"{year} YTD / {prefecture.name_en} / {category.name_en}: "
                f"{response.search_hits} hits"
            )

    return rows


def write_csv(path: Path, rows: list[dict[str, str | int | bool]]) -> None:
    """Write year-to-date count rows to a UTF-8 CSV file."""

    path.parent.mkdir(parents=True, exist_ok=True)
    fieldnames = [
        "year",
        "period_label",
        "period_start",
        "period_end",
        "is_complete_year",
        "lg_code",
        "prefecture_ja",
        "prefecture_en",
        "category_code",
        "category_ja",
        "category_en",
        "search_hits",
        "collected_at",
    ]
    with path.open("w", encoding="utf-8", newline="") as output_file:
        writer = csv.DictWriter(output_file, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)


if __name__ == "__main__":
    main()
