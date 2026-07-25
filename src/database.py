"""SQLite persistence for procurement notices."""

from __future__ import annotations

import sqlite3
from collections.abc import Iterable
from pathlib import Path

from src.models import ProcurementNotice

SCHEMA = """
CREATE TABLE IF NOT EXISTS notices (
    key TEXT PRIMARY KEY,
    project_name TEXT,
    organization_name TEXT,
    prefecture_name TEXT,
    cft_issue_date TEXT,
    external_document_uri TEXT,
    category TEXT,
    procedure_type TEXT,
    raw_xml TEXT,
    data_json TEXT NOT NULL
);
"""


def connect(path: str | Path) -> sqlite3.Connection:
    """Open a SQLite database and ensure the simple schema exists."""

    connection = sqlite3.connect(path)
    connection.execute(SCHEMA)
    connection.commit()
    return connection


def insert_notices(
    connection: sqlite3.Connection, notices: Iterable[ProcurementNotice]
) -> int:
    """Insert notices, ignoring duplicates by the KKJ ``Key`` field."""

    inserted = 0
    for notice in notices:
        cursor = connection.execute(
            """
            INSERT OR IGNORE INTO notices (
                key, project_name, organization_name, prefecture_name,
                cft_issue_date, external_document_uri, category, procedure_type,
                raw_xml, data_json
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                notice.key,
                notice.project_name,
                notice.organization_name,
                notice.prefecture_name,
                notice.cft_issue_date.isoformat() if notice.cft_issue_date else None,
                notice.external_document_uri,
                notice.category,
                notice.procedure_type,
                notice.raw_xml,
                notice.model_dump_json(),
            ),
        )
        inserted += cursor.rowcount
    connection.commit()
    return inserted
