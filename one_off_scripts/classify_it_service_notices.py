"""Apply a versioned IT title taxonomy to historical KKJ service notices."""

from __future__ import annotations

import argparse
import hashlib
import json
import sqlite3
from contextlib import closing
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import pandas as pd

DEFAULT_DATABASE = Path("service_history.sqlite")
DEFAULT_TAXONOMY = Path("reference_data/it_service_taxonomy_v1_1.json")
DEFAULT_OUTPUT = Path("analysis_outputs/service_notices_classified_v1_1.csv")
DEFAULT_IT_OUTPUT = Path("analysis_outputs/it_service_notices_v1_1.csv")
DEFAULT_METADATA_OUTPUT = Path(
    "analysis_outputs/it_service_classification_v1_1_metadata.json"
)


def main() -> None:
    """Load notices, apply the taxonomy, and write reproducible analysis files."""

    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--database", type=Path, default=DEFAULT_DATABASE)
    parser.add_argument("--taxonomy", type=Path, default=DEFAULT_TAXONOMY)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument("--it-output", type=Path, default=DEFAULT_IT_OUTPUT)
    parser.add_argument(
        "--metadata-output", type=Path, default=DEFAULT_METADATA_OUTPUT
    )
    args = parser.parse_args()

    taxonomy = load_taxonomy(args.taxonomy)
    notices = load_notices(args.database)
    classified = classify_notices(notices, taxonomy)
    it_notices = classified.loc[classified["it_related"]].copy()

    write_csv(args.output, classified)
    write_csv(args.it_output, it_notices)
    write_metadata(
        args.metadata_output,
        database_path=args.database,
        taxonomy_path=args.taxonomy,
        taxonomy=taxonomy,
        classified=classified,
    )

    print(f"taxonomy version: {taxonomy['version']}")
    print(f"service notices classified: {len(classified)}")
    print(f"IT-related notices: {len(it_notices)}")
    print(f"IT share of services: {len(it_notices) / len(classified):.2%}")
    print(f"all classified notices: {args.output}")
    print(f"IT-related notices: {args.it_output}")
    print(f"run metadata: {args.metadata_output}")


def load_taxonomy(path: Path) -> dict[str, Any]:
    """Load and minimally validate the versioned taxonomy JSON."""

    taxonomy = json.loads(path.read_text(encoding="utf-8"))
    required_keys = {
        "version",
        "patterns",
        "core_it_delivery_subgroups",
        "adjacent_subgroups",
    }
    missing = required_keys - taxonomy.keys()
    if missing:
        raise ValueError(f"taxonomy is missing required keys: {sorted(missing)}")

    subgroup_names = set(taxonomy["patterns"])
    configured_names = set(taxonomy["core_it_delivery_subgroups"]) | set(
        taxonomy["adjacent_subgroups"]
    )
    if subgroup_names != configured_names:
        raise ValueError(
            "taxonomy patterns must equal the combined core and adjacent subgroups"
        )
    exclusion_names = set(taxonomy.get("exclusion_patterns", {}))
    if not exclusion_names <= subgroup_names:
        raise ValueError("taxonomy exclusions must refer to configured subgroups")
    return taxonomy


def load_notices(database_path: Path) -> pd.DataFrame:
    """Load full parsed notice models from SQLite and flatten them for analysis."""

    with closing(sqlite3.connect(database_path)) as connection:
        rows = connection.execute(
            "SELECT data_json FROM notices ORDER BY key"
        ).fetchall()

    records = [json.loads(row[0]) for row in rows]
    if not records:
        raise ValueError(f"no notices found in {database_path}")

    notices = pd.DataFrame.from_records(records)
    if notices["key"].duplicated().any():
        raise ValueError("database contains duplicate KKJ keys")

    # Full descriptions and raw XML remain available in SQLite. Excluding them
    # keeps the analysis CSVs compact and avoids large multiline text fields.
    notices = notices.drop(
        columns=["raw_xml", "project_description"], errors="ignore"
    )
    notices["attachment_count"] = notices["attachments"].map(len)
    notices["attachments_json"] = notices["attachments"].map(
        lambda value: json.dumps(value, ensure_ascii=False, separators=(",", ":"))
    )
    notices = notices.drop(columns=["attachments"])
    notices["cft_issue_year"] = pd.to_datetime(
        notices["cft_issue_date"], errors="coerce", utc=True
    ).dt.year.astype("Int64")
    return notices


