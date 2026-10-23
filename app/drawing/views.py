"""Fit a model view into a sheet box and draw dimensions, welds, and balloons."""

from __future__ import annotations

import math

from app.drawing.prims import Prim, arc, circle, line, poly, solid, text

ROLE_LABELS = {
    "flat": "FLAT PATTERN",
    "front": "FRONT",
    "side": "SIDE",
    "top": "TOP",
    "bottom": "BOTTOM",
    "back": "BACK",
    "end": "END",
    "iso": "ISOMETRIC",
    "section": "SECTION A-A",
    "inlet": "INLET FLANGE",
    "discharge": "DISCHARGE FLANGE",
    "detail": "DETAIL",
}


def _as_float(value, default=0.0) -> float:
    try:
        return float(value)
    except (TypeError, ValueError):
        return default


VIEW_STYLES = ("hidden-line-removed", "hidden-line", "shaded", "raster")
_STYLE_NOTE = {
    "hidden-line": "HIDDEN LINE",
    "shaded": "SHADED",
    "raster": "RASTER",
}


def view_style_name(value) -> str:
    style = str(value or "hidden-line-removed")
    return style if style in VIEW_STYLES else "hidden-line-removed"


def _style_caption(style: str, envelope: bool = False) -> str:
    return _STYLE_NOTE.get(style, "")


def _face_colors(style: str) -> list[str]:
    if style == "shaded":
        return ["#d9d4cc", "#e6e1d8", "#c4bfb6"]
    if style == "raster":
        return ["#b7b2a8", "#d2cdc4", "#8f8a82"]
    return []


def profile_size(role: str, length: float, width: float, height: float) -> tuple[float, float]:
    """Model width and height of one orthographic view.

    With no thickness, the front view is the plate face and the projected
    views are a thin edge. That edge is not a measured thickness.
    """
    known = height > 0
    visual = height if known else max(min(length, width) * 0.06, 0.12)
    if role in {"front", "back"}:
        return (length, height) if known else (length, width)
    if role in {"side", "end", "section"}:
        return (width, height) if known else (width, visual)
    if role in {"top", "bottom"}:
        return (length, width) if known else (length, visual)
    if role == "flat":
        return length, width
    return (length, height) if known else (length, width)


def owned_dims(roles: list[str], length: float, width: float, height: float) -> dict:
    """Each overall axis is dimensioned once, on the view where it is easiest to read."""
    owned = {role: {"h": False, "v": False} for role in roles}
    known = height > 0
    if "front" in roles:
        owned["front"] = {"h": True, "v": True}
        if known and "top" in roles:
            owned["top"] = {"h": False, "v": True}
        elif known and "side" in roles:
            owned["side"] = {"h": True, "v": False}
        elif known and "end" in roles:
            owned["end"] = {"h": True, "v": False}
    elif "top" in roles:
        owned["top"] = {"h": True, "v": True}
    elif "side" in roles:
        owned["side"] = {"h": True, "v": True}
    return owned


_NICE_SCALES = (
    10, 5, 4, 2, 1, 0.5, 0.25, 0.2, 0.125, 0.1,
    1 / 12, 1 / 16, 0.05, 1 / 24, 1 / 30, 1 / 32, 0.025, 0.02, 1 / 64, 0.01,
)


def snap_scale(exact: float) -> float:
    if exact <= 0:
        return exact
    fit = [scale for scale in _NICE_SCALES if scale <= exact * 1.001]
    return fit[0] if fit else exact


def scale_label(scale: float) -> str:
    if scale >= 1 and abs(scale - round(scale)) < 1e-6:
        return f"SCALE {int(round(scale))} : 1"
    if scale > 0:
        inverse = 1 / scale
        if abs(inverse - round(inverse)) < 0.08:
            return f"SCALE 1 : {int(round(inverse))}"
    return f"SCALE {scale:.3f}"


