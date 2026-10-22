"""Seed drawing templates and the Norstar parts-list format.

Edits made in the app are stored in SQLite and are not overwritten on the next start.
"""

from __future__ import annotations

from datetime import datetime, timezone

from app.db import connect, dumps

NORSTAR = {
    "name": "NORSTAR",
    "sub": "INDUSTRIES",
    "mark": "star",
    "productSeries": "STANDARD DRAWING - IN",
    "standard": "THIS DRAWING CONFORMS TO ASME Y14.5M-1994 FOR DOCUMENTATION PRACTICES",
    "proprietary": "NOTICE: NORSTAR INDUSTRIES CLAIMS PROPRIETARY RIGHTS TO THE MATERIAL SHOWN. THE DRAWING MAY NOT BE REPRODUCED WITHOUT WRITTEN PERMISSION.",
    "tolerances": [".X ± 0.1", ".XX ± 0.03", ".XXX ± 0.010", "ANGLE ± 0.5"],
}

MERIDIAN = {
    "name": "MERIDIAN",
    "sub": "MANUFACTURING",
    "mark": "diamond",
    "productSeries": "CUSTOM PROJECT",
    "standard": "THIS DRAWING CONFORMS TO ASME Y14.5M-1994 FOR DOCUMENTATION PRACTICES",
    "proprietary": "NOTICE: THIS DRAWING IS THE PROPERTY OF MERIDIAN. IT MAY NOT BE REPRODUCED WITHOUT WRITTEN PERMISSION.",
    "tolerances": [".X ± 0.1", ".XX ± 0.03", ".XXX ± 0.010", "ANGLE ± 0.5"],
}

BEND_COLUMNS = [
    {"key": "id", "heading": "BEND ID", "width": 0.18},
    {"key": "direction", "heading": "BEND DIRECTION", "width": 0.32},
    {"key": "angle", "heading": "BEND ANGLE", "width": 0.25},
    {"key": "radius", "heading": "BEND RADIUS", "width": 0.25},
]

PART_VIEWS = [
    {"role": "flat", "label": "FLAT PATTERN"},
    {"role": "front", "label": "FRONT"},
    {"role": "side", "label": "SIDE"},
    {"role": "iso", "label": "ISOMETRIC"},
]

CHAIN_FIELDS = [
    {"key": "project", "label": "PROJECT / REF"},
    {"key": "construction", "label": "CONSTRUCTION MATERIAL"},
    {"key": "head", "label": "HEAD CONSTRUCTION"},
    {"key": "tail", "label": "TAIL CONSTRUCTION"},
]

UTROUGH_FIELDS = [
    {"key": "diameter", "label": "TROUGH DIAMETER"},
    {"key": "capacity", "label": "CAPACITY"},
    {"key": "speed", "label": "SCREW SPEED"},
    {"key": "construction", "label": "CONSTRUCTION MATERIAL"},
    {"key": "cover", "label": "COVER"},
]

ELEVATOR_FIELDS = [
    {"key": "capacity", "label": "CAPACITY"},
    {"key": "belt", "label": "BELT SPEED"},
    {"key": "bucket", "label": "BUCKET"},
    {"key": "casing", "label": "CASING"},
    {"key": "head", "label": "HEAD PULLEY"},
    {"key": "boot", "label": "BOOT PULLEY"},
]


def _template(template_id, name, drawing_type, applies_to, width, height, label, company, views, table, notes, fields=None, default_views=None):
    return {
        "id": template_id,
        "name": name,
        "drawing_type": drawing_type,
        "applies_to": applies_to,
        "sheet_width_in": width,
        "sheet_height_in": height,
        "sheet_label": label,
        "body": {
            "company": company,
            "views": views,
            "default_views": default_views or [view["role"] for view in views],
            "table": table,
            "signoff_fields": fields or [],
            "sop_notes": notes,
        },
    }