def classify_notices(
    notices: pd.DataFrame, taxonomy: dict[str, Any]
) -> pd.DataFrame:
    """Apply multi-label subgroup patterns and derived high-level classifications."""

    classified = notices.copy()
    titles = classified["project_name"].fillna("")
    patterns: dict[str, str] = taxonomy["patterns"]
    exclusion_patterns: dict[str, str] = taxonomy.get("exclusion_patterns", {})
    tag_columns = list(patterns)

    for subgroup, pattern in patterns.items():
        matches = titles.str.contains(
            pattern,
            case=False,
            regex=True,
            na=False,
        )
        exclusion_pattern = exclusion_patterns.get(subgroup)
        if exclusion_pattern:
            matches &= ~titles.str.contains(
                exclusion_pattern,
                case=False,
                regex=True,
                na=False,
            )
        classified[subgroup] = matches

    core_columns: list[str] = taxonomy["core_it_delivery_subgroups"]
    adjacent_columns: list[str] = taxonomy["adjacent_subgroups"]
    classified["it_related"] = classified[tag_columns].any(axis=1)
    classified["core_it_delivery"] = classified[core_columns].any(axis=1)
    classified["digital_or_ai_adjacent"] = (
        classified[adjacent_columns].any(axis=1)
        & ~classified["core_it_delivery"]
    )
    classified["subgroup_count"] = classified[tag_columns].sum(axis=1)
    classified["matched_subgroups"] = classified[tag_columns].apply(
        lambda row: "|".join(row.index[row]),
        axis=1,
    )
    classified["taxonomy_version"] = taxonomy["version"]

    first_columns = [
        "key",
        "project_name",
        "organization_name",
        "lg_code",
        "prefecture_name",
        "city_code",
        "city_name",
        "cft_issue_date",
        "cft_issue_year",
        "category",
        "procedure_type",
        "external_document_uri",
        "taxonomy_version",
        "it_related",
        "core_it_delivery",
        "digital_or_ai_adjacent",
        "matched_subgroups",
        "subgroup_count",
        *tag_columns,
    ]
    remaining_columns = [
        column for column in classified.columns if column not in first_columns
    ]
    return classified[first_columns + remaining_columns].sort_values(
        ["cft_issue_date", "key"], na_position="last"
    )


def write_csv(path: Path, frame: pd.DataFrame) -> None:
    """Write an analysis DataFrame as UTF-8 CSV without its pandas index."""

    path.parent.mkdir(parents=True, exist_ok=True)
    frame.to_csv(path, index=False)


def write_metadata(
    path: Path,
    *,
    database_path: Path,
    taxonomy_path: Path,
    taxonomy: dict[str, Any],
    classified: pd.DataFrame,
) -> None:
    """Write provenance and row-count metadata for the classification run."""

    tag_columns = list(taxonomy["patterns"])
    metadata = {
        "created_at": datetime.now(UTC).isoformat(),
        "database": str(database_path),
        "taxonomy": str(taxonomy_path),
        "taxonomy_version": taxonomy["version"],
        "taxonomy_sha256": hashlib.sha256(taxonomy_path.read_bytes()).hexdigest(),
        "excluded_large_source_fields": ["raw_xml", "project_description"],
        "service_notice_count": len(classified),
        "it_related_notice_count": int(classified["it_related"].sum()),
        "core_it_delivery_notice_count": int(
            classified["core_it_delivery"].sum()
        ),
        "digital_or_ai_adjacent_notice_count": int(
            classified["digital_or_ai_adjacent"].sum()
        ),
        "subgroup_notice_counts": {
            column: int(classified[column].sum()) for column in tag_columns
        },
    }
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(metadata, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )


if __name__ == "__main__":
    main()