def place_third_angle(roles: list[str], area, overall: dict, right_reserve: float = 0.0) -> dict | None:
    """Third-angle views, large enough to read. Side and end stack so a long assembly is not three stamps in a row."""
    length = _as_float(overall.get("length"))
    width = _as_float(overall.get("width"))
    height = _as_float(overall.get("height"))
    if length <= 0 or width <= 0:
        return None
    x, y, aw, ah = area
    roles = list(roles)
    flat_box = None
    if "flat" in roles:
        flat_h = min(ah * 0.28, 2.6)
        flat_box = (x, y, max(aw - right_reserve, 1), flat_h)
        y += flat_h + 0.2
        ah -= flat_h + 0.2
    columns = []
    if "back" in roles and "front" in roles:
        columns.append(["back"])
    center = []
    if "bottom" in roles:
        center.append("bottom")
    if "front" in roles:
        center.append("front")
    elif "back" in roles:
        center.append("back")
    if "top" in roles:
        center.append("top")
    if center:
        columns.append(center)
    depth = [role for role in ("side", "end", "section") if role in roles]
    if depth:
        columns.append(depth)
    if not columns or aw < 1.5 or ah < 1.5:
        return None

    def wh(role):
        return profile_size(role, length, width, height)

    gap = 0.72
    model_w = sum(max(wh(role)[0] for role in column) for column in columns)
    model_h = max(sum(wh(role)[1] for role in column) for column in columns)
    gaps_x = max(len(columns) - 1, 0)
    gaps_y = max(max(len(column) - 1, 0) for column in columns)
    avail_w = aw - right_reserve - 1.05
    avail_h = ah - 0.95
    if model_w <= 0 or model_h <= 0 or avail_w <= 0.5 or avail_h <= 0.5:
        return None
    exact = min((avail_w - gap * gaps_x) / model_w, (avail_h - gap * gaps_y) / model_h)
    candidates = [scale for scale in _NICE_SCALES if scale <= exact * 1.001] or [max(exact, 0.01)]
    want_iso = "iso" in roles

    def layout(scale: float):
        cursor_x = x + 0.72
        origin_y = y + 0.82
        placed = {}
        for column in columns:
            cursor_y = origin_y
            column_w = max(wh(role)[0] for role in column)
            for role in column:
                mw, mh = wh(role)
                placed[role] = {
                    "ox": cursor_x + (column_w - mw) * scale / 2,
                    "oy": cursor_y,
                    "mw": mw,
                    "mh": mh,
                }
                cursor_y += mh * scale + gap
            cursor_x += column_w * scale + gap
        used_right = max(item["ox"] + item["mw"] * scale for item in placed.values())
        used_top = max(item["oy"] + item["mh"] * scale for item in placed.values())
        return placed, used_right, used_top

    scale = candidates[-1]
    placed, used_right, used_top = layout(scale)
    for candidate in candidates:
        trial_placed, trial_right, trial_top = layout(candidate)
        free_right = (x + aw - right_reserve) - trial_right
        if want_iso and free_right < 2.5 and candidate != candidates[-1]:
            continue
        scale = candidate
        placed, used_right, used_top = trial_placed, trial_right, trial_top
        break

    iso_box = None
    if want_iso:
        free_right = (x + aw - right_reserve) - used_right
        free_above = (y + ah) - used_top
        if free_right >= 2.1:
            iso_box = (used_right + 0.28, y + 0.12, free_right - 0.28, max(ah - 0.22, 1.4))
        elif free_above >= 1.7:
            iso_w = min(4.8, max(aw * 0.36, 2.2))
            iso_box = (x + aw - right_reserve - iso_w, used_top + 0.18, iso_w, max(free_above - 0.28, 1.4))
    base = "front" if "front" in placed else next(iter(placed))
    return {"views": placed, "scale": scale, "base": base, "iso": iso_box, "flat": flat_box}


