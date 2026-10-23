"""Border, title block, parts list, bend table, and signoff information."""

from __future__ import annotations

import math

from app.drawing.prims import Prim, line, rect, text


def wrap(value: str, width_in: float, size: float) -> list[str]:
    if not value:
        return []
    max_chars = max(6, int(width_in / (size * 0.52)))
    lines: list[str] = []
    for paragraph in str(value).split("\n"):
        words = paragraph.split()
        if not words:
            lines.append("")
            continue
        cur = ""
        for word in words:
            trial = f"{cur} {word}".strip()
            if len(trial) <= max_chars:
                cur = trial
            else:
                if cur:
                    lines.append(cur)
                cur = word
        if cur:
            lines.append(cur)
    return lines


def border(width: float, height: float) -> list[Prim]:
    outer = 0.38
    inner = 0.50
    return [
        rect(outer, outer, width - 2 * outer, height - 2 * outer, layer="BORDER"),
        rect(inner, inner, width - 2 * inner, height - 2 * inner, layer="THIN"),
    ]


# standard-desc2: the Standard.idw / Standard.dwg title block.
# The description is two lines. Each line past two grows the block.
BLOCK_W = 8.20
DESC_SIZE = 0.15
DESC_PITCH = 0.22
DESC_LINES = 2
_PART_W = 1.72
_THICK_W = 1.55
_IDENT_H = 0.50
_BODY_H = 1.70


def _desc_width(block_w: float) -> float:
    return max(3.2, block_w - _PART_W - 0.16)


def description_lines(value: str, block_w: float) -> list[str]:
    lines = wrap(value or "—", _desc_width(block_w), DESC_SIZE)
    return lines or ["—"]


def _desc_band(line_count: int) -> float:
    """Label plus two description lines. Extra lines add one pitch each."""
    count = max(DESC_LINES, line_count)
    return 0.30 + count * DESC_PITCH


def title_block_height(props: dict | None, block_w: float) -> float:
    """Description is two lines. The block grows by one line for each line past two."""
    count = len(description_lines((props or {}).get("description") or "", block_w))
    return _desc_band(count) + _IDENT_H + _BODY_H


def _cell_label(prims: list[Prim], x, y, w, h, label, value, value_size=0.11, bold=False, limit=2):
    prims.append(text(x + 0.06, y + h - 0.13, label, size=0.05))
    lines = wrap(value or "—", w - 0.12, value_size)[:limit]
    for i, line_text in enumerate(lines):
        prims.append(text(x + 0.06, y + h - 0.30 - i * value_size * 1.2, line_text, size=value_size, bold=bold))


def star(cx, cy, r_out=0.16, r_in=0.07) -> list[Prim]:
    pts = []
    for i in range(10):
        radius = r_out if i % 2 == 0 else r_in
        ang = math.radians(-90 + i * 36)
        pts.append((cx + radius * math.cos(ang), cy + radius * math.sin(ang)))
    pts.append(pts[0])
    return [line(pts[i][0], pts[i][1], pts[i + 1][0], pts[i + 1][1], layer="THIN") for i in range(len(pts) - 1)]


def diamond(cx, cy, r=0.11) -> list[Prim]:
    pts = [(cx, cy + r), (cx + r, cy), (cx, cy - r), (cx - r, cy), (cx, cy + r)]
    return [line(pts[i][0], pts[i][1], pts[i + 1][0], pts[i + 1][1], layer="OBJECT") for i in range(4)]


def projection_symbol(x, y) -> list[Prim]:
    """Third-angle truncated cone: side view of the frustum, then the near-end circle."""
    prims = [
        line(x, y + 0.16, x + 0.34, y + 0.28, layer="THIN"),
        line(x, y + 0.16, x + 0.34, y + 0.04, layer="THIN"),
        line(x + 0.34, y + 0.28, x + 0.34, y + 0.04, layer="THIN"),
        line(x, y + 0.04, x, y + 0.28, layer="THIN"),
    ]
    # Circle is the view of the small end, placed to the right.
    from app.drawing.prims import circle

    prims.append(circle(x + 0.52, y + 0.16, 0.09, layer="THIN"))
    return prims