TEMPLATES = [
    _template(
        "norstar-part", "Norstar part", "part", "ipt", 17, 11, "B", NORSTAR, PART_VIEWS,
        {"kind": "bend", "title": "TABLE", "columns": BEND_COLUMNS},
        "Flat parts: side, front, isometric, and a flat view when the part has bends. "
        "Dimension overall height and width on the side, the front, and the flat. "
        "Dimension thickness where it is easiest to see. Laser cut-outs that are in the DXF stay undimensioned. "
        "Bend lines, bend IDs, and a bend table are required when the part is formed. Direction up whenever possible.",
    ),
    _template(
        "norstar-weldment", "Norstar weldment", "weldment", "iam", 22, 17, "C", NORSTAR,
        [
            {"role": "side", "label": "SIDE"},
            {"role": "end", "label": "END"},
            {"role": "detail", "label": "DETAIL A"},
            {"role": "iso", "label": "ISOMETRIC"},
            {"role": "top", "label": "TOP"},
        ],
        {"kind": "parts", "title": "Parts List"},
        "Use as many views as production needs. Dimension overall height, width, and depth. "
        "Dimension where parts meet, from the end of one part to the first face of the next. "
        "Use baseline dimensions when several parts sit on a long base. "
        "Put weld symbols on the view that points at the joint most clearly. "
        "Parts list in the top left, with a balloon for every item.",
        default_views=["side", "end", "detail", "iso"],
    ),
    _template(
        "norstar-assembly", "Norstar assembly", "assembly", "iam", 22, 17, "C", NORSTAR,
        [
            {"role": "side", "label": "SIDE"},
            {"role": "top", "label": "TOP"},
            {"role": "end", "label": "END"},
            {"role": "iso", "label": "ISOMETRIC"},
            {"role": "front", "label": "FRONT"},
        ],
        {"kind": "parts", "title": "Parts List"},
        "Use as many views as production needs. Dimension overall height, width, and depth. "
        "Parts list in the top left, with a balloon for every item. "
        "Part number and description go in the title block.",
        default_views=["side", "top", "end", "iso"],
    ),
    _template(
        "norstar-signoff", "Norstar signoff — chain conveyor", "signoff", "iam", 34, 22, "D", NORSTAR,
        [
            {"role": "side", "label": "SIDE ELEVATION"},
            {"role": "front", "label": "FRONT"},
            {"role": "section", "label": "SECTION A-A"},
            {"role": "inlet", "label": "INLET FLANGE"},
            {"role": "discharge", "label": "DISCHARGE FLANGE"},
        ],
        {"kind": "signoff"},
        "Side view with overall length, overall height, discharge height, and each section length labeled. "
        "Front view, end cross-section dimensioned for ordered height and width, and face views of the inlet and discharge "
        "showing flange size and the opening. Customer, order number, quote number, signature, and date sit in the lower left, "
        "plus the unit lines for this conveyor.",
        fields=CHAIN_FIELDS,
    ),
    _template(
        "meridian-part", "Meridian part", "part", "ipt", 17, 11, "B", MERIDIAN, PART_VIEWS,
        {"kind": "bend", "title": "TABLE", "columns": BEND_COLUMNS},
        "Same part-drawing rules as the shop SOP. Swap the title block if Meridian uses a different tolerance block.",
    ),
    _template(
        "meridian-signoff-utrough", "Meridian signoff — u-trough", "signoff", "iam", 34, 22, "D", MERIDIAN,
        [
            {"role": "side", "label": "SIDE ELEVATION"},
            {"role": "section", "label": "SECTION A-A"},
            {"role": "inlet", "label": "INLET FLANGE"},
            {"role": "discharge", "label": "DISCHARGE FLANGE"},
            {"role": "front", "label": "FRONT"},
        ],
        {"kind": "signoff"},
        "U-trough signoff. Side elevation with section lengths, end cross-section for ordered size, inlet and discharge faces. "
        "Customer block includes trough diameter, capacity, screw speed, material, and cover.",
        fields=UTROUGH_FIELDS,
        default_views=["side", "section", "inlet", "discharge"],
    ),
    _template(
        "meridian-signoff-elevator", "Meridian signoff — bucket elevator", "signoff", "iam", 34, 22, "D", MERIDIAN,
        [
            {"role": "side", "label": "SIDE ELEVATION"},
            {"role": "section", "label": "SECTION A-A"},
            {"role": "inlet", "label": "INLET"},
            {"role": "discharge", "label": "DISCHARGE"},
            {"role": "front", "label": "FRONT"},
        ],
        {"kind": "signoff"},
        "Bucket elevator signoff. Side elevation with boot, leg, and head labeled and dimensioned. "
        "End cross-section confirms casing size. Inlet and discharge faces show the opening. "
        "A long leg may be drawn broken, with the true length in the dimension.",
        fields=ELEVATOR_FIELDS,
        default_views=["side", "section", "inlet", "discharge"],
    ),
]

BOM_FORMATS = [
    {
        "id": "norstar-parts-list",
        "name": "Norstar parts list",
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
    now = datetime.now(timezone.utc).isoformat()
    with connect() as conn:
        count = conn.execute("SELECT COUNT(*) AS n FROM templates").fetchone()["n"]
        if count:
            return
        for template in TEMPLATES:
            conn.execute(
                """
                INSERT INTO templates
                (id, name, drawing_type, applies_to, sheet_width_in, sheet_height_in, sheet_label, body_json, updated_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    template["id"], template["name"], template["drawing_type"], template["applies_to"],
                    template["sheet_width_in"], template["sheet_height_in"], template["sheet_label"],
                    dumps(template["body"]), now,
                ),
            )
        for fmt in BOM_FORMATS:
            conn.execute(
                "INSERT INTO bom_formats (id, name, is_default, body_json, updated_at) VALUES (?, ?, ?, ?, ?)",
                (fmt["id"], fmt["name"], fmt["is_default"], dumps(fmt["body"]), now),
            )