def balloon_stack(rows: list[dict], box: tuple, limit_x: float) -> list[Prim]:
    """Item balloons in a column beside a view. Sheet inches, so the leaders stay short."""
    x, y, w, h = box
    count = min(len(rows), 16)
    if count <= 0 or w <= 0 or h <= 0:
        return []
    pitch = 0.34
    if pitch * max(count - 1, 1) > h - 0.2:
        pitch = max(0.26, (h - 0.2) / max(count - 1, 1))
    stack = pitch * (count - 1)
    top = y + (h + stack) / 2
    cx = min(x + w + 0.50, limit_x - 0.16)
    prims: list[Prim] = []
    radius = 0.13
    for index, row in enumerate(rows[:count]):
        item = row.get("item")
        if item in (None, ""):
            item = index + 1
        by = top - index * pitch
        ty = min(max(by, y + 0.1), y + h - 0.1)
        prims.append(circle(cx, by, radius, layer="THIN"))
        prims.append(text(cx, by - 0.035, str(item), size=0.08, anchor="middle", bold=True))
        prims.append(line(cx - radius, by, x + w, ty, layer="THIN"))
        prims.append(solid([(x + w, ty), (x + w - 0.07, ty + 0.028), (x + w - 0.07, ty - 0.028)]))
    return prims


def envelope_view(role: str, overall: dict, view_style: str = "hidden-line-removed", annotation_size: float = 0.10) -> dict:
    length = _as_float(overall.get("length"))
    width = _as_float(overall.get("width"))
    height = _as_float(overall.get("height"))
    if length <= 0 or width <= 0:
        return {"empty": True}
    known = height > 0
    visual = height if known else max(min(length, width) * 0.06, 0.12)
    style = view_style_name(view_style)
    if role == "iso":
        return _iso_box(length, width, height if known else visual, style, annotation_size)
    if role in {"front", "back"}:
        w, h = (length, height) if known else (length, width)
    elif role in {"side", "end", "section"}:
        w, h = (width, height) if known else (width, visual)
    elif role in {"top", "bottom"}:
        w, h = (length, width) if known else (length, visual)
    elif role == "flat":
        w, h = length, width
    else:
        w, h = (length, height) if known else (length, width)
    pad_x = max(w * 0.12, 0.4)
    pad_y = max(h * 0.18, 0.45)
    view = {
        "paths": [{"pts": [[0, 0], [w, 0], [w, h], [0, h], [0, 0]], "layer": "OBJECT"}],
        "dims": [
            {"kind": "horizontal", "x1": 0, "x2": w, "y": -pad_y, "ext": 0, "text": _fmt(w)},
            {"kind": "vertical", "y1": 0, "y2": h, "x": -pad_x, "ext": 0, "text": _fmt(h)},
        ],
        "caption": _style_caption(style, True),
        "annotationSize": annotation_size,
    }
    colors = _face_colors(style)
    if colors:
        view["fills"] = [{"pts": [[0, 0], [w, 0], [w, h], [0, h]], "fill": colors[0]}]
    return view


def _iso_box(length: float, width: float, height: float, style: str = "hidden-line-removed", annotation_size: float = 0.10) -> dict:
    def p(x, y, z):
        c = math.cos(math.radians(30))
        s = math.sin(math.radians(30))
        return [(x - z) * c, y + (x + z) * s]

    corners = {
        (i, j, k): p(i * length, j * height, k * width)
        for i in (0, 1)
        for j in (0, 1)
        for k in (0, 1)
    }
    edges = [
        ((0, 0, 0), (1, 0, 0)),
        ((1, 0, 0), (1, 1, 0)),
        ((1, 1, 0), (0, 1, 0)),
        ((0, 1, 0), (0, 0, 0)),
        ((0, 0, 1), (1, 0, 1)),
        ((1, 0, 1), (1, 1, 1)),
        ((1, 1, 1), (0, 1, 1)),
        ((0, 1, 1), (0, 0, 1)),
        ((0, 0, 0), (0, 0, 1)),
        ((1, 0, 0), (1, 0, 1)),
        ((1, 1, 0), (1, 1, 1)),
        ((0, 1, 0), (0, 1, 1)),
    ]
    paths = []
    for a, b in edges:
        hidden = style == "hidden-line" and a[2] == 1 and b[2] == 1
        paths.append({
            "pts": [corners[a], corners[b]],
            "layer": "HIDDEN" if hidden else "OBJECT",
            "dashed": hidden,
        })
    view = {
        "paths": paths,
        "caption": _style_caption(style, True),
        "annotationSize": annotation_size,
    }
    colors = _face_colors(style)
    if colors:
        def face(*keys):
            return [corners[key] for key in keys]

        view["fills"] = [
            {"pts": face((0, 0, 0), (1, 0, 0), (1, 1, 0), (0, 1, 0)), "fill": colors[0]},
            {"pts": face((0, 1, 0), (1, 1, 0), (1, 1, 1), (0, 1, 1)), "fill": colors[1]},
            {"pts": face((1, 0, 0), (1, 0, 1), (1, 1, 1), (1, 1, 0)), "fill": colors[2]},
        ]
    return view


