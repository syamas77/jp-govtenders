"""High-level collection workflow for KKJ notices."""

from __future__ import annotations

import logging
from dataclasses import dataclass
from pathlib import Path

from src.client import KkjClient
from src.database import connect, insert_notices
from src.models import SearchResponse
from src.parser import parse_search_response

LOGGER = logging.getLogger(__name__)


@dataclass(frozen=True)
class CollectionResult:
    """Result summary for one KKJ collection run."""

    response: SearchResponse
    inserted_count: int | None
    database_path: Path | None


def collect_once(
    *,
    query: str | None = None,
    project_name: str | None = None,
    organization_name: str | None = None,
    count: int = 1,
    database_path: Path | None = None,
    lg_code: str | None = None,
    category: int | None = None,
    cft_issue_date: str | None = None,
) -> CollectionResult:
    """Fetch, parse, and optionally store one KKJ search response.

    The KKJ guide does not document pagination/offset. This intentionally only
    performs one request with documented filters.
    """

    client = KkjClient()
    xml_text = client.search(
        query=query,
        project_name=project_name,
        organization_name=organization_name,
        count=count,
        lg_code=lg_code,
        category=category,
        cft_issue_date=cft_issue_date,
    )
    response = parse_search_response(xml_text)

    inserted_count: int | None = None
    if database_path is not None:
        with connect(database_path) as connection:
            inserted_count = insert_notices(connection, response.notices)
        LOGGER.info(
            "stored notices",
            extra={"inserted": inserted_count, "database_path": str(database_path)},
        )

    return CollectionResult(
        response=response,
        inserted_count=inserted_count,
        database_path=database_path,
    )
