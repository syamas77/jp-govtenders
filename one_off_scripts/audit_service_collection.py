"""Audit historical service collection by year and prefecture."""

from __future__ import annotations

import argparse
import json
import sqlite3
from contextlib import closing
from pathlib import Path

import pandas as pd

DEFAULT_DATABASE = Path("service_history.sqlite")
DEFAULT_ANNUAL_COUNTS = Path("one_off_scripts/annual_counts.csv")
DEFAULT_OUTPUT = Path("analysis_outputs/service_collection_completeness_audit.csv")


def main() -> None:
    """Compare collection-period, stored-notice, and annual API counts."""

    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--database", type=Path, default=DEFAULT_DATABASE)
    parser.add_argument("--annual-counts", type=Path, default=DEFAULT_ANNUAL_COUNTS)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    args = parser.parse_args()

    audit = build_audit(args.database, args.annual_counts)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    audit.to_csv(args.output, index=False)

    print(f"audit rows: {len(audit)}")
    print(f"complete rows: {int(audit['is_complete'].sum())}")
    print(f"incomplete rows: {int((~audit['is_complete']).sum())}")
    print(f"period search hits: {int(audit['period_search_hits'].sum())}")
    print(f"stored notices: {int(audit['stored_notices'].sum())}")
    print(f"output: {args.output}")
    if not audit["is_complete"].all():
        raise SystemExit(1)


def build_audit(database_path: Path, annual_counts_path: Path) -> pd.DataFrame:
    """Return one completeness row per year and prefecture."""

    annual = pd.read_csv(annual_counts_path, dtype={"lg_code": str})
    annual = annual.loc[annual["category_code"].eq(3)].copy()
    annual = annual[
        ["year", "lg_code", "prefecture_ja", "prefecture_en", "search_hits"]
    ].rename(columns={"search_hits": "annual_search_hits"})

    with closing(sqlite3.connect(database_path)) as connection:
        periods = pd.read_sql_query(
            "SELECT * FROM collection_periods WHERE category = 3", connection
        )
        data_rows = connection.execute("SELECT data_json FROM notices").fetchall()

    periods["year"] = periods["period_start"].str[:4].astype(int)
    completed = periods.loc[periods["status"].eq("completed")]
    period_totals = completed.groupby(["year", "lg_code"], as_index=False).agg(
        completed_periods=("status", "size"),
        period_search_hits=("search_hits", "sum"),
        period_returned=("returned_count", "sum"),
    )
    status_counts = (
        periods.groupby(["year", "lg_code", "status"])
        .size()
        .unstack(fill_value=0)
        .reset_index()
        .rename_axis(columns=None)
    )
    for status in ("failed", "split"):
        if status not in status_counts:
            status_counts[status] = 0
    status_counts = status_counts.rename(
        columns={"failed": "failed_periods", "split": "split_periods"}
    )[["year", "lg_code", "failed_periods", "split_periods"]]

    notice_records = [json.loads(row[0]) for row in data_rows]
    notices = pd.DataFrame.from_records(notice_records)
    notices["year"] = pd.to_datetime(
        notices["cft_issue_date"], errors="coerce", utc=True
    ).dt.year.astype("Int64")
    stored_totals = (
        notices.groupby(["year", "lg_code"], as_index=False)
        .size()
        .rename(columns={"size": "stored_notices"})
    )

    audit = annual.merge(period_totals, on=["year", "lg_code"], how="left")
    audit = audit.merge(status_counts, on=["year", "lg_code"], how="left")
    audit = audit.merge(stored_totals, on=["year", "lg_code"], how="left")
    numeric_columns = [
        "completed_periods",
        "period_search_hits",
        "period_returned",
        "failed_periods",
        "split_periods",
        "stored_notices",
    ]
    audit[numeric_columns] = audit[numeric_columns].fillna(0).astype(int)
    audit["period_minus_annual"] = (
        audit["period_search_hits"] - audit["annual_search_hits"]
    )
    audit["returned_minus_period"] = (
        audit["period_returned"] - audit["period_search_hits"]
    )
    audit["stored_minus_period"] = (
        audit["stored_notices"] - audit["period_search_hits"]
    )
    audit["is_complete"] = (
        audit["period_minus_annual"].eq(0)
        & audit["returned_minus_period"].eq(0)
        & audit["stored_minus_period"].eq(0)
        & audit["failed_periods"].eq(0)
    )
    return audit.sort_values(["year", "lg_code"]).reset_index(drop=True)


if __name__ == "__main__":
    main()