def _fmt(value: float) -> str:
    text_value = f"{value:.3f}".rstrip("0").rstrip(".")
    if "." not in text_value:
        return f"{value:.3f}"
    return text_value


def view_has_geometry(view: dict | None) -> bool:
    if not view or view.get("empty"):
        return False
    return bool(view.get("paths") or view.get("circles") or view.get("arcs") or view.get("hatch"))


def _bbox_of(view: dict) -> tuple[float, float, float, float]:
    xs: list[float] = []
    ys: list[float] = []

    def add(x, y):
        xs.append(x)
        ys.append(y)

    for path in view.get("paths") or []:
        for x, y in path.get("pts") or []:
            add(x, y)
    for fill in view.get("fills") or []:
        for x, y in fill.get("pts") or []:
            add(x, y)
    for c in view.get("circles") or []:
        r = _as_float(c.get("r"))
        add(_as_float(c.get("cx")) - r, _as_float(c.get("cy")) - r)
        add(_as_float(c.get("cx")) + r, _as_float(c.get("cy")) + r)
    for a in view.get("arcs") or []:
        for x, y in _sample_arc(a):
            add(x, y)
    for d in view.get("dims") or []:
        kind = d.get("kind")
        if kind == "horizontal":
            add(_as_float(d.get("x1")), _as_float(d.get("y")))
            add(_as_float(d.get("x2")), _as_float(d.get("y")))
            add(_as_float(d.get("x1")), _as_float(d.get("ext", d.get("y"))))
            add(_as_float(d.get("x2")), _as_float(d.get("ext", d.get("y"))))
        elif kind == "vertical":
            add(_as_float(d.get("x")), _as_float(d.get("y1")))
            add(_as_float(d.get("x")), _as_float(d.get("y2")))
            add(_as_float(d.get("ext", d.get("x"))), _as_float(d.get("y1")))
        elif kind == "leader":
            add(_as_float(d.get("x")), _as_float(d.get("y")))
            add(_as_float(d.get("tx")), _as_float(d.get("ty")))
    for note in view.get("notes") or []:
        add(_as_float(note.get("x")), _as_float(note.get("y")))
    for b in view.get("balloons") or []:
        add(_as_float(b.get("x")), _as_float(b.get("y")))
        add(_as_float(b.get("nx")), _as_float(b.get("ny")))
    for w in view.get("welds") or []:
        add(_as_float(w.get("x")), _as_float(w.get("y")))
        add(_as_float(w.get("tx", w.get("x"))), _as_float(w.get("ty", w.get("y"))))
    if not xs:
        return (0, 0, 1, 1)
    return (min(xs), min(ys), max(xs), max(ys))


def _sample_arc(a: dict) -> list[tuple[float, float]]:
    cx, cy, r = _as_float(a.get("cx")), _as_float(a.get("cy")), _as_float(a.get("r"))
    a0, a1 = _as_float(a.get("a0")), _as_float(a.get("a1"))
    sweep = a1 - a0
    if sweep <= 0:
        sweep += 360
    pts = []
    for i in range(9):
        ang = math.radians(a0 + sweep * i / 8)
        pts.append((cx + r * math.cos(ang), cy + r * math.sin(ang)))
    return pts


