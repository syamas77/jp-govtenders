"""Compare two classified notice CSVs and export every taxonomy change."""

from __future__ import annotations

import argparse
from pathlib import Path

import pandas as pd

DEFAULT_OLD = Path("analysis_outputs/service_notices_classified_v1.csv")
DEFAULT_NEW = Path(
    "analysis_outputs/service_notices_classified_v1_1_candidate.csv"
)
DEFAULT_OUTPUT = Path("analysis_outputs/taxonomy_v1_to_v1_1_candidate_changes.csv")
IDENTITY_COLUMNS = [
    "key",
    "project_name",
    "organization_name",
    "lg_code",
    "prefecture_name",
    "cft_issue_year",
    "cft_issue_date",
    "external_document_uri",
]
CLASSIFICATION_COLUMNS = [
    "taxonomy_version",
    "it_related",
    "core_it_delivery",
    "digital_or_ai_adjacent",
    "matched_subgroups",
    "subgroup_count",
]


def main() -> None:
    """Load two classifications and write all changed rows."""

    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--old", type=Path, default=DEFAULT_OLD)
    parser.add_argument("--new", type=Path, default=DEFAULT_NEW)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    args = parser.parse_args()

    changes = compare_classifications(args.old, args.new)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    changes.to_csv(args.output, index=False)

    print(f"changed notices: {len(changes)}")
    for change_type, count in _change_type_counts(changes).items():
        print(f"{change_type}: {count}")
    print(f"output: {args.output}")


def compare_classifications(old_path: Path, new_path: Path) -> pd.DataFrame:
    """Return notices with membership, subgroup, or high-level changes."""

    old = pd.read_csv(old_path, dtype={"key": str, "lg_code": str}, low_memory=False)
    new = pd.read_csv(new_path, dtype={"key": str, "lg_code": str}, low_memory=False)
    if set(old["key"]) != set(new["key"]):
        raise ValueError("old and new classifications must contain identical KKJ keys")
    old["matched_subgroups"] = old["matched_subgroups"].fillna("")
    new["matched_subgroups"] = new["matched_subgroups"].fillna("")

    identity = new[IDENTITY_COLUMNS].copy()
    old_classification = old[["key", *CLASSIFICATION_COLUMNS]].rename(
        columns={column: f"old_{column}" for column in CLASSIFICATION_COLUMNS}
    )
    new_classification = new[["key", *CLASSIFICATION_COLUMNS]].rename(
        columns={column: f"new_{column}" for column in CLASSIFICATION_COLUMNS}
    )
    comparison = identity.merge(old_classification, on="key", validate="one_to_one")
    comparison = comparison.merge(new_classification, on="key", validate="one_to_one")

    comparison["change_types"] = comparison.apply(_change_types, axis=1)
    changes = comparison.loc[comparison["change_types"].ne("")].copy()
    changes["review_decision"] = ""
    changes["review_notes"] = ""
    return changes.sort_values(
        ["change_types", "cft_issue_year", "lg_code", "key"]
    ).reset_index(drop=True)


def _change_types(row: pd.Series) -> str:
    changes: list[str] = []
    if not row["old_it_related"] and row["new_it_related"]:
        changes.append("newly_matched")
    if row["old_it_related"] and not row["new_it_related"]:
        changes.append("removed_match")
    if row["old_matched_subgroups"] != row["new_matched_subgroups"]:
        changes.append("subgroup_changed")
    if (
        row["old_core_it_delivery"] != row["new_core_it_delivery"]
        or row["old_digital_or_ai_adjacent"]
        != row["new_digital_or_ai_adjacent"]
    ):
        changes.append("high_level_changed")
    return "|".join(changes)


def _change_type_counts(changes: pd.DataFrame) -> dict[str, int]:
    counts: dict[str, int] = {}
    for values in changes["change_types"].str.split("|"):
        for value in values:
            counts[value] = counts.get(value, 0) + 1
    return counts


if __name__ == "__main__":
    main()
