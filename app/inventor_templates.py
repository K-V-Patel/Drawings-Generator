"""Inventor 2025 drawing templates.

The shop keeps its .idw and .dwg borders in the English template folder.
This machine often cannot open that Windows path, so the folder is scanned
when it is reachable and a catalog from tools/ExportTemplates.vb can be
imported when it is not.
"""

from __future__ import annotations

import io
import json
import os
import re
import zipfile
from pathlib import Path

from app.db import connect, dumps, loads
from app.seed import BEND_COLUMNS, COMPANY

SHOP_TEMPLATE_DIR = r"C:\Users\Public\Documents\Autodesk\Inventor 2025\Templates\en-US"
CATALOG_SCHEMA = "drawgen-templates/1"
DRAWING_EXTENSIONS = {".idw", ".dwg"}

ANSI = {
    "A": (11.0, 8.5),
    "B": (17.0, 11.0),
    "C": (22.0, 17.0),
    "D": (34.0, 22.0),
    "E": (44.0, 34.0),
}

PART_VIEWS = [
    {"role": "flat", "label": "FLAT PATTERN"},
    {"role": "front", "label": "FRONT"},
    {"role": "side", "label": "SIDE"},
    {"role": "iso", "label": "ISOMETRIC"},
]
WELD_VIEWS = [
    {"role": "side", "label": "SIDE"},
    {"role": "end", "label": "END"},
    {"role": "detail", "label": "DETAIL A"},
    {"role": "iso", "label": "ISOMETRIC"},
]
ASSEMBLY_VIEWS = [
    {"role": "side", "label": "SIDE"},
    {"role": "front", "label": "FRONT"},
    {"role": "end", "label": "END"},
    {"role": "iso", "label": "ISOMETRIC"},
]
SIGNOFF_VIEWS = [
    {"role": "side", "label": "SIDE ELEVATION"},
    {"role": "front", "label": "FRONT"},
    {"role": "section", "label": "SECTION A-A"},
    {"role": "inlet", "label": "INLET FLANGE"},
    {"role": "discharge", "label": "DISCHARGE FLANGE"},
]


def shop_template_dir() -> str:
    return SHOP_TEMPLATE_DIR


def read_dir() -> Path | None:
    raw = os.environ.get("DRAWINGS_TEMPLATE_DIR") or SHOP_TEMPLATE_DIR
    path = Path(raw)
    if path.is_dir():
        return path
    return None


def source_status() -> dict:
    folder = read_dir()
    drawings: list[str] = []
    other = 0
    if folder is not None:
        found = _walk(folder)
        drawings = [item["relativePath"] for item in found if item["kind"] == "drawing"]
        other = sum(1 for item in found if item["kind"] == "other")
    return {
        "path": SHOP_TEMPLATE_DIR,
        "reachable": folder is not None,
        "drawings": drawings,
        "otherCount": other,
    }


def sync_if_reachable() -> dict | None:
    folder = read_dir()
    if folder is None:
        return None
    return import_folder(folder)


def import_upload(filename: str, data: bytes) -> dict:
    if len(data) > 40 * 1024 * 1024:
        raise ValueError("File is larger than 40 MB.")
    lower = (filename or "").lower()
    if lower.endswith(".json"):
        return import_catalog(_load_json(data))
    if lower.endswith(".zip"):
        return import_zip(data)
    if Path(lower).suffix in DRAWING_EXTENSIONS:
        return import_entries(
            [{"fileName": Path(filename).name, "relativePath": Path(filename).name}],
            SHOP_TEMPLATE_DIR,
            from_catalog=False,
        )
    raise ValueError("Drop a template list (.json), a zip of the template folder, or an .idw / .dwg file.")


def import_uploads(files: list[tuple[str, bytes]]) -> dict:
    if not files:
        raise ValueError("Drop a template list (.json), a zip of the template folder, or an .idw / .dwg file.")
    if len(files) == 1:
        return import_upload(files[0][0], files[0][1])
    entries = []
    for name, data in files:
        if Path(name).suffix.lower() not in DRAWING_EXTENSIONS:
            raise ValueError("Drop drawing templates (.idw or .dwg), or a single .json or .zip.")
        if len(data) > 40 * 1024 * 1024:
            raise ValueError("File is larger than 40 MB.")
        entries.append({"fileName": Path(name).name, "relativePath": Path(name).name})
    return import_entries(entries, SHOP_TEMPLATE_DIR, from_catalog=False)


def import_catalog(payload: dict) -> dict:
    if not isinstance(payload, dict) or payload.get("schema") != CATALOG_SCHEMA:
        raise ValueError("That file is not a drawing-template list from Inventor.")
    folder = str(payload.get("folder") or SHOP_TEMPLATE_DIR)
    templates = payload.get("templates")
    if not isinstance(templates, list):
        raise ValueError("The template list has no templates.")
    return import_entries(templates, folder, from_catalog=True)