def _sheet_span(x1, y1, x2, y2, value, size, bold, horizontal: bool) -> list[Prim]:
    prims = [line(x1, y1, x2, y2, layer="DIM"), _arrow(x1, y1, x2, y2), _arrow(x2, y2, x1, y1)]
    if horizontal:
        prims.append(text((x1 + x2) / 2, y1 + 0.06, value, size=size, anchor="middle", bold=bold))
    else:
        prims.append(text(x1 - 0.06, (y1 + y2) / 2, value, size=size, anchor="end", bold=bold))
    return prims


def render_placed(view: dict, role: str, label: str, place: dict) -> list[Prim]:
    """Draw one orthographic view at a shared third-angle scale."""
    scale = float(place["scale"])
    ox, oy = float(place["ox"]), float(place["oy"])
    mw, mh = float(place["mw"]), float(place["mh"])
    prims: list[Prim] = []

    def p(px, py):
        return ox + px * scale, oy + py * scale

    ann = _as_float((view or {}).get("annotationSize"), 0.10) or 0.10
    bold = str((view or {}).get("annotationStyle") or "") == "bold"
    for fill in (view or {}).get("fills") or []:
        pts = [p(px, py) for px, py in fill.get("pts") or []]
        if len(pts) >= 3:
            prims.append(solid(pts, fill=str(fill.get("fill") or "")))
    for path in (view or {}).get("paths") or []:
        pts = [p(px, py) for px, py in path.get("pts") or []]
        if len(pts) >= 2:
            layer = path.get("layer") or "OBJECT"
            dashed = bool(path.get("dashed")) or layer in {"CENTER", "HIDDEN"}
            prims.append(poly(pts, layer=layer, dashed=dashed))
    dims = (view or {}).get("dims") or []
    for dim in dims:
        if dim.get("kind") == "horizontal":
            prims.extend(_sheet_span(ox, oy - 0.36, ox + mw * scale, oy - 0.36, dim.get("text", ""), ann, bold, True))
        elif dim.get("kind") == "vertical":
            prims.extend(_sheet_span(ox - 0.42, oy, ox - 0.42, oy + mh * scale, dim.get("text", ""), ann, bold, False))
    title = label or ROLE_LABELS.get(role, role.upper())
    name_y = oy - (0.62 if any(dim.get("kind") == "horizontal" for dim in dims) else 0.28)
    prims.append(text(ox + mw * scale / 2, name_y, title, size=0.10, anchor="middle", bold=True))
    scale_text = place.get("scaleText") or ""
    if scale_text:
        prims.append(text(ox + mw * scale / 2, name_y - 0.16, scale_text, size=0.08, anchor="middle"))
    for balloon in (view or {}).get("balloons") or []:
        prims.extend(_balloon(balloon, p))
    return prims


