"""SQLite storage for templates, BOM formats, and drawing jobs."""

from __future__ import annotations

import json
import os
import sqlite3
from pathlib import Path


def data_dir() -> Path:
    path = Path(os.environ.get("DRAWINGS_DATA", "data"))
    if not path.is_absolute():
        path = Path(__file__).resolve().parent.parent / path
    path.mkdir(parents=True, exist_ok=True)
    (path / "uploads").mkdir(exist_ok=True)
    return path


def db_path() -> Path:
    return data_dir() / "drawings.sqlite"


def connect() -> sqlite3.Connection:
    conn = sqlite3.connect(db_path())
    conn.row_factory = sqlite3.Row
    return conn


def init_db() -> None:
    with connect() as conn:
        conn.executescript(
            """
            CREATE TABLE IF NOT EXISTS templates (
                id TEXT PRIMARY KEY,
                name TEXT NOT NULL,
                drawing_type TEXT NOT NULL,
                applies_to TEXT NOT NULL,
                sheet_width_in REAL NOT NULL,
                sheet_height_in REAL NOT NULL,
                sheet_label TEXT NOT NULL,
                body_json TEXT NOT NULL,
                updated_at TEXT NOT NULL
            );
            CREATE TABLE IF NOT EXISTS bom_formats (
                id TEXT PRIMARY KEY,
                name TEXT NOT NULL,
                is_default INTEGER NOT NULL DEFAULT 0,
                body_json TEXT NOT NULL,
                updated_at TEXT NOT NULL
            );
            CREATE TABLE IF NOT EXISTS jobs (
                id TEXT PRIMARY KEY,
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL,
                source_name TEXT,
                source_kind TEXT,
                example_id TEXT,
                template_id TEXT,
                bom_format_id TEXT,
                view_count INTEGER,
                selected_views_json TEXT,
                properties_json TEXT,
                model_json TEXT,
                bom_rows_json TEXT,
                warnings_json TEXT,
                status TEXT,
                sample INTEGER DEFAULT 0,
                sample_note TEXT,
                sop_json TEXT,
                snapshot_json TEXT
            );
            """
        )


def dumps(value) -> str:
    return json.dumps(value, ensure_ascii=False)


def loads(value, fallback):
    if not value:
        return fallback
    return json.loads(value)