def import_zip(data: bytes) -> dict:
    try:
        archive = zipfile.ZipFile(io.BytesIO(data))
    except zipfile.BadZipFile as exc:
        raise ValueError("That zip could not be read.") from exc
    with archive:
        names = [name for name in archive.namelist() if name and not name.endswith("/")]
        if len(names) > 500:
            raise ValueError("That zip has more than 500 files.")
        for name in names:
            if not name.lower().endswith(".json"):
                continue
            try:
                payload = _load_json(archive.read(name))
            except (ValueError, UnicodeError, zipfile.BadZipFile):
                continue
            if isinstance(payload, dict) and payload.get("schema") == CATALOG_SCHEMA:
                return import_catalog(payload)
        entries = []
        for name in names:
            if Path(name).suffix.lower() not in DRAWING_EXTENSIONS:
                continue
            if "__MACOSX" in name:
                continue
            relative = _zip_relative(name)
            if not relative:
                continue
            entries.append({"fileName": Path(relative.replace("\\", "/")).name, "relativePath": relative})
    if not entries:
        raise ValueError("That zip has no .idw or .dwg drawing templates.")
    return import_entries(entries, SHOP_TEMPLATE_DIR, from_catalog=False)


def import_folder(folder: Path) -> dict:
    found = [item for item in _walk(folder) if item["kind"] == "drawing"]
    entries = [
        {"fileName": item["fileName"], "relativePath": item["relativePath"]}
        for item in found
    ]
    if not entries:
        raise ValueError(f"No .idw or .dwg files are in {folder}.")
    return import_entries(entries, SHOP_TEMPLATE_DIR, from_catalog=False)


def import_entries(entries: list, folder: str, from_catalog: bool) -> dict:
    imported = 0
    updated = 0
    skipped: list[str] = []
    from datetime import datetime, timezone

    timestamp = datetime.now(timezone.utc).isoformat()
    with connect() as conn:
        for raw in entries:
            if not isinstance(raw, dict):
                continue
            if raw.get("error"):
                skipped.append(str(raw.get("relativePath") or raw.get("fileName") or raw.get("error")))
                continue
            relative = _relative(raw)
            if not relative:
                continue
            file_name = str(raw.get("fileName") or Path(relative.replace("\\", "/")).name)
            template_id = _template_id(relative)
            width, height, label, size_read = _sheet_size(raw, from_catalog)
            source = {
                "folder": folder,
                "fileName": file_name,
                "relativePath": relative,
                "titleBlock": str(raw.get("titleBlock") or ""),
                "border": str(raw.get("border") or ""),
                "sheetSizeRead": size_read,
            }
            existing = conn.execute("SELECT * FROM templates WHERE id = ?", (template_id,)).fetchone()
            if existing:
                body = loads(existing["body_json"], {})
                body["source"] = source
                sheet_width = float(existing["sheet_width_in"])
                sheet_height = float(existing["sheet_height_in"])
                sheet_label = existing["sheet_label"]
                if size_read:
                    sheet_width, sheet_height, sheet_label = width, height, label
                _save_row(
                    conn, template_id, existing["name"], existing["drawing_type"], existing["applies_to"],
                    sheet_width, sheet_height, sheet_label, body, timestamp,
                )
                updated += 1
                continue
            drawing_type, applies_to = _classify(relative)
            views = _views_for(drawing_type)
            table = _table_for(drawing_type)
            company = _company_for(relative, source["titleBlock"])
            body = {
                "company": company,
                "views": views,
                "default_views": [view["role"] for view in views],
                "table": table,
                "signoff_fields": [],
                "sop_notes": _notes(relative, folder, applies_to, size_read),
                "source": source,
            }
            _save_row(
                conn, template_id, _display_name(relative), drawing_type, applies_to,
                width, height, label, body, timestamp,
            )
            imported += 1
    return {"imported": imported, "updated": updated, "skipped": skipped}


def _save_row(conn, template_id, name, drawing_type, applies_to, width, height, label, body, timestamp) -> None:
    conn.execute(
        """
        INSERT INTO templates
        (id, name, drawing_type, applies_to, sheet_width_in, sheet_height_in, sheet_label, body_json, updated_at)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
        ON CONFLICT(id) DO UPDATE SET
            name = excluded.name,
            drawing_type = excluded.drawing_type,
            applies_to = excluded.applies_to,
            sheet_width_in = excluded.sheet_width_in,
            sheet_height_in = excluded.sheet_height_in,
            sheet_label = excluded.sheet_label,
            body_json = excluded.body_json,
            updated_at = excluded.updated_at
        """,
        (template_id, name, drawing_type, applies_to, width, height, label, dumps(body), timestamp),
    )