def render_view(view: dict, role: str, label: str, box: tuple[float, float, float, float]) -> list[Prim]:
    x, y, w, h = box
    prims: list[Prim] = []
    caption = (view or {}).get("caption")
    title = label or ROLE_LABELS.get(role, role.upper())
    if caption:
        title = f"{title} — {caption}"
    prims.append(text(x + w / 2, y + 0.02, title, size=0.09, anchor="middle", bold=True))
    scale_note = (view or {}).get("scale")
    if scale_note:
        prims.append(text(x + w / 2, y + 0.16, str(scale_note), size=0.07, anchor="middle"))

    inner_bottom = y + (0.32 if scale_note else 0.2)
    inner = (x + 0.06, inner_bottom, max(w - 0.12, 0.4), max(h - (inner_bottom - y) - 0.06, 0.4))
    if not view or view.get("empty") or not view_has_geometry(view):
        prims.append(text(x + w / 2, y + h / 2, "NO PROFILE", size=0.1, anchor="middle"))
        return prims

    minx, miny, maxx, maxy = _bbox_of(view)
    gw = max(maxx - minx, 0.01)
    gh = max(maxy - miny, 0.01)
    ix, iy, iw, ih = inner
    scale = min(iw / gw, ih / gh)
    ox = ix + (iw - gw * scale) / 2 - minx * scale
    oy = iy + (ih - gh * scale) / 2 - miny * scale

    def p(px, py):
        return ox + px * scale, oy + py * scale

    ann = _as_float((view or {}).get("annotationSize"), 0.10)
    if ann <= 0:
        ann = 0.10
    bold = str((view or {}).get("annotationStyle") or "") == "bold"
    for fill in view.get("fills") or []:
        pts = [p(px, py) for px, py in fill.get("pts") or []]
        if len(pts) >= 3:
            prims.append(solid(pts, fill=str(fill.get("fill") or "")))
    for path in view.get("paths") or []:
        pts = [p(px, py) for px, py in path.get("pts") or []]
        if len(pts) >= 2:
            layer = path.get("layer") or "OBJECT"
            dashed = bool(path.get("dashed")) or layer in {"CENTER", "HIDDEN"}
            prims.append(poly(pts, layer=layer, dashed=dashed))
    for c in view.get("circles") or []:
        cx, cy = p(_as_float(c.get("cx")), _as_float(c.get("cy")))
        prims.append(circle(cx, cy, _as_float(c.get("r")) * scale, layer=c.get("layer") or "OBJECT"))
        if c.get("center", True) and c.get("layer", "OBJECT") == "OBJECT":
            r = _as_float(c.get("r")) * scale
            arm = r + 0.08
            prims.append(line(cx - arm, cy, cx + arm, cy, layer="CENTER", dashed=True))
            prims.append(line(cx, cy - arm, cx, cy + arm, layer="CENTER", dashed=True))
    for a in view.get("arcs") or []:
        cx, cy = p(_as_float(a.get("cx")), _as_float(a.get("cy")))
        prims.append(arc(cx, cy, _as_float(a.get("r")) * scale, _as_float(a.get("a0")), _as_float(a.get("a1")), layer=a.get("layer") or "OBJECT"))
    for hatch in view.get("hatch") or []:
        prims.extend(_hatch(hatch, p, scale))
    for dim in view.get("dims") or []:
        prims.extend(_dim(dim, p, ann, bold))
    for note in view.get("notes") or []:
        nx, ny = p(_as_float(note.get("x")), _as_float(note.get("y")))
        prims.append(text(nx, ny, note.get("text", ""), size=_as_float(note.get("size"), 0.09), anchor=note.get("anchor", "start"), bold=bool(note.get("bold"))))
    for weld in view.get("welds") or []:
        prims.extend(_weld(weld, p))
    for balloon in view.get("balloons") or []:
        prims.extend(_balloon(balloon, p))
    return prims


def _hatch(hatch: dict, p, scale: float) -> list[Prim]:
    x0, y0 = _as_float(hatch.get("x")), _as_float(hatch.get("y"))
    w, h = _as_float(hatch.get("w")), _as_float(hatch.get("h"))
    gap = _as_float(hatch.get("gap"), 0.18)
    prims = []
    span = w + h
    start = -h
    n = int(span / gap) + 2
    for i in range(n):
        # 45-degree line y - x = k, clipped to the rectangle.
        k = start + i * gap
        candidates = []
        y = x0 + k
        if y0 <= y <= y0 + h:
            candidates.append((x0, y))
        # right x=x0+w
        y = x0 + w + k
        if y0 <= y <= y0 + h:
            candidates.append((x0 + w, y))
        # bottom y=y0: x = y0 - k
        x = y0 - k
        if x0 <= x <= x0 + w:
            candidates.append((x, y0))
        # top y=y0+h
        x = y0 + h - k
        if x0 <= x <= x0 + w:
            candidates.append((x, y0 + h))
        uniq = []
        for pt in candidates:
            if all(abs(pt[0] - u[0]) > 1e-6 or abs(pt[1] - u[1]) > 1e-6 for u in uniq):
                uniq.append(pt)
        if len(uniq) >= 2:
            a, b = p(*uniq[0]), p(*uniq[1])
            prims.append(line(a[0], a[1], b[0], b[1], layer="HATCH"))
    return prims


