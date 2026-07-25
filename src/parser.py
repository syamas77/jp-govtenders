"""XML parser for KKJ API responses."""

from __future__ import annotations

import xml.etree.ElementTree as ET
from typing import Any

from pydantic import ValidationError

from src.models import Attachment, ProcurementNotice, SearchResponse


class KkjApiError(RuntimeError):
    """Raised when the KKJ API returns an XML <Error> response."""


def parse_search_response(xml_text: str) -> SearchResponse:
    """Parse a KKJ XML response into Pydantic models.

    Unknown XML tags are ignored. Missing optional tags become ``None``.
    """

    root = ET.fromstring(xml_text)
    error = _text(root.find("Error"))
    if error:
        raise KkjApiError(error)

    search_results = root.find("SearchResults")
    notices: list[ProcurementNotice] = []
    if search_results is not None:
        for element in search_results.findall("SearchResult"):
            try:
                notices.append(_parse_notice(element))
            except ValidationError as exc:
                # Keep the collector resilient: one malformed notice should not
                # make the whole response unusable. The raw XML is logged by the
                # caller if needed.
                raise ValueError(f"failed to parse SearchResult: {exc}") from exc

    return SearchResponse(
        version=_text(root.find("Version")),
        search_hits=_int_or_none(_text(search_results.find("SearchHits")))
        if search_results is not None
        else None,
        notices=notices,
    )


def _parse_notice(element: ET.Element) -> ProcurementNotice:
    """Parse one ``SearchResult`` element."""

    data: dict[str, Any] = {
        "result_id": _int_or_none(_child_text(element, "ResultId")),
        "key": _child_text(element, "Key") or "",
        "external_document_uri": _child_text(element, "ExternalDocumentURI"),
        "project_name": _child_text(element, "ProjectName"),
        "date": _child_text(element, "Date"),
        "file_type": _child_text(element, "FileType"),
        "file_size": _int_or_none(_child_text(element, "FileSize")),
        "lg_code": _child_text(element, "LgCode"),
        "prefecture_name": _child_text(element, "PrefectureName"),
        "city_code": _child_text(element, "CityCode"),
        "city_name": _child_text(element, "CityName"),
        "organization_name": _child_text(element, "OrganizationName"),
        "certification": _child_text(element, "Certification"),
        "cft_issue_date": _child_text(element, "CftIssueDate"),
        "period_end_time": _child_text(element, "PeriodEndTime"),
        "category": _child_text(element, "Category"),
        "procedure_type": _child_text(element, "ProcedureType"),
        "location": _child_text(element, "Location"),
        "tender_submission_deadline": _child_text(element, "TenderSubmissionDeadline"),
        "opening_tenders_event": _child_text(element, "OpeningTendersEvent"),
        "item_code": _child_text(element, "ItemCode"),
        "project_description": _child_text(element, "ProjectDescription"),
        "attachments": _parse_attachments(element),
        "raw_xml": ET.tostring(element, encoding="unicode"),
    }
    return ProcurementNotice.model_validate(data)


def _parse_attachments(element: ET.Element) -> list[Attachment]:
    """Parse optional attachment elements."""

    attachments = element.find("Attachments")
    if attachments is None:
        return []
    return [
        Attachment(name=_child_text(item, "Name"), uri=_child_text(item, "Uri"))
        for item in attachments.findall("Attachment")
    ]


def _child_text(element: ET.Element, tag: str) -> str | None:
    """Return stripped text for a child tag, or ``None``."""

    return _text(element.find(tag))


def _text(element: ET.Element | None) -> str | None:
    """Return stripped element text, preserving absent/empty values as ``None``."""

    if element is None or element.text is None:
        return None
    value = element.text.strip()
    return value or None


def _int_or_none(value: str | None) -> int | None:
    """Convert an integer field, returning ``None`` for missing values."""

    if value is None:
        return None
    return int(value)
