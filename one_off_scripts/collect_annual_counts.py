"""Collect annual KKJ search-hit totals for trend analysis."""

from __future__ import annotations

import argparse
import csv
import logging
from datetime import UTC, datetime
from pathlib import Path

from one_off_scripts.collect_counts import CATEGORIES, PREFECTURES
from src.client import KkjClient
from src.parser import parse_search_response

DEFAULT_OUTPUT = Path("one_off_scripts/annual_counts.csv")
DEFAULT_START_YEAR = 2022
DEFAULT_END_YEAR = 2025


def main() -> None:
    """Query annual prefecture/category totals and write them to CSV."""

    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--start-year", type=int, default=DEFAULT_START_YEAR)
    parser.add_argument("--end-year", type=int, default=DEFAULT_END_YEAR)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    args = parser.parse_args()

    if args.start_year > args.end_year:
        parser.error("--start-year must be less than or equal to --end-year")

    logging.basicConfig(
        level=logging.INFO, format="%(levelname)s %(name)s: %(message)s"
    )
    rows = collect_annual_count_rows(args.start_year, args.end_year)
    write_csv(args.output, rows)
    print(f"wrote {len(rows)} rows to {args.output}")


def collect_annual_count_rows(
    start_year: int, end_year: int
) -> list[dict[str, str | int]]:
    """Fetch annual search hits for each selected prefecture and category."""

    client = KkjClient()
    collected_at = datetime.now(UTC).isoformat()
    rows: list[dict[str, str | int]] = []

    for year in range(start_year, end_year + 1):
        period_start = f"{year}-01-01"
        period_end = f"{year}-12-31"
        date_filter = f"{period_start}/{period_end}"

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
                        "period_start": period_start,
                        "period_end": period_end,
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
                    f"{year} / {prefecture.name_en} / {category.name_en}: "
                    f"{response.search_hits} hits"
                )

    return rows


def write_csv(path: Path, rows: list[dict[str, str | int]]) -> None:
    """Write annual count rows to a UTF-8 CSV file."""

    path.parent.mkdir(parents=True, exist_ok=True)
    fieldnames = [
        "year",
        "period_start",
        "period_end",
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
