"""Place views, the title block, and the SOP tables on one sheet."""

from __future__ import annotations

from app.drawing.frame import border, data_table, signoff_block, title_block
from app.drawing.prims import Prim, text
from app.drawing.views import ROLE_LABELS, envelope_view, render_view, view_has_geometry


def _box(x, y, w, h):
    return (x, y, max(w, 0.4), max(h, 0.4))


def _grid(roles: list[str], area, gap: float = 0.28) -> dict:
    x, y, w, h = area
    n = len(roles)
    if n == 0:
        return {}
    cols = 1 if n == 1 else 2 if n <= 4 else 3
    rows = (n + cols - 1) // cols
    cw = (w - gap * (cols - 1)) / cols
    rh = (h - gap * (rows - 1)) / rows
    boxes = {}
    for i, role in enumerate(roles):
        c = i % cols
        r = i // cols
        # Row 0 is the top row.
        boxes[role] = _box(
            x + c * (cw + gap),
            y + (rows - 1 - r) * (rh + gap),
            cw,
            rh,
        )
    return boxes


def allocate(roles: list[str], area, table, drawing_type: str) -> dict:
    x, y, w, h = area
    roles = list(roles)
    if not roles:
        return {}

    if drawing_type == "signoff" and "side" in roles:
        side_h = h * 0.48
        boxes = {"side": _box(x, y, w, side_h)}
        rest = [r for r in roles if r != "side"]
        boxes.update(_grid(rest, (x, y + side_h + 0.12, w, h - side_h - 0.12)))
        return boxes

    if drawing_type in {"weldment", "assembly"} and "side" in roles and len(roles) >= 3:
        side_h = h * 0.46
        boxes = {"side": _box(x, y, w, side_h)}
        rest = [r for r in roles if r != "side"]
        boxes.update(_grid(rest, (x, y + side_h + 0.12, w, h - side_h - 0.12)))
        return boxes

    if drawing_type == "part":
        return _allocate_part(roles, area, table)

    return _grid(roles, area)


def _allocate_part(roles: list[str], area, table) -> dict:
    x, y, w, h = area
    top = y + h
    boxes = {}
    if "iso" in roles:
        if table:
            iso_x = min(table[0] + table[2] + 0.16, x + w * 0.62)
        else:
            iso_x = x + w * 0.62
        iso_h = h * 0.44
        boxes["iso"] = _box(iso_x, top - iso_h, x + w - iso_x, iso_h)
        split_y = top - iso_h
        left_limit = iso_x - 0.1
    else:
        split_y = top
        left_limit = x + w

    rest = [r for r in roles if r != "iso"]
    lower_h = split_y - y
    if "flat" in rest and lower_h > 1.6:
        flat_h = lower_h * (0.48 if len(rest) > 1 else 0.9)
        flat_w = left_limit - x if len(rest) == 1 else w * 0.72
        boxes["flat"] = _box(x, y, flat_w, flat_h)
        others = [r for r in rest if r != "flat"]
        band_h = split_y - (y + flat_h) - 0.22
        if others and band_h > 0.8:
            boxes.update(_grid(others, (x, y + flat_h + 0.22, left_limit - x, band_h)))
        elif others:
            boxes.update(_grid(others, (x, y, w, lower_h)))
            boxes.pop("flat", None)
            boxes.update(_grid(rest, (x, y, left_limit - x, lower_h)))
    else:
        boxes.update(_grid(rest, (x, y, max(left_limit - x, w * 0.5), lower_h)))
    return boxes


def _resolve(model: dict, role: str) -> dict:
    views = model.get("views") or {}
    authored = views.get(role)
    if view_has_geometry(authored):
        return authored
    overall = model.get("overall") or {}
    made = envelope_view(role, overall)
    if view_has_geometry(made):
        return made
    return {"empty": True}


def table_spec(template: dict, bom_format: dict | None) -> tuple[str, list[dict]] | None:
    table = template.get("table") or {}
    kind = table.get("kind")
    if kind == "bend":
        return table.get("title") or "TABLE", table.get("columns") or []
    if kind == "parts" and bom_format:
        return bom_format.get("title") or "Parts List", bom_format.get("columns") or []
    return None


def table_rows(template: dict, model: dict, bom_rows: list[dict]) -> list[dict]:
    kind = (template.get("table") or {}).get("kind")
    if kind == "bend":
        rows = []
        for bend in model.get("bends") or []:
            rows.append({
                "id": bend.get("id", ""),
                "direction": bend.get("direction", ""),
                "angle": bend.get("angle", ""),
                "radius": bend.get("radius", ""),
                **bend,
            })
        return rows
    if kind == "parts":
        return bom_rows or []
    return []


def compose(template: dict, bom_format: dict | None, job: dict) -> list[Prim]:
    width = float(template["sheet_width_in"])
    height = float(template["sheet_height_in"])
    props = dict(job.get("properties") or {})
    props.setdefault("sheetSize", template.get("sheet_label") or "")
    model = job.get("model") or {}
    company = template.get("company") or {}
    roles = list(job.get("selected_views") or [])
    label_for = {v["role"]: v.get("label") or ROLE_LABELS.get(v["role"], v["role"].upper()) for v in template.get("views") or []}

    outer = 0.50
    tb_h = 2.15 if height >= 16 else 1.92 if height >= 10 else 1.6
    tb_w = min(10.8, width - 1.15)
    tb = (width - outer - tb_w, outer, tb_w, tb_h)

    spec = table_spec(template, bom_format)
    rows = table_rows(template, model, job.get("bom_rows") or [])
    table_box = None
    if spec and spec[1]:
        tw = min(7.6, width * 0.48)
        row_h = 0.30
        th = row_h * (2 + max(len(rows), 1))
        table_box = (outer, height - outer - th, tw, th)

    info_box = None
    if (template.get("table") or {}).get("kind") == "signoff" or template.get("drawing_type") == "signoff":
        info_w = min(6.6, tb[0] - outer - 0.2)
        info_box = (outer, outer, info_w, tb_h)

    bottom = outer + tb_h + 0.22
    top = height - outer - 0.12
    # Parts lists sit in the top left. Keep weldment and assembly views below them.
    # A part bend table is short, and the isometric sits beside it.
    if table_box and template.get("drawing_type") != "part":
        top = min(top, table_box[1] - 0.1)
    area = (outer + 0.06, bottom, width - 2 * outer - 0.12, max(top - bottom, 1))
    boxes = allocate(roles, area, table_box, template.get("drawing_type") or "part")

    prims: list[Prim] = []
    prims.extend(border(width, height))
    for role in roles:
        box = boxes.get(role)
        if not box:
            continue
        view = _resolve(model, role)
        prims.extend(render_view(view, role, label_for.get(role, ""), box))
    if table_box and spec:
        prims.extend(data_table(*table_box, spec[0], spec[1], rows))
    prims.extend(title_block(*tb, company, props))
    if info_box:
        prims.extend(signoff_block(*info_box, props, template.get("signoff_fields") or []))

    note = job.get("sample_note")
    if note:
        prims.append(text(outer, height - 0.28, note, size=0.07, bold=True))
    return prims
