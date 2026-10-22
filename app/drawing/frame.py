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


def _cell_label(prims: list[Prim], x, y, w, h, label, value, value_size=0.11, bold=False):
    prims.append(text(x + 0.06, y + h - 0.12, label, size=0.055))
    lines = wrap(value or "—", w - 0.12, value_size)[:3]
    for i, line_text in enumerate(lines):
        prims.append(text(x + 0.06, y + h * 0.42 - i * value_size * 1.15, line_text, size=value_size, bold=bold))


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
    prims: list[Prim] = [rect(x, y, w, h, layer="TABLE")]
    x1 = x + w * 0.23
    x2 = x + w * 0.40
    x3 = x + w * 0.68
    y_mat = y + h * 0.38
    y_bot = y + h * 0.18
    prims.append(line(x, y_mat, x + w, y_mat, layer="TABLE"))
    prims.append(line(x, y_bot, x + w, y_bot, layer="TABLE"))
    prims.append(line(x1, y, x1, y + h, layer="TABLE"))
    prims.append(line(x2, y_mat, x2, y + h, layer="TABLE"))
    prims.append(line(x3, y_bot, x3, y + h, layer="TABLE"))

    # Tolerance column.
    tol = company.get("tolerances") or []
    prims.append(text(x + 0.06, y + h - 0.16, "UNLESS OTHERWISE SPECIFIED", size=0.052, bold=True))
    prims.append(text(x + 0.06, y + h - 0.30, "TOLERANCE:", size=0.052))
    for i, row in enumerate(tol[:6]):
        prims.append(text(x + 0.06, y + h - 0.44 - i * 0.11, row, size=0.06))
    prims.append(text(x + 0.06, y_mat + 0.08, "DO NOT SCALE PRINT", size=0.055, bold=True))

    # Projection.
    prims.append(text(x1 + 0.08, y + h - 0.18, "THIRD ANGLE", size=0.06, bold=True))
    prims.append(text(x1 + 0.08, y + h - 0.32, "PROJECTION", size=0.06, bold=True))
    prims.extend(projection_symbol(x1 + 0.12, y_mat + 0.28))
    standard = company.get("standard") or "THIS DRAWING CONFORMS TO ASME Y14.5M-1994"
    for i, row in enumerate(wrap(standard, (x2 - x1) - 0.12, 0.05)[:4]):
        prims.append(text(x1 + 0.06, y_mat + 0.16 - i * 0.08, row, size=0.048))

    # Identity.
    mark = company.get("mark")
    name_x = x2 + 0.1
    if mark == "star":
        prims.extend(star(x2 + 0.22, y + h - 0.28, 0.14, 0.06))
        name_x = x2 + 0.42
    elif mark == "diamond":
        prims.extend(diamond(x2 + 0.2, y + h - 0.28, 0.1))
        name_x = x2 + 0.38
    prims.append(text(name_x, y + h - 0.24, company.get("name", ""), size=0.15, bold=True))
    prims.append(text(name_x, y + h - 0.40, company.get("sub", ""), size=0.07))
    notice = company.get("proprietary") or ""
    for i, row in enumerate(wrap(notice, (x3 - x2) - 0.16, 0.045)[:5]):
        prims.append(text(x2 + 0.08, y + h - 0.58 - i * 0.075, row, size=0.045))

    # Right-hand name stack.
    stack_h = (y + h - y_mat) / 4
    rows = [
        ("PRODUCT SERIES", props.get("productSeries") or company.get("productSeries") or ""),
        ("DRAWN BY", _person(props.get("drawnBy"), props.get("drawnDate"))),
        ("DESIGNER", _person(props.get("designer"), props.get("designerDate"))),
        ("CHECKER", props.get("checker") or ""),
    ]
    for i, (label, value) in enumerate(rows):
        top = y + h - i * stack_h
        if i:
            prims.append(line(x3, top, x + w, top, layer="TABLE"))
        prims.append(text(x3 + 0.06, top - 0.11, label, size=0.05))
        prims.append(text(x3 + 0.06, top - stack_h + 0.08, value or "—", size=0.075, bold=i == 0))

    # Material / description / part number / rev.
    x_pn = x1 + (x3 - x1) * 0.58
    prims.append(line(x_pn, y_bot, x_pn, y_mat, layer="TABLE"))
    _cell_label(prims, x, y_bot, x1 - x, y_mat - y_bot, "MATERIAL", props.get("material") or "", 0.09, True)
    _cell_label(prims, x1, y_bot, x_pn - x1, y_mat - y_bot, "DESCRIPTION", props.get("description") or "", 0.08, True)
    _cell_label(prims, x_pn, y_bot, x3 - x_pn, y_mat - y_bot, "PART NO.", props.get("partNumber") or "", 0.12, True)
    _cell_label(prims, x3, y_bot, x + w - x3, y_mat - y_bot, "REV", props.get("rev") or "", 0.1, True)

    # Bottom strip.
    bottom_cells = [
        ("SHEET SIZE", props.get("sheetSize") or ""),
        ("MASS", props.get("mass") or ""),
        ("THICKNESS", props.get("thickness") or ""),
        ("SCALE", props.get("scale") or "SEE ABOVE"),
        ("SHEET NO.", f"{props.get('sheetNumber') or '1'} OF {props.get('sheetCount') or '1'}"),
    ]
    cell_w = w / 5
    for i, (label, value) in enumerate(bottom_cells):
        if i:
            prims.append(line(x + i * cell_w, y, x + i * cell_w, y_bot, layer="TABLE"))
        prims.append(text(x + i * cell_w + 0.05, y_bot - 0.11, label, size=0.048))
        prims.append(text(x + i * cell_w + 0.05, y + 0.05, value or "—", size=0.07, bold=True))
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
