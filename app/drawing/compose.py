"""Place views, the title block, and the SOP tables on one sheet."""

from __future__ import annotations

from app.drawing.frame import BLOCK_W, BORDER_INSET, border, data_table, signoff_block, title_block, title_block_height
from app.drawing.prims import Prim, text
from app.drawing.views import (
    ROLE_LABELS,
    apply_view_style,
    balloon_stack,
    envelope_view,
    owned_dims,
    place_third_angle,
    render_placed,
    render_view,
    scale_label,
    view_has_geometry,
    view_style_name,
)


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


def _display(model: dict) -> tuple[str, float, str, bool, bool]:
    display = model.get("display") if isinstance(model.get("display"), dict) else {}
    style = view_style_name(display.get("viewStyle"))
    try:
        size = float(display.get("annotationSize") or 0.10)
    except (TypeError, ValueError):
        size = 0.10
    if size <= 0 or size > 1:
        size = 0.10
    annotation = "bold" if display.get("annotationStyle") == "bold" else "standard"
    balloons = display.get("balloons", True)
    parts = display.get("partsList", True)
    return style, size, annotation, bool(balloons), bool(parts)


def _resolve(model: dict, role: str, style: str, size: float, annotation: str) -> dict:
    views = model.get("views") or {}
    authored = views.get(role)
    if view_has_geometry(authored):
        return apply_view_style(authored, style, size, annotation)
    overall = model.get("overall") or {}
    made = envelope_view(role, overall, style, size)
    if view_has_geometry(made):
        made["annotationStyle"] = annotation
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

    inset = BORDER_INSET
    tb_w = min(BLOCK_W, width - 2 * inset - 0.4)
    tb_h = title_block_height(props, tb_w)
    # Seated on the template border's lower-right corner, the way Inventor places it.
    tb = (width - inset - tb_w, inset, tb_w, tb_h)

    spec = table_spec(template, bom_format)
    rows = table_rows(template, model, job.get("bom_rows") or [])
    kind = (template.get("table") or {}).get("kind")
    source = job.get("source_kind") or ""
    style, ann, annotation, want_balloons, want_parts = _display(model)
    # A part has no parts list. An empty bend table is not drawn.
    if source == "ipt" or template.get("drawing_type") == "part" or not want_parts:
        if kind == "parts":
            spec = None
        elif kind == "bend" and not rows and (source == "ipt" or template.get("drawing_type") == "part"):
            spec = None
    table_box = None
    if spec and spec[1]:
        count = max(len(rows), 1)
        if template.get("drawing_type") == "part":
            tw = min(7.6, width * 0.48)
            th = 0.30 * (2 + count)
            table_box = (inset + 0.08, height - inset - th - 0.08, tw, th)
        else:
            # Beside the title block, so the views keep the top of the sheet.
            tw = min(7.5, max(tb[0] - inset - 0.28, 4.2))
            th = 0.22 * (2 + count)
            limit = height - inset - 0.35
            if inset + th > limit:
                th = max(limit - inset, 1.2)
            table_box = (inset + 0.08, inset, tw, th)

    info_box = None
    if (template.get("table") or {}).get("kind") == "signoff" or template.get("drawing_type") == "signoff":
        info_w = min(6.6, tb[0] - inset - 0.25)
        info_box = (inset + 0.08, inset, info_w, tb_h)

    bottom = inset + tb_h + 0.28
    if table_box and template.get("drawing_type") != "part":
        bottom = max(bottom, table_box[1] + table_box[3] + 0.2)
    top = height - inset - 0.16
    area = (inset + 0.12, bottom, width - 2 * inset - 0.24, max(top - bottom, 1))
    overall = model.get("overall") or {}
    authored = any(view_has_geometry((model.get("views") or {}).get(role)) for role in roles)
    balloon_role = next((role for role in ("iso", "front", "side") if role in roles), None)
    use_balloons = source == "iam" and want_balloons and want_parts and len(rows) > 1 and bool(balloon_role)
    placement = None
    if not authored and template.get("drawing_type") != "signoff":
        placement = place_third_angle(roles, area, overall, 1.15 if use_balloons else 0.0)
    boxes = {} if placement else allocate(roles, area, table_box, template.get("drawing_type") or "part")
    if placement:
        covered = set(placement["views"])
        if placement.get("iso"):
            covered.add("iso")
        if placement.get("flat"):
            covered.add("flat")
        rest = [role for role in roles if role not in covered]
        if rest:
            boxes = _grid(rest, area)

    prims: list[Prim] = []
    prims.extend(border(width, height))
    try:
        length = float(overall.get("length") or 0)
        width_in = float(overall.get("width") or 0)
        height_in = float(overall.get("height") or 0)
    except (TypeError, ValueError):
        length, width_in, height_in = 0, 0, 0
    owned = owned_dims(roles, length, width_in, height_in) if placement else {}
    for role in roles:
        view = _resolve(model, role, style, ann, annotation)
        label = label_for.get(role, "")
        placed = placement["views"].get(role) if placement else None
        if placed:
            view = dict(view)
            keep = owned.get(role) or {"h": False, "v": False}
            view["dims"] = [
                dim for dim in (view.get("dims") or [])
                if (dim.get("kind") == "horizontal" and keep["h"]) or (dim.get("kind") == "vertical" and keep["v"])
            ]
            view["caption"] = ""
            prims.extend(render_placed(view, role, label, {
                **placed,
                "scale": placement["scale"],
                "scaleText": scale_label(placement["scale"]) if role == placement["base"] else "",
            }))
            continue
        if placement and role == "iso" and placement.get("iso"):
            box = placement["iso"]
        elif placement and role == "flat" and placement.get("flat"):
            box = placement["flat"]
        else:
            box = boxes.get(role)
        if not box:
            continue
        prims.extend(render_view(view, role, label, box))
        if use_balloons and role == balloon_role:
            prims.extend(balloon_stack(rows, box, width - inset - 0.02))
            use_balloons = False
    if use_balloons and placement:
        target = placement.get("iso")
        placed = (placement.get("views") or {}).get(balloon_role or "")
        if not target and placed:
            target = (
                placed["ox"],
                placed["oy"],
                placed["mw"] * placement["scale"],
                placed["mh"] * placement["scale"],
            )
        if target:
            prims.extend(balloon_stack(rows, target, width - inset - 0.02))
    if table_box and spec:
        prims.extend(data_table(*table_box, spec[0], spec[1], rows))
    prims.extend(title_block(*tb, company, props))
    if info_box:
        prims.extend(signoff_block(*info_box, props, template.get("signoff_fields") or []))

    note = job.get("sample_note")
    if note:
        prims.append(text(inset + 0.12, height - inset - 0.08, note, size=0.07, bold=True))
    return prims
