"""The three drawing templates: Standard.idw, Standard.dwg, and Sign off.

Company names from sample jobs are not stored here. Edits to these three
templates are kept. Any other template is removed on startup.
"""

from __future__ import annotations

from datetime import datetime, timezone

from app.db import connect, dumps, loads
from app.parser import acceptable_property, sanitize_properties

BEND_COLUMNS = [
    {"key": "id", "heading": "BEND ID", "width": 0.18},
    {"key": "direction", "heading": "BEND DIRECTION", "width": 0.32},
    {"key": "angle", "heading": "BEND ANGLE", "width": 0.25},
    {"key": "radius", "heading": "BEND RADIUS", "width": 0.25},
]

COMPANY = {
    "name": "",
    "sub": "",
    "mark": "none",
    "productSeries": "",
    "standard": "THIS DRAWING CONFORMS TO ASME Y14.5M-1994 FOR DOCUMENTATION PRACTICES",
    "proprietary": "",
    "tolerances": [],
}

STANDARD_VIEWS = [
    {"role": "front", "label": "FRONT"},
    {"role": "side", "label": "SIDE"},
    {"role": "top", "label": "TOP"},
    {"role": "end", "label": "END"},
    {"role": "iso", "label": "ISOMETRIC"},
    {"role": "flat", "label": "FLAT PATTERN"},
    {"role": "bottom", "label": "BOTTOM"},
    {"role": "back", "label": "BACK"},
]

SIGNOFF_VIEWS = [
    {"role": "side", "label": "SIDE ELEVATION"},
    {"role": "front", "label": "FRONT"},
    {"role": "section", "label": "SECTION A-A"},
    {"role": "inlet", "label": "INLET FLANGE"},
    {"role": "discharge", "label": "DISCHARGE FLANGE"},
]

STANDARD_NOTES = (
    "Standard drawing. A part uses front, side, and isometric, plus a flat view when it has bends. "
    "Dimension overall height and width, and thickness where it is easiest to see. "
    "Do not dimension laser cut-outs that are also in the DXF. "
    "An assembly uses as many views as production needs, with overall height, width, and depth, "
    "and a parts list with balloons in the top left. "
    "A weldment adds weld symbols on the clearest view."
)

SIGNOFF_NOTES = (
    "Sign off sheet. Side elevation with overall length and height, discharge height, and each section length. "
    "Front view, an end cross-section of the ordered height and width, and face views of the inlet and discharge "
    "with flange size and the opening. Customer, order number, quote number, signature, and date sit in the lower left."
)

OFFICIAL_IDS = ("standard-idw", "standard-dwg", "signoff")


def _template(template_id, name, drawing_type, applies_to, width, height, label, views, table, notes, fields=None, default_views=None):
    return {
        "id": template_id,
        "name": name,
        "drawing_type": drawing_type,
        "applies_to": applies_to,
        "sheet_width_in": width,
        "sheet_height_in": height,
        "sheet_label": label,
        "body": {
            "company": dict(COMPANY),
            "views": views,
            "default_views": default_views or [view["role"] for view in views],
            "table": table,
            "signoff_fields": fields or [],
            "sop_notes": notes,
        },
    }


TEMPLATES = [
    _template(
        "standard-idw", "Standard.idw", "standard", "both", 17, 11, "B", STANDARD_VIEWS,
        {"kind": "auto"},
        STANDARD_NOTES,
        default_views=["front", "side", "iso"],
    ),
    _template(
        "standard-dwg", "Standard.dwg", "standard", "both", 17, 11, "B", STANDARD_VIEWS,
        {"kind": "auto"},
        STANDARD_NOTES,
        default_views=["front", "side", "iso"],
    ),
    _template(
        "signoff", "Sign off", "signoff", "both", 34, 22, "D", SIGNOFF_VIEWS,
        {"kind": "signoff"},
        SIGNOFF_NOTES,
        default_views=["side", "front", "section", "inlet", "discharge"],
    ),
]

BOM_FORMATS = [
    {
        "id": "parts-list",
        "name": "Parts list",
        "is_default": 1,
        "body": {
            "title": "Parts List",
            "placement": "top-left",
            "show_balloons": True,
            "columns": [
                {"key": "item", "heading": "ITEM", "width": 0.12},
                {"key": "partNumber", "heading": "PART NUMBER", "width": 0.24},
                {"key": "description", "heading": "DESCRIPTION", "width": 0.48},
                {"key": "qty", "heading": "ITEM QTY", "width": 0.16},
            ],
        },
    }
]


def seed_if_empty() -> None:
    install_shop_templates()


