"""Command-line entry point for jp-govtenders."""

from __future__ import annotations

import argparse
import logging
from pathlib import Path

from src.collector import CollectionResult, collect_once
from src.partitioned_collector import DEFAULT_LG_CODES, collect_service_history

CATEGORY_HELP = (
    "Documented KKJ Category: 1=物品/goods, 2=工事/construction, 3=役務/services."
)
REQUIRED_FILTER_HELP = (
    "KKJ requires at least one of --query, --project-name, --organization-name, "
    "or --lg-code."
)


def main() -> None:
    """Run the jp-govtenders command-line interface."""

    parser = argparse.ArgumentParser(description="Collect notices from the KKJ API.")
    subparsers = parser.add_subparsers(dest="command")

    collect_parser = subparsers.add_parser(
        "collect", help="Fetch KKJ notices and save them to SQLite."
    )
    _add_search_arguments(collect_parser)
    collect_parser.add_argument(
        "--count",
        type=int,
        default=100,
        help="Documented Count parameter. Max is 1000.",
    )
    collect_parser.add_argument(
        "--database",
        type=Path,
        required=True,
        help="SQLite database file to create/use.",
    )
    collect_parser.add_argument(
        "--print-json",
        action="store_true",
        help="Print full parsed JSON for debugging.",
    )

    count_parser = subparsers.add_parser(
        "count", help="Show KKJ search hit count without saving notices."
    )
    _add_search_arguments(count_parser)

    history_parser = subparsers.add_parser(
        "collect-services-history",
        help="Collect restartable, date-partitioned historical service notices.",
    )
    history_parser.add_argument(
        "--database",
        type=Path,
        required=True,
        help="SQLite database file to create/use.",
    )
    history_parser.add_argument("--start-year", type=int, default=2022)
    history_parser.add_argument("--end-year", type=int, default=2025)
    history_parser.add_argument(
        "--lg-code",
        dest="lg_codes",
        action="append",
        help=(
            "Prefecture code to collect. Repeat for multiple codes. "
            f"Defaults to {', '.join(DEFAULT_LG_CODES)}."
        ),
    )
    history_parser.add_argument(
        "--request-delay",
        type=float,
        default=0.2,
        help="Minimum seconds between API requests. Default: 0.2.",
    )

    args = parser.parse_args()
    logging.basicConfig(
        level=logging.INFO, format="%(levelname)s %(name)s: %(message)s"
    )

    if args.command == "collect":
        _require_documented_search_filter(parser, args)
        result = collect_once(
            query=args.query,
            project_name=args.project_name,
            organization_name=args.organization_name,
            count=args.count,
            database_path=args.database,
            lg_code=args.lg_code,
            category=args.category,
            cft_issue_date=args.cft_issue_date,
        )
        _print_collection_result(result, print_json=args.print_json)
        return

    if args.command == "count":
        _require_documented_search_filter(parser, args)
        result = collect_once(
            query=args.query,
            project_name=args.project_name,
            organization_name=args.organization_name,
            count=1,
            lg_code=args.lg_code,
            category=args.category,
            cft_issue_date=args.cft_issue_date,
        )
        print(f"search hits: {result.response.search_hits}")
        print("database: not saved")
        return

    if args.command == "collect-services-history":
        if args.end_year < args.start_year:
            history_parser.error("--end-year must be on or after --start-year")
        if args.request_delay < 0:
            history_parser.error("--request-delay must be non-negative")
        lg_codes = tuple(args.lg_codes) if args.lg_codes else DEFAULT_LG_CODES
        summary = collect_service_history(
            database_path=args.database,
            start_year=args.start_year,
            end_year=args.end_year,
            lg_codes=lg_codes,
            request_delay=args.request_delay,
        )
        print(f"API requests: {summary.requests}")
        print(f"periods completed: {summary.completed_periods}")
        print(f"periods skipped: {summary.skipped_periods}")
        print(f"periods split: {summary.split_periods}")
        print(f"periods failed: {summary.failed_periods}")
        print(f"notices expected: {summary.expected_notices}")
        print(f"notices returned: {summary.returned_notices}")
        print(f"new notices inserted: {summary.inserted_notices}")
        print(f"database: {args.database}")
        if summary.failed_periods:
            raise SystemExit(1)
        return

    parser.print_help()


def _add_search_arguments(parser: argparse.ArgumentParser) -> None:
    """Add documented KKJ search filters to a subcommand parser."""

    parser.add_argument("--query", help="Documented KKJ Query parameter, e.g. 官公需.")
    parser.add_argument("--project-name", help="Documented Project_Name filter.")
    parser.add_argument(
        "--organization-name", help="Documented Organization_Name filter."
    )
    parser.add_argument(
        "--lg-code", help="Documented LG_Code prefecture filter, e.g. 13 for Tokyo."
    )
    parser.add_argument("--category", type=int, choices=[1, 2, 3], help=CATEGORY_HELP)
    parser.add_argument(
        "--cft-issue-date",
        help="Documented CFT_Issue_Date period, e.g. 2026-07-01/2026-07-31.",
    )


def _require_documented_search_filter(
    parser: argparse.ArgumentParser, args: argparse.Namespace
) -> None:
    """Enforce the API guide's required search filter rule."""

    if not any([args.query, args.project_name, args.organization_name, args.lg_code]):
        parser.error(REQUIRED_FILTER_HELP)


def _print_collection_result(result: CollectionResult, *, print_json: bool) -> None:
    """Print a small summary by default, or full JSON when requested."""

    if print_json:
        print(result.response.model_dump_json(indent=2))
        return

    print(f"search hits: {result.response.search_hits}")
    print(f"notices returned: {len(result.response.notices)}")
    if result.inserted_count is not None:
        print(f"new notices inserted: {result.inserted_count}")
    if result.database_path is not None:
        print(f"database: {result.database_path}")


if __name__ == "__main__":
    main()
