"""Collect KKJ search-hit totals for the initial analysis matrix."""

from __future__ import annotations

import argparse
import csv
import logging
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path

from src.client import KkjClient
from src.parser import parse_search_response

DEFAULT_OUTPUT = Path("one_off_scripts/counts.csv")


@dataclass(frozen=True)
class Prefecture:
    """A prefecture included in the initial research sample."""

    lg_code: str
    name_ja: str
    name_en: str


@dataclass(frozen=True)
class Category:
    """A documented KKJ procurement category."""

    code: int
    name_ja: str
    name_en: str


PREFECTURES = (
    Prefecture("01", "北海道", "Hokkaido"),
    Prefecture("13", "東京都", "Tokyo"),
    Prefecture("14", "神奈川県", "Kanagawa"),
    Prefecture("23", "愛知県", "Aichi"),
    Prefecture("27", "大阪府", "Osaka"),
    Prefecture("40", "福岡県", "Fukuoka"),
)

CATEGORIES = (
    Category(1, "物品", "goods"),
    Category(2, "工事", "construction"),
    Category(3, "役務", "services"),
)


def main() -> None:
    """Query all prefecture/category combinations and write a CSV."""

    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    args = parser.parse_args()

    logging.basicConfig(
        level=logging.INFO, format="%(levelname)s %(name)s: %(message)s"
    )
    rows = collect_count_rows()
    write_csv(args.output, rows)
    print(f"wrote {len(rows)} rows to {args.output}")


def collect_count_rows() -> list[dict[str, str | int]]:
    """Fetch total search hits for the 18 initial analysis groups."""

    client = KkjClient()
    collected_at = datetime.now(UTC).isoformat()
    rows: list[dict[str, str | int]] = []

    for prefecture in PREFECTURES:
        for category in CATEGORIES:
            xml_text = client.search(
                lg_code=prefecture.lg_code,
                category=category.code,
                count=1,
            )
            response = parse_search_response(xml_text)
            rows.append(
                {
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
                f"{prefecture.name_en} / {category.name_en}: "
                f"{response.search_hits} hits"
            )

    return rows


def write_csv(path: Path, rows: list[dict[str, str | int]]) -> None:
    """Write count rows to a UTF-8 CSV file."""

    path.parent.mkdir(parents=True, exist_ok=True)
    fieldnames = [
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