def install_shop_templates() -> None:
    timestamp = datetime.now(timezone.utc).isoformat()
    with connect() as conn:
        _install_formats(conn, timestamp)
        conn.execute(
            f"DELETE FROM templates WHERE id NOT IN ({','.join('?' for _ in OFFICIAL_IDS)})",
            OFFICIAL_IDS,
        )
        have = {row["id"] for row in conn.execute("SELECT id FROM templates")}
        for template in TEMPLATES:
            if template["id"] in have:
                _merge_views(conn, template, timestamp)
                continue
            conn.execute(
                """
                INSERT INTO templates
                (id, name, drawing_type, applies_to, sheet_width_in, sheet_height_in, sheet_label, body_json, updated_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    template["id"], template["name"], template["drawing_type"], template["applies_to"],
                    template["sheet_width_in"], template["sheet_height_in"], template["sheet_label"],
                    dumps(template["body"]), timestamp,
                ),
            )
        conn.execute(
            """
            UPDATE jobs SET template_id = 'signoff'
            WHERE template_id NOT IN ('standard-idw', 'standard-dwg', 'signoff')
              AND template_id LIKE '%signoff%'
            """
        )
        conn.execute(
            """
            UPDATE jobs SET template_id = 'standard-idw'
            WHERE template_id NOT IN ('standard-idw', 'standard-dwg', 'signoff')
            """
        )
        conn.execute("DELETE FROM jobs WHERE sample = 1")
        _retire_false_sheets(conn, timestamp)


def _merge_views(conn, template: dict, timestamp: str) -> None:
    """Add view roles that the shop list gained. Stored labels stay as they are."""
    row = conn.execute("SELECT body_json FROM templates WHERE id = ?", (template["id"],)).fetchone()
    if not row:
        return
    body = loads(row["body_json"], {})
    if not isinstance(body, dict):
        return
    views = list(body.get("views") or [])
    have = {view.get("role") for view in views if isinstance(view, dict)}
    added = False
    for view in template["body"].get("views") or []:
        if view.get("role") not in have:
            views.append(dict(view))
            added = True
    if not added:
        return
    body["views"] = views
    conn.execute(
        "UPDATE templates SET body_json = ?, updated_at = ? WHERE id = ?",
        (dumps(body), timestamp, template["id"]),
    )


def _install_formats(conn, timestamp: str) -> None:
    old = conn.execute("SELECT id FROM bom_formats WHERE id = 'norstar-parts-list'").fetchone()
    current = conn.execute("SELECT id FROM bom_formats WHERE id = 'parts-list'").fetchone()
    if old and not current:
        conn.execute(
            "UPDATE bom_formats SET id = 'parts-list', name = 'Parts list' WHERE id = 'norstar-parts-list'"
        )
        conn.execute("UPDATE jobs SET bom_format_id = 'parts-list' WHERE bom_format_id = 'norstar-parts-list'")
    elif old and current:
        conn.execute("DELETE FROM bom_formats WHERE id = 'norstar-parts-list'")
        conn.execute("UPDATE jobs SET bom_format_id = 'parts-list' WHERE bom_format_id = 'norstar-parts-list'")
    elif not current:
        fmt = BOM_FORMATS[0]
        conn.execute(
            "INSERT INTO bom_formats (id, name, is_default, body_json, updated_at) VALUES (?, ?, ?, ?, ?)",
            (fmt["id"], fmt["name"], fmt["is_default"], dumps(fmt["body"]), timestamp),
        )
    for row in conn.execute("SELECT id, name FROM bom_formats"):
        lowered = (row["name"] or "").lower()
        if "norstar" in lowered or "meridian" in lowered:
            conn.execute("UPDATE bom_formats SET name = 'Parts list' WHERE id = ?", (row["id"],))


def _branded(text: str) -> bool:
    lowered = (text or "").lower()
    return "norstar" in lowered or "meridian" in lowered


def _retire_false_sheets(conn, timestamp: str) -> None:
    rows = conn.execute("SELECT id, source_name, properties_json, snapshot_json FROM jobs").fetchall()
    for row in rows:
        props = loads(row["properties_json"], {})
        cleaned = sanitize_properties(props, row["source_name"] or "")
        snapshot = loads(row["snapshot_json"], None)
        drop_snapshot = False
        if isinstance(snapshot, dict):
            company = ((snapshot.get("template") or {}).get("company") or {})
            blob = " ".join(str(company.get(key) or "") for key in ("name", "sub", "proprietary", "productSeries"))
            dirty = any(
                value not in (None, "") and not acceptable_property(value)
                for value in (props or {}).values()
                if isinstance(value, str)
            )
            drop_snapshot = _branded(blob) or dirty
        if cleaned != props or drop_snapshot:
            conn.execute(
                """
                UPDATE jobs
                SET properties_json = ?, snapshot_json = ?, sop_json = NULL,
                    status = CASE WHEN ? THEN 'draft' ELSE status END, updated_at = ?
                WHERE id = ?
                """,
                (
                    dumps(cleaned),
                    None if drop_snapshot else row["snapshot_json"],
                    1 if drop_snapshot else 0,
                    timestamp,
                    row["id"],
                ),
            )
