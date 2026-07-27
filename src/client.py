"""Minimal HTTP client for the official KKJ search API."""

from __future__ import annotations

import logging
from typing import Any, Self

import httpx

LOGGER = logging.getLogger(__name__)


class KkjHttpError(RuntimeError):
    """Raised for transport errors or non-success HTTP responses."""


class KkjClient:
    """Small wrapper around ``httpx`` for KKJ API requests."""

    def __init__(
        self, base_url: str = "http://www.kkj.go.jp/api/", timeout: float = 30.0
    ) -> None:
        self.base_url = base_url
        self.timeout = timeout
        self._http_client: httpx.Client | None = None

    def __enter__(self) -> Self:
        """Open a reusable HTTP connection for a multi-request collection run."""

        self._http_client = httpx.Client(timeout=self.timeout)
        return self

    def __exit__(self, *args: object) -> None:
        """Close the reusable HTTP connection."""

        if self._http_client is not None:
            self._http_client.close()
            self._http_client = None

    def search(
        self,
        *,
        query: str | None = None,
        project_name: str | None = None,
        organization_name: str | None = None,
        count: int | None = None,
        lg_code: str | None = None,
        category: int | None = None,
        cft_issue_date: str | None = None,
    ) -> str:
        """Run a documented KKJ search and return raw XML.

        The API guide says at least one of Query, Project_Name,
        Organization_Name, or LG_Code is required.
        """

        params: dict[str, Any] = {}
        if query is not None:
            params["Query"] = query
        if project_name is not None:
            params["Project_Name"] = project_name
        if organization_name is not None:
            params["Organization_Name"] = organization_name
        if count is not None:
            params["Count"] = count
        if lg_code is not None:
            params["LG_Code"] = lg_code
        if category is not None:
            params["Category"] = category
        if cft_issue_date is not None:
            params["CFT_Issue_Date"] = cft_issue_date

        if not any(
            params.get(name)
            for name in ("Query", "Project_Name", "Organization_Name", "LG_Code")
        ):
            raise ValueError(
                "one of query, project_name, organization_name, or lg_code is required"
            )

        LOGGER.info("requesting KKJ API", extra={"params": params})
        try:
            if self._http_client is None:
                with httpx.Client(timeout=self.timeout) as client:
                    response = client.get(self.base_url, params=params)
            else:
                response = self._http_client.get(self.base_url, params=params)
            response.raise_for_status()
        except httpx.HTTPError as exc:
            raise KkjHttpError(f"KKJ API request failed: {exc}") from exc

        LOGGER.info(
            "received KKJ API response", extra={"status_code": response.status_code}
        )
        return response.text
