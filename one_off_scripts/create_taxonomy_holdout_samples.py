"""Create independent simple-random holdout samples for taxonomy validation."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

import pandas as pd

DEFAULT_INPUT = Path(
    "analysis_outputs/service_notices_classified_v1_1_candidate.csv"
)
DEFAULT_MATCHED_OUTPUT = Path(
    "analysis_outputs/taxonomy_v1_1_matched_holdout.csv"
)
DEFAULT_UNMATCHED_OUTPUT = Path(
    "analysis_outputs/taxonomy_v1_1_unmatched_holdout.csv"
)
DEFAULT_METADATA_OUTPUT = Path(
    "analysis_outputs/taxonomy_v1_1_holdout_metadata.json"
)
DEFAULT_MATCHED_SIZE = 150
DEFAULT_UNMATCHED_SIZE = 200
DEFAULT_RANDOM_STATE = 20260731
DEFAULT_DEVELOPMENT_FILES = (
    Path("analysis_outputs/unmatched_service_titles_reviewed.csv"),
    Path("analysis_outputs/unmatched_service_titles_review_round2_reviewed.csv"),
    Path("analysis_outputs/historical_unmatched_taxonomy_review_v1_reviewed.csv"),
    Path("analysis_outputs/historical_matched_taxonomy_review_v1_reviewed.csv"),
    Path("analysis_outputs/taxonomy_v1_to_v1_1_candidate_changes_reviewed.csv"),
    Path("analysis_outputs/taxonomy_v1_1_matched_holdout_reviewed.csv"),
    Path("analysis_outputs/taxonomy_v1_1_unmatched_holdout_reviewed.csv"),
    Path("analysis_outputs/taxonomy_v1_to_v1_1_candidate2_changes_reviewed.csv"),
    Path("analysis_outputs/taxonomy_v1_1_candidate2_final_matched_holdout_reviewed.csv"),
    Path("analysis_outputs/taxonomy_v1_1_candidate2_final_unmatched_holdout_reviewed.csv"),
    Path("analysis_outputs/taxonomy_v1_to_v1_1_lean_candidate_changes_reviewed.csv"),
)


def main() -> None:
    """Sample matched and unmatched notices not used during taxonomy development."""

    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input", type=Path, default=DEFAULT_INPUT)
    parser.add_argument("--matched-size", type=int, default=DEFAULT_MATCHED_SIZE)
    parser.add_argument("--unmatched-size", type=int, default=DEFAULT_UNMATCHED_SIZE)
    parser.add_argument("--random-state", type=int, default=DEFAULT_RANDOM_STATE)
    parser.add_argument("--matched-output", type=Path, default=DEFAULT_MATCHED_OUTPUT)
    parser.add_argument(
        "--unmatched-output", type=Path, default=DEFAULT_UNMATCHED_OUTPUT
    )
    parser.add_argument(
        "--metadata-output", type=Path, default=DEFAULT_METADATA_OUTPUT
    )
    args = parser.parse_args()
    if args.matched_size < 1 or args.unmatched_size < 1:
        parser.error("holdout sample sizes must be positive")

    classified = pd.read_csv(
        args.input,
        dtype={"key": str, "lg_code": str, "city_code": str},
        low_memory=False,
    )
    excluded_keys, used_files = load_development_keys(DEFAULT_DEVELOPMENT_FILES)
    eligible = classified.loc[~classified["key"].isin(excluded_keys)].copy()
    matched_population = eligible.loc[eligible["it_related"]]
    unmatched_population = eligible.loc[~eligible["it_related"]]

    matched = matched_population.sample(
        n=min(args.matched_size, len(matched_population)),
        random_state=args.random_state,
    ).copy()
    unmatched = unmatched_population.sample(
        n=min(args.unmatched_size, len(unmatched_population)),
        random_state=args.random_state + 1,
    ).copy()

    matched = prepare_review(matched, matched=True)
    unmatched = prepare_review(unmatched, matched=False)
    for path, frame in (
        (args.matched_output, matched),
        (args.unmatched_output, unmatched),
    ):
        path.parent.mkdir(parents=True, exist_ok=True)
        frame.to_csv(path, index=False)

    metadata = {
        "classification_input": str(args.input),
        "taxonomy_version": str(classified["taxonomy_version"].iloc[0]),
        "sampling_method": "simple random sampling without replacement",
        "random_state_matched": args.random_state,
        "random_state_unmatched": args.random_state + 1,
        "development_files_excluded": [str(path) for path in used_files],
        "unique_development_keys_excluded": len(excluded_keys),
        "eligible_matched_population": len(matched_population),
        "eligible_unmatched_population": len(unmatched_population),
        "matched_sample_size": len(matched),
        "unmatched_sample_size": len(unmatched),
    }
    args.metadata_output.parent.mkdir(parents=True, exist_ok=True)
    args.metadata_output.write_text(
        json.dumps(metadata, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )

    print(f"development keys excluded: {len(excluded_keys)}")
    print(f"matched holdout rows: {len(matched)}")
    print(f"matched output: {args.matched_output}")
    print(f"unmatched holdout rows: {len(unmatched)}")
    print(f"unmatched output: {args.unmatched_output}")
    print(f"metadata: {args.metadata_output}")


def load_development_keys(paths: tuple[Path, ...]) -> tuple[set[str], list[Path]]:
    """Load keys from existing review/development artifacts when available."""

    keys: set[str] = set()
    used_files: list[Path] = []
    for path in paths:
        if not path.exists():
            continue
        frame = pd.read_csv(path, usecols=["key"], dtype={"key": str})
        keys.update(frame["key"].dropna())
        used_files.append(path)
    return keys, used_files


def prepare_review(frame: pd.DataFrame, *, matched: bool) -> pd.DataFrame:
    """Select review fields and add blank adjudication columns."""

    common_columns = [
        "key",
        "project_name",
        "organization_name",
        "lg_code",
        "prefecture_name",
        "cft_issue_year",
        "cft_issue_date",
        "external_document_uri",
        "taxonomy_version",
        "it_related",
        "core_it_delivery",
        "digital_or_ai_adjacent",
        "matched_subgroups",
    ]
    review = frame[common_columns].copy()
    review["review_decision"] = ""
    if matched:
        review["incorrect_or_boundary_tags"] = ""
    else:
        review["suggested_it_tag"] = ""
    review["source_inspected"] = False
    review["review_notes"] = ""
    return review


if __name__ == "__main__":
    main()