def _arrow(x, y, toward_x, toward_y, length=0.09) -> Prim:
    ang = math.atan2(toward_y - y, toward_x - x)
    back = ang + math.pi
    a1 = back + 0.38
    a2 = back - 0.38
    p1 = (x + length * math.cos(a1), y + length * math.sin(a1))
    p2 = (x + length * math.cos(a2), y + length * math.sin(a2))
    return solid([(x, y), p1, p2])


def _dim(dim: dict, p, size: float = 0.10, bold: bool = False) -> list[Prim]:
    kind = dim.get("kind")
    prims: list[Prim] = []
    if kind == "horizontal":
        x1, y1 = p(_as_float(dim["x1"]), _as_float(dim["y"]))
        x2, y2 = p(_as_float(dim["x2"]), _as_float(dim["y"]))
        ext = _as_float(dim.get("ext", dim["y"]))
        e1 = p(_as_float(dim["x1"]), ext)
        e2 = p(_as_float(dim["x2"]), ext)
        prims.extend(_extension(e1, (x1, y1)))
        prims.extend(_extension(e2, (x2, y2)))
        prims.append(line(x1, y1, x2, y2, layer="DIM"))
        prims.append(_arrow(x1, y1, x2, y2))
        prims.append(_arrow(x2, y2, x1, y1))
        mx, my = (x1 + x2) / 2, (y1 + y2) / 2
        ox, oy = _away((x1, y1), e1, 0.05)
        prims.append(text(mx + ox, my + oy, dim.get("text", ""), size=size, anchor="middle", bold=bold))
    elif kind == "vertical":
        x1, y1 = p(_as_float(dim["x"]), _as_float(dim["y1"]))
        x2, y2 = p(_as_float(dim["x"]), _as_float(dim["y2"]))
        ext = _as_float(dim.get("ext", dim["x"]))
        e1 = p(ext, _as_float(dim["y1"]))
        e2 = p(ext, _as_float(dim["y2"]))
        prims.extend(_extension(e1, (x1, y1)))
        prims.extend(_extension(e2, (x2, y2)))
        prims.append(line(x1, y1, x2, y2, layer="DIM"))
        prims.append(_arrow(x1, y1, x2, y2))
        prims.append(_arrow(x2, y2, x1, y1))
        mx, my = (x1 + x2) / 2, (y1 + y2) / 2
        ox, oy = _away((x1, y1), e1, 0.05)
        anchor = "end" if ox < 0 else "start"
        prims.append(text(mx + ox, my + oy, dim.get("text", ""), size=size, anchor=anchor, bold=bold))
    elif kind == "leader":
        x, y = p(_as_float(dim["x"]), _as_float(dim["y"]))
        tx, ty = p(_as_float(dim["tx"]), _as_float(dim["ty"]))
        prims.append(line(tx, ty, x, y, layer="DIM"))
        prims.append(_arrow(x, y, tx, ty))
        prims.append(text(tx, ty + 0.03, dim.get("text", ""), size=size, anchor=dim.get("anchor", "start"), bold=bold))
    return prims


def _away(dim_pt, ext_pt, dist) -> tuple[float, float]:
    dx, dy = dim_pt[0] - ext_pt[0], dim_pt[1] - ext_pt[1]
    norm = math.hypot(dx, dy) or 1
    return dx / norm * dist, dy / norm * dist


def _extension(start, end) -> list[Prim]:
    dx, dy = end[0] - start[0], end[1] - start[1]
    norm = math.hypot(dx, dy) or 1
    ux, uy = dx / norm, dy / norm
    gap = 0.05
    overrun = 0.06
    a = (start[0] + ux * gap, start[1] + uy * gap)
    b = (end[0] + ux * overrun, end[1] + uy * overrun)
    return [line(a[0], a[1], b[0], b[1], layer="DIM")]