def _walk(folder: Path) -> list[dict]:
    found = []
    for path in sorted(folder.rglob("*")):
        if not path.is_file():
            continue
        if path.name.startswith("."):
            continue
        relative = path.relative_to(folder).as_posix().replace("/", "\\")
        suffix = path.suffix.lower()
        kind = "drawing" if suffix in DRAWING_EXTENSIONS else "other"
        if kind == "other" and suffix not in {".ipt", ".iam", ".ipn"}:
            continue
        found.append({"relativePath": relative, "fileName": path.name, "kind": kind})
    return found


def _load_json(data: bytes) -> dict:
    try:
        payload = json.loads(data.decode("utf-8-sig"))
    except (UnicodeError, json.JSONDecodeError) as exc:
        raise ValueError("That JSON could not be read.") from exc
    if not isinstance(payload, dict):
        raise ValueError("That JSON could not be read.")
    return payload


def _zip_relative(name: str) -> str:
    parts = [part for part in name.replace("\\", "/").split("/") if part not in {"", ".", ".."}]
    parts = [part for part in parts if part != "__MACOSX" and not part.startswith("._")]
    lower = [part.lower() for part in parts]
    if "en-us" in lower:
        parts = parts[lower.index("en-us") + 1 :]
    return "\\".join(parts)


def _relative(raw: dict) -> str:
    relative = str(raw.get("relativePath") or raw.get("fileName") or "").strip()
    relative = relative.replace("/", "\\")
    while relative.startswith(".\\"):
        relative = relative[2:]
    return relative.strip("\\")


def _template_id(relative: str) -> str:
    slug = relative.lower()
    slug = re.sub(r"[^a-z0-9]+", "-", slug).strip("-")
    return "inv-" + slug[:80]


def _display_name(relative: str) -> str:
    parts = [part for part in relative.split("\\") if part]
    if len(parts) <= 1:
        return parts[0] if parts else relative
    return f"{parts[-2]} / {parts[-1]}"


def _classify(relative: str) -> tuple[str, str]:
    blob = relative.lower().replace("\\", " ").replace("-", " ").replace("_", " ")
    if "signoff" in blob or "sign off" in blob:
        return "signoff", "iam"
    if "weld" in blob:
        return "weldment", "iam"
    if "assembl" in blob:
        return "assembly", "iam"
    if "part" in blob or "sheet metal" in blob or "sheetmetal" in blob:
        return "part", "ipt"
    return "part", "both"


def _views_for(drawing_type: str) -> list[dict]:
    if drawing_type == "weldment":
        return [dict(view) for view in WELD_VIEWS]
    if drawing_type == "assembly":
        return [dict(view) for view in ASSEMBLY_VIEWS]
    if drawing_type == "signoff":
        return [dict(view) for view in SIGNOFF_VIEWS]
    return [dict(view) for view in PART_VIEWS]


def _table_for(drawing_type: str) -> dict:
    if drawing_type == "part":
        return {"kind": "bend", "title": "TABLE", "columns": [dict(column) for column in BEND_COLUMNS]}
    if drawing_type == "signoff":
        return {"kind": "signoff"}
    if drawing_type in {"weldment", "assembly"}:
        return {"kind": "parts", "title": "Parts List"}
    return {"kind": "none"}


def _company_for(relative: str, title_block: str) -> dict:
    return dict(COMPANY)


def _sheet_size(raw: dict, from_catalog: bool) -> tuple[float, float, str, bool]:
    width = _number(raw.get("sheetWidthIn"))
    height = _number(raw.get("sheetHeightIn"))
    if from_catalog and width and height and width >= 8 and height >= 6:
        label = str(raw.get("sheetLabel") or "").upper() or _sheet_label(width, height)
        return width, height, label, True
    return 17.0, 11.0, "B", False


def _number(value) -> float:
    try:
        return float(value)
    except (TypeError, ValueError):
        return 0.0


def _sheet_label(width: float, height: float) -> str:
    for label, (wide, high) in ANSI.items():
        if (abs(width - wide) < 0.2 and abs(height - high) < 0.2) or (
            abs(width - high) < 0.2 and abs(height - wide) < 0.2
        ):
            return label
    return "CUSTOM"


def _notes(relative: str, folder: str, applies_to: str, size_read: bool) -> str:
    note = f"Inventor drawing template {relative} from {folder}."
    if applies_to == "both":
        note += " This border is used for parts and assemblies. Set the drawing type when the sheet is a weldment, assembly, or signoff."
    if not size_read:
        note += " Sheet size was not read from the file. Run ExportTemplates.vb in Inventor, or set the size here."
    return note
