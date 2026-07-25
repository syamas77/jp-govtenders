"""Pydantic models for KKJ procurement notices."""

from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field


class Attachment(BaseModel):
    """A single attachment referenced by a procurement notice."""

    model_config = ConfigDict(extra="ignore")

    name: str | None = None
    uri: str | None = None


class ProcurementNotice(BaseModel):
    """A procurement notice returned by the KKJ API.

    Most fields are optional because the API guide marks many XML tags as
    optional and says tag order is not stable.
    """

    model_config = ConfigDict(extra="ignore")

    result_id: int | None = None
    key: str
    external_document_uri: str | None = None
    project_name: str | None = None
    date: datetime | None = None
    file_type: str | None = None
    file_size: int | None = None
    lg_code: str | None = None
    prefecture_name: str | None = None
    city_code: str | None = None
    city_name: str | None = None
    organization_name: str | None = None
    certification: str | None = None
    cft_issue_date: datetime | None = None
    period_end_time: datetime | None = None
    category: str | None = None
    procedure_type: str | None = None
    location: str | None = None
    tender_submission_deadline: datetime | None = None
    opening_tenders_event: datetime | None = None
    item_code: str | None = None
    project_description: str | None = None
    attachments: list[Attachment] = Field(default_factory=list)
    raw_xml: str | None = None


class SearchResponse(BaseModel):
    """Parsed KKJ search response."""

    model_config = ConfigDict(extra="ignore")

    version: str | None = None
    search_hits: int | None = None
    notices: list[ProcurementNotice] = Field(default_factory=list)
