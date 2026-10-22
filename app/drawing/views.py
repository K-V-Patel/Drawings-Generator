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


def envelope_view(role: str, overall: dict) -> dict:
    length = _as_float(overall.get("length"))
    width = _as_float(overall.get("width"))
    height = _as_float(overall.get("height"))
    if length <= 0 or width <= 0 or height <= 0:
        return {"empty": True}
    if role in {"front", "back"}:
        w, h = length, height
    elif role in {"side", "end", "section"}:
        w, h = width, height
    elif role in {"top", "bottom", "flat"}:
        w, h = length, width
    elif role == "iso":
        return _iso_box(length, width, height)
    else:
        w, h = length, height
    pad_x = max(w * 0.12, 0.4)
    pad_y = max(h * 0.18, 0.45)
    return {
        "paths": [{"pts": [[0, 0], [w, 0], [w, h], [0, h], [0, 0]], "layer": "OBJECT"}],
        "dims": [
            {"kind": "horizontal", "x1": 0, "x2": w, "y": -pad_y, "ext": 0, "text": _fmt(w)},
            {"kind": "vertical", "y1": 0, "y2": h, "x": -pad_x, "ext": 0, "text": _fmt(h)},
        ],
        "caption": "ENVELOPE",
    }


def _iso_box(length: float, width: float, height: float) -> dict:
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
    paths = [{"pts": [corners[a], corners[b]], "layer": "OBJECT"} for a, b in edges]
    return {"paths": paths, "caption": "ENVELOPE"}


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

    for path in view.get("paths") or []:
        pts = [p(px, py) for px, py in path.get("pts") or []]
        if len(pts) >= 2:
            layer = path.get("layer") or "OBJECT"
            prims.append(poly(pts, layer=layer, dashed=layer == "CENTER"))
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
        prims.extend(_dim(dim, p))
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


def _dim(dim: dict, p) -> list[Prim]:
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
        prims.append(text(mx + ox, my + oy, dim.get("text", ""), size=0.085, anchor="middle"))
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
        prims.append(text(mx + ox, my + oy, dim.get("text", ""), size=0.085, anchor=anchor))
    elif kind == "leader":
        x, y = p(_as_float(dim["x"]), _as_float(dim["y"]))
        tx, ty = p(_as_float(dim["tx"]), _as_float(dim["ty"]))
        prims.append(line(tx, ty, x, y, layer="DIM"))
        prims.append(_arrow(x, y, tx, ty))
        prims.append(text(tx, ty + 0.03, dim.get("text", ""), size=0.085, anchor=dim.get("anchor", "start")))
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
