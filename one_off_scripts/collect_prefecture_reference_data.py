"""Build prefecture population and area reference CSVs from official sources."""

from __future__ import annotations

import csv
from io import BytesIO
from pathlib import Path
from typing import Any

import httpx
import pandas as pd

from one_off_scripts.collect_counts import PREFECTURES

REFERENCE_DATA_DIR = Path("reference_data")
POPULATION_OUTPUT = REFERENCE_DATA_DIR / "prefecture_population.csv"
AREA_OUTPUT = REFERENCE_DATA_DIR / "prefecture_area.csv"

POPULATION_ESTIMATE_URLS = {
    2022: "https://www.stat.go.jp/data/jinsui/2022np/zuhyou/05k2022-2.xlsx",
    2023: "https://www.stat.go.jp/data/jinsui/2023np/zuhyou/05k2023-2.xlsx",
    2024: "https://www.stat.go.jp/data/jinsui/2024np/zuhyou/05k2024-2.xlsx",
}
CENSUS_2025_URL = (
    "https://www.e-stat.go.jp/stat-search/file-download?"
    "statInfId=000040454825&fileKind=0"
)
GSI_AREA_SOURCE_URL = "https://www.gsi.go.jp/KOKUJYOHO/MENCHO-title.htm"


def main() -> None:
    """Download official workbooks and write normalized reference CSVs."""

    population_rows: list[dict[str, Any]] = []
    with httpx.Client(timeout=60.0, follow_redirects=True) as client:
        for year, url in POPULATION_ESTIMATE_URLS.items():
            workbook = download_workbook(client, url)
            population_rows.extend(parse_population_estimates(workbook, year, url))

        census_workbook = download_workbook(client, CENSUS_2025_URL)
        census_population_rows, area_rows = parse_2025_census(census_workbook)
        population_rows.extend(census_population_rows)

    write_rows(POPULATION_OUTPUT, population_rows)
    write_rows(AREA_OUTPUT, area_rows)
    print(f"wrote {len(population_rows)} rows to {POPULATION_OUTPUT}")
    print(f"wrote {len(area_rows)} rows to {AREA_OUTPUT}")


def download_workbook(client: httpx.Client, url: str) -> bytes:
    """Download one official Excel workbook."""

    response = client.get(url)
    response.raise_for_status()
    return response.content


def parse_population_estimates(
    workbook: bytes, year: int, source_url: str
) -> list[dict[str, Any]]:
    """Parse selected prefectures from an annual Population Estimates table."""

    frame = pd.read_excel(BytesIO(workbook), sheet_name=0, header=None)
    rows: list[dict[str, Any]] = []

    for prefecture in PREFECTURES:
        matches = frame[
            (frame[1].astype(str).str.strip() == prefecture.lg_code)
            & (frame[2].astype(str).str.strip() == prefecture.name_ja)
        ]
        if len(matches) != 1:
            raise ValueError(
                f"expected one {year} population row for {prefecture.name_ja}, "
                f"found {len(matches)}"
            )

        # The official table is published in thousands of people. Preserve the
        # source unit and convert it to people for analysis joins.
        source_value_thousands = int(matches.iloc[0, 4])
        rows.append(
            {
                "year": year,
                "population_as_of_date": f"{year}-10-01",
                "lg_code": prefecture.lg_code,
                "prefecture_ja": prefecture.name_ja,
                "prefecture_en": prefecture.name_en,
                "population": source_value_thousands * 1_000,
                "source_population_value": source_value_thousands,
                "source_unit": "thousand people",
                "source_series": "Population Estimates",
                "value_status": "estimate; rounded to nearest thousand",
                "source_url": source_url,
            }
        )

    return rows


def parse_2025_census(
    workbook: bytes,
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    """Parse preliminary 2025 Census population and GSI-based area values."""

    frame = pd.read_excel(BytesIO(workbook), sheet_name=0, header=None)
    population_rows: list[dict[str, Any]] = []
    area_rows: list[dict[str, Any]] = []

    for prefecture in PREFECTURES:
        prefecture_label = f"{prefecture.lg_code}_{prefecture.name_ja}"
        matches = frame[
            (frame[0].astype(str).str.strip() == "a")
            & (frame[1].astype(str).str.strip() == prefecture_label)
        ]
        if len(matches) != 1:
            raise ValueError(
                f"expected one 2025 Census row for {prefecture.name_ja}, "
                f"found {len(matches)}"
            )

        row = matches.iloc[0]
        population_rows.append(
            {
                "year": 2025,
                "population_as_of_date": "2025-10-01",
                "lg_code": prefecture.lg_code,
                "prefecture_ja": prefecture.name_ja,
                "prefecture_en": prefecture.name_en,
                "population": int(row[3]),
                "source_population_value": int(row[3]),
                "source_unit": "people",
                "source_series": "2025 Population Census",
                "value_status": "preliminary count",
                "source_url": CENSUS_2025_URL,
            }
        )
        area_rows.append(
            {
                "area_as_of_date": "2025-10-01",
                "lg_code": prefecture.lg_code,
                "prefecture_ja": prefecture.name_ja,
                "prefecture_en": prefecture.name_en,
                "area_km2": float(row[10]),
                "source_name": "GSI prefecture and municipality area survey",
                "source_url": GSI_AREA_SOURCE_URL,
                "source_table_url": CENSUS_2025_URL,
            }
        )

    return population_rows, area_rows


def write_rows(path: Path, rows: list[dict[str, Any]]) -> None:
    """Write dictionaries to a UTF-8 CSV using their shared keys."""

    if not rows:
        raise ValueError(f"no rows to write to {path}")
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as output_file:
        writer = csv.DictWriter(output_file, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)


if __name__ == "__main__":
    main()