def title_block(x, y, w, h, company: dict, props: dict) -> list[Prim]:
    """ANSI-style standard-desc2 block. Description stays two lines and grows past that."""
    lines = description_lines(props.get("description") or "", w)
    band = _desc_band(len(lines))
    y_body = y + _BODY_H
    y_ident = y_body + _IDENT_H
    y_top = y_ident + band
    x_part = x + w - _PART_W
    x_thick = x_part - _THICK_W
    prims: list[Prim] = [rect(x, y, w, y_top - y, layer="TABLE")]
    prims.append(line(x, y_body, x + w, y_body, layer="TABLE"))
    prims.append(line(x, y_ident, x + w, y_ident, layer="TABLE"))
    prims.append(line(x_part, y_body, x_part, y_top, layer="TABLE"))
    prims.append(line(x_thick, y_body, x_thick, y_ident, layer="TABLE"))

    prims.append(text(x + 0.08, y_top - 0.12, "DESCRIPTION", size=0.045))
    for i, line_text in enumerate(lines):
        prims.append(text(x + 0.08, y_top - 0.34 - i * DESC_PITCH, line_text, size=DESC_SIZE, bold=True))
    prims.append(text(x_part + 0.08, y_top - 0.12, "PART NO.", size=0.045))
    pn_lines = wrap(props.get("partNumber") or "—", _PART_W - 0.16, 0.13)[:2] or ["—"]
    pn_base = y_ident + max(0.12, (band - 0.18 - len(pn_lines) * 0.16) / 2)
    for i, line_text in enumerate(pn_lines):
        prims.append(text(x_part + 0.08, pn_base - i * 0.16, line_text, size=0.13, bold=True))

    prims.append(text(x + 0.08, y_ident - 0.13, "MATERIAL", size=0.045))
    prims.append(text(x + 0.08, y_body + 0.12, props.get("material") or "—", size=0.11, bold=True))
    prims.append(text(x_thick + 0.08, y_ident - 0.13, "THICKNESS", size=0.045))
    prims.append(text(x_thick + 0.08, y_body + 0.12, props.get("thickness") or "—", size=0.11, bold=True))
    prims.append(text(x_part + 0.08, y_ident - 0.13, "REV", size=0.045))
    prims.append(text(x_part + 0.08, y_body + 0.12, props.get("rev") or "—", size=0.11, bold=True))

    x_proj = x + 3.05
    x_sign = x + 4.75
    x_meta = x + w - 1.42
    prims.append(line(x_proj, y, x_proj, y_body, layer="TABLE"))
    prims.append(line(x_sign, y, x_sign, y_body, layer="TABLE"))
    prims.append(line(x_meta, y, x_meta, y_body, layer="TABLE"))

    tol = company.get("tolerances") or [
        "DIMENSIONS ARE IN INCHES",
        ".X ± .1",
        ".XX ± .01",
        ".XXX ± .005",
        "ANGLES ± 1°",
    ]
    prims.append(text(x + 0.08, y_body - 0.14, "UNLESS OTHERWISE SPECIFIED", size=0.042, bold=True))
    for i, row in enumerate(tol[:5]):
        prims.append(text(x + 0.08, y_body - 0.32 - i * 0.18, row, size=0.05))
    prims.append(text(x + 0.08, y + 0.08, "DO NOT SCALE DRAWING", size=0.042, bold=True))

    prims.append(text(x_proj + 0.08, y_body - 0.16, "THIRD ANGLE", size=0.05, bold=True))
    prims.append(text(x_proj + 0.08, y_body - 0.32, "PROJECTION", size=0.045, bold=True))
    prims.extend(projection_symbol(x_proj + 0.16, y + 0.36))

    signatures = [
        ("DRAWN", _person(props.get("drawnBy"), props.get("drawnDate")) or "—"),
        ("CHECKED", (props.get("checker") or "").strip() or "—"),
        ("ENG APPR", "—"),
    ]
    sign_h = _BODY_H / len(signatures)
    for i, (label, value) in enumerate(signatures):
        top = y_body - i * sign_h
        if i:
            prims.append(line(x_sign, top, x_meta, top, layer="TABLE"))
        prims.append(text(x_sign + 0.08, top - 0.14, label, size=0.045))
        prims.append(text(x_sign + 0.08, top - sign_h + 0.10, value, size=0.08, bold=True))
    notice = (company.get("proprietary") or "").strip()
    if notice:
        for i, row in enumerate(wrap(notice, x_proj - x - 0.16, 0.042)[:2]):
            prims.append(text(x + 0.08, y + 0.42 - i * 0.12, row, size=0.042))

    meta = [
        ("SCALE", props.get("scale") or "SEE ABOVE"),
        ("SIZE", props.get("sheetSize") or "—"),
        ("MASS", props.get("mass") or "—"),
        ("SHEET", f"{props.get('sheetNumber') or '1'} OF {props.get('sheetCount') or '1'}"),
    ]
    cell_h = _BODY_H / len(meta)
    for i, (label, value) in enumerate(meta):
        top = y_body - i * cell_h
        if i:
            prims.append(line(x_meta, top, x + w, top, layer="TABLE"))
        prims.append(text(x_meta + 0.06, top - 0.13, label, size=0.042))
        prims.append(text(x_meta + 0.06, top - cell_h + 0.08, value or "—", size=0.07, bold=True))
    return prims