def _weld(weld: dict, p) -> list[Prim]:
    jx, jy = p(_as_float(weld.get("x")), _as_float(weld.get("y")))
    tx, ty = p(_as_float(weld.get("tx", weld.get("x"))), _as_float(weld.get("ty", weld.get("y"))))
    prims = [line(tx, ty, jx, jy, layer="THIN"), _arrow(jx, jy, tx, ty)]
    # Reference line runs to the right of the tail point.
    x2, y2 = tx + 0.85, ty
    prims.append(line(tx, ty, x2, y2, layer="THIN"))
    size = str(weld.get("size", ""))
    # Fillet triangle under the reference line (arrow side).
    t1 = (tx + 0.22, ty)
    t2 = (tx + 0.5, ty)
    t3 = (tx + 0.36, ty - 0.16)
    prims.append(poly([t1, t2, t3, t1], layer="THIN"))
    if size:
        prims.append(text(tx + 0.36, ty + 0.04, size, size=0.08, anchor="middle"))
    tail = weld.get("tail")
    if tail:
        prims.append(text(x2 + 0.06, ty + 0.02, str(tail), size=0.075, anchor="start"))
    return prims


def attach_balloons(view: dict, rows: list[dict]) -> dict:
    """Item balloons beside a view. Assemblies only; the caller decides that."""
    if not rows or not view or view.get("empty") or view.get("balloons"):
        return view
    minx, miny, maxx, maxy = _bbox_of(view)
    span = max(maxy - miny, 1.0)
    width = max(maxx - minx, 1.0)
    count = min(len(rows), 16)
    balloons = []
    for index, row in enumerate(rows[:count]):
        item = row.get("item")
        if item in (None, ""):
            item = index + 1
        balloons.append({
            "item": item,
            "x": minx + width * 0.62,
            "y": miny + span * ((index + 1) / (count + 1)),
            "nx": maxx + width * 0.28,
            "ny": maxy - (index + 0.5) * (span / count),
        })
    copied = dict(view)
    copied["balloons"] = balloons
    return copied


def apply_view_style(view: dict, style: str, annotation_size: float, annotation_style: str) -> dict:
    """Stamp annotation settings, and shade closed profiles when the style asks for it."""
    if not view or view.get("empty"):
        return view or {"empty": True}
    style = view_style_name(style)
    copied = dict(view)
    copied["annotationSize"] = annotation_size
    copied["annotationStyle"] = "bold" if annotation_style == "bold" else "standard"
    colors = _face_colors(style)
    if colors and not copied.get("fills"):
        fills = []
        for path in copied.get("paths") or []:
            pts = path.get("pts") or []
            if len(pts) >= 4 and pts[0] == pts[-1] and (path.get("layer") or "OBJECT") == "OBJECT":
                fills.append({"pts": pts[:-1], "fill": colors[0]})
        if fills:
            copied["fills"] = fills
    if style == "hidden-line":
        paths = []
        for path in copied.get("paths") or []:
            item = dict(path)
            if item.get("hidden") or item.get("layer") == "HIDDEN":
                item["dashed"] = True
                item["layer"] = "HIDDEN"
            paths.append(item)
        copied["paths"] = paths
    if not copied.get("caption"):
        note = _style_caption(style, False)
        if note:
            copied["caption"] = note
    return copied


def _balloon(balloon: dict, p) -> list[Prim]:
    nx, ny = p(_as_float(balloon.get("nx")), _as_float(balloon.get("ny")))
    x, y = p(_as_float(balloon.get("x")), _as_float(balloon.get("y")))
    r = 0.13
    prims = [circle(nx, ny, r, layer="THIN")]
    prims.append(text(nx, ny - 0.035, str(balloon.get("item", "")), size=0.09, anchor="middle", bold=True))
    dx, dy = x - nx, y - ny
    norm = math.hypot(dx, dy) or 1
    prims.append(line(nx + dx / norm * r, ny + dy / norm * r, x, y, layer="THIN"))
    prims.append(solid([(x, y), (x + 0.04, y + 0.025), (x + 0.025, y + 0.045)]))
    return prims
