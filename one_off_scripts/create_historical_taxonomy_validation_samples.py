"""Create deterministic historical samples for taxonomy drift validation."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

import pandas as pd

DEFAULT_INPUT = Path("analysis_outputs/service_notices_classified_v1.csv")
DEFAULT_TAXONOMY = Path("reference_data/it_service_taxonomy_v1.json")
DEFAULT_UNMATCHED_OUTPUT = Path(
    "analysis_outputs/historical_unmatched_taxonomy_review_v1.csv"
)
DEFAULT_MATCHED_OUTPUT = Path(
    "analysis_outputs/historical_matched_taxonomy_review_v1.csv"
)
DEFAULT_SAMPLE_SIZE = 100
DEFAULT_RANDOM_STATE = 20260730


def main() -> None:
    """Write unmatched and subgroup-stratified matched review samples."""

    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input", type=Path, default=DEFAULT_INPUT)
    parser.add_argument("--taxonomy", type=Path, default=DEFAULT_TAXONOMY)
    parser.add_argument("--sample-size", type=int, default=DEFAULT_SAMPLE_SIZE)
    parser.add_argument("--random-state", type=int, default=DEFAULT_RANDOM_STATE)
    parser.add_argument(
        "--unmatched-output", type=Path, default=DEFAULT_UNMATCHED_OUTPUT
    )
    parser.add_argument("--matched-output", type=Path, default=DEFAULT_MATCHED_OUTPUT)
    args = parser.parse_args()
    if args.sample_size < 1:
        parser.error("--sample-size must be positive")

    taxonomy: dict[str, Any] = json.loads(
        args.taxonomy.read_text(encoding="utf-8")
    )
    classified = pd.read_csv(
        args.input,
        dtype={"key": str, "lg_code": str, "city_code": str},
        low_memory=False,
    )
    tag_columns = list(taxonomy["patterns"])

    unmatched = create_unmatched_sample(
        classified,
        sample_size=args.sample_size,
        random_state=args.random_state,
    )
    matched = create_matched_sample(
        classified,
        tag_columns=tag_columns,
        sample_size=args.sample_size,
        random_state=args.random_state,
    )

    for path, frame in (
        (args.unmatched_output, unmatched),
        (args.matched_output, matched),
    ):
        path.parent.mkdir(parents=True, exist_ok=True)
        frame.to_csv(path, index=False)

    print(f"unmatched review rows: {len(unmatched)}")
    print(f"unmatched output: {args.unmatched_output}")
    print(f"matched review rows: {len(matched)}")
    print(f"matched output: {args.matched_output}")


def create_unmatched_sample(
    classified: pd.DataFrame,
    *,
    sample_size: int,
    random_state: int,
) -> pd.DataFrame:
    """Sample unmatched titles while cycling across year/prefecture strata."""

    candidates = classified.loc[~classified["it_related"]].copy()
    sample = _balanced_sample(
        candidates,
        sample_size=min(sample_size, len(candidates)),
        random_state=random_state,
    )
    columns = _existing_columns(
        sample,
        [
            "key",
            "project_name",
            "organization_name",
            "lg_code",
            "prefecture_name",
            "cft_issue_year",
            "cft_issue_date",
            "external_document_uri",
        ],
    )
    review = sample[columns].copy()
    review["review_decision"] = ""
    review["suggested_it_tag"] = ""
    review["review_notes"] = ""
    return review


def create_matched_sample(
    classified: pd.DataFrame,
    *,
    tag_columns: list[str],
    sample_size: int,
    random_state: int,
) -> pd.DataFrame:
    """Sample unique matched notices across subgroups, years, and prefectures."""

    candidates = classified.loc[classified["it_related"]].copy()
    active_tags = [tag for tag in tag_columns if candidates[tag].any()]
    active_tags.sort(key=lambda tag: int(candidates[tag].sum()))
    base_quota, remainder = divmod(sample_size, len(active_tags))
    selected_frames: list[pd.DataFrame] = []
    selected_keys: set[str] = set()

    for index, tag in enumerate(active_tags):
        quota = base_quota + (1 if index < remainder else 0)
        tag_candidates = candidates.loc[
            candidates[tag] & ~candidates["key"].isin(selected_keys)
        ]
        selected = _balanced_sample(
            tag_candidates,
            sample_size=min(quota, len(tag_candidates)),
            random_state=random_state + index + 1,
        )
        selected = selected.copy()
        selected["sampling_subgroup"] = tag
        selected_frames.append(selected)
        selected_keys.update(selected["key"])

    sample = pd.concat(selected_frames, ignore_index=True)
    if len(sample) < sample_size:
        remaining = candidates.loc[~candidates["key"].isin(selected_keys)]
        fill = _balanced_sample(
            remaining,
            sample_size=min(sample_size - len(sample), len(remaining)),
            random_state=random_state + len(active_tags) + 1,
        ).copy()
        fill["sampling_subgroup"] = "general_fill"
        sample = pd.concat([sample, fill], ignore_index=True)

    columns = _existing_columns(
        sample,
        [
            "key",
            "project_name",
            "organization_name",
            "lg_code",
            "prefecture_name",
            "cft_issue_year",
            "cft_issue_date",
            "external_document_uri",
            "sampling_subgroup",
            "matched_subgroups",
            "core_it_delivery",
            "digital_or_ai_adjacent",
            *tag_columns,
        ],
    )
    review = sample[columns].copy()
    review["review_decision"] = ""
    review["incorrect_or_boundary_tags"] = ""
    review["review_notes"] = ""
    return review


def _balanced_sample(
    frame: pd.DataFrame,
    *,
    sample_size: int,
    random_state: int,
) -> pd.DataFrame:
    """Deterministically cycle through year/prefecture groups before repeating."""

    if sample_size == 0:
        return frame.head(0).copy()
    shuffled = frame.sample(frac=1, random_state=random_state).copy()
    shuffled["_stratum_rank"] = shuffled.groupby(
        ["cft_issue_year", "lg_code"], dropna=False
    ).cumcount()
    sample = shuffled.sort_values("_stratum_rank", kind="stable").head(sample_size)
    return sample.drop(columns=["_stratum_rank"])


def _existing_columns(frame: pd.DataFrame, columns: list[str]) -> list[str]:
    """Return requested columns that exist, preserving order and uniqueness."""

    return list(dict.fromkeys(column for column in columns if column in frame))


if __name__ == "__main__":
    main()