def _person(name, date) -> str:
    name = (name or "").strip()
    date = (date or "").strip()
    if name and date:
        return f"{name}   {date}"
    return name or date


def data_table(x, y, w, h, title: str, columns: list[dict], rows: list[dict]) -> list[Prim]:
    """Table with its top at y+h and its bottom at y (Y up)."""
    prims = [rect(x, y, w, h, layer="TABLE")]
    row_h = h / (2 + max(len(rows), 1))
    # Title band.
    title_top = y + h
    prims.append(line(x, title_top - row_h, x + w, title_top - row_h, layer="TABLE"))
    prims.append(text(x + w / 2, title_top - row_h * 0.68, title, size=0.09, anchor="middle", bold=True))
    header_bottom = title_top - 2 * row_h
    prims.append(line(x, header_bottom, x + w, header_bottom, layer="TABLE"))
    cursor = x
    for col in columns:
        cw = w * float(col.get("width") or 0)
        if cursor > x + 0.01:
            prims.append(line(cursor, y, cursor, header_bottom + row_h, layer="TABLE"))
        prims.append(text(cursor + 0.05, header_bottom + row_h * 0.32, col.get("heading", ""), size=0.062, bold=True))
        cursor += cw
    body = rows or [{}]
    for r_index, row in enumerate(body):
        row_top = header_bottom - r_index * row_h
        if r_index:
            prims.append(line(x, row_top, x + w, row_top, layer="TABLE"))
        cursor = x
        for col in columns:
            cw = w * float(col.get("width") or 0)
            value = "" if not rows else row.get(col.get("key"), "")
            prims.append(text(cursor + 0.05, row_top - row_h * 0.68, str(value), size=0.07))
            cursor += cw
    return prims


def signoff_block(x, y, w, h, props: dict, fields: list[dict]) -> list[Prim]:
    prims = [rect(x, y, w, h, layer="TABLE")]
    prims.append(text(x + 0.08, y + h - 0.16, "UNIT AND CUSTOMER", size=0.08, bold=True))
    prims.append(line(x, y + h - 0.26, x + w, y + h - 0.26, layer="TABLE"))
    lines = [
        ("CUSTOMER", props.get("customer") or ""),
        ("ORDER NO.", props.get("orderNumber") or ""),
        ("QUOTE NO.", props.get("quoteNumber") or ""),
    ]
    extras = props.get("extras") or {}
    for field in fields:
        lines.append((field.get("label") or field.get("key", ""), extras.get(field.get("key"), "")))
    lines.append(("SIGNATURE", props.get("signature") or "________________"))
    lines.append(("DATE", props.get("signDate") or "________________"))
    usable = h - 0.36
    step = min(0.16, usable / max(len(lines), 1))
    size = 0.062 if step < 0.15 else 0.07
    for i, (label, value) in enumerate(lines):
        yy = y + h - 0.42 - i * step
        if yy < y + 0.04:
            break
        shown = value if value else "—"
        prims.append(text(x + 0.08, yy, f"{label}:  {shown}", size=size))
    return prims
