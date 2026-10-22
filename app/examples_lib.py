"""Worked jobs.

Norstar sheets are rebuilt from the figures in Creating Drawings SOP.
Meridian sheets are sample jobs in that same pattern. The T: drive folders
were not mounted here, so neither set is the live Inventor model.
"""

from __future__ import annotations

import math


def _iso(x, y, z):
    c = math.cos(math.radians(30))
    s = math.sin(math.radians(30))
    return [(x - z) * c, y + (x + z) * s]


def _segs(pairs, layer="OBJECT"):
    return [{"pts": [_iso(*a), _iso(*b)], "layer": layer} for a, b in pairs]


def _ellipse(cx, cy, cz, radius, plane, n=24):
    pts = []
    for i in range(n + 1):
        a = 2 * math.pi * i / n
        if plane == "xz":
            pts.append(_iso(cx + radius * math.cos(a), cy, cz + radius * math.sin(a)))
        elif plane == "yz":
            pts.append(_iso(cx, cy + radius * math.cos(a), cz + radius * math.sin(a)))
        else:
            pts.append(_iso(cx + radius * math.cos(a), cy + radius * math.sin(a), cz))
    return {"pts": pts, "layer": "OBJECT"}


def _balloons(paths, items):
    pts = [pt for path in paths for pt in path.get("pts") or []]
    if not pts or not items:
        return []
    xs = [p[0] for p in pts]
    ys = [p[1] for p in pts]
    span = max(max(xs) - min(xs), max(ys) - min(ys), 1)
    balloons = []
    for index, item in enumerate(items):
        pt = pts[min(len(pts) - 1, int((index + 0.5) * len(pts) / len(items)))]
        balloons.append({
            "item": str(item),
            "x": pt[0],
            "y": pt[1],
            "nx": pt[0] + span * 0.08,
            "ny": pt[1] + span * (0.12 + index * 0.05),
        })
    return balloons


def _base(example_id, group, source, filename, kind, template_id, note, props, model, views, view_count=None):
    rows = [
        {
            "item": str(item.get("item")),
            "partNumber": item.get("partNumber", ""),
            "description": item.get("description", ""),
            "qty": str(item.get("qty", "")),
        }
        for item in model.get("components") or []
    ]
    return {
        "id": example_id,
        "group": group,
        "sourcePath": source,
        "fidelity": "sop-figure" if group.startswith("Norstar") else "sample-job",
        "fileName": filename,
        "fileKind": kind,
        "templateId": template_id,
        "viewCount": view_count or len(views),
        "views": views,
        "properties": props,
        "model": model,
        "bomRows": rows,
        "sample": True,
        "sampleNote": note,
        "warnings": [],
    }


def _props(**kwargs):
    base = {
        "partNumber": "",
        "description": "",
        "material": "",
        "thickness": "",
        "mass": "",
        "rev": "",
        "drawnBy": "",
        "drawnDate": "",
        "designer": "",
        "designerDate": "",
        "checker": "",
        "scale": "SEE ABOVE",
        "sheetNumber": "1",
        "sheetCount": "1",
        "productSeries": "STANDARD DRAWING - IN",
        "customer": "",
        "orderNumber": "",
        "quoteNumber": "",
        "signature": "",
        "signDate": "",
        "extras": {},
    }
    base.update(kwargs)
    return base


def cor438():
    length, width = 9.667, 4.0
    left, right = 2.0, length - 2.0
    flat_paths = [
        {"pts": [[left, 0], [right, 0]], "layer": "OBJECT"},
        {"pts": [[right, width], [left, width]], "layer": "OBJECT"},
        {"pts": [[2.15, 0.15], [2.15, width - 0.15]], "layer": "CENTER", "bend": True},
        {"pts": [[length - 2.15, 0.15], [length - 2.15, width - 0.15]], "layer": "CENTER", "bend": True},
    ]
    flat = {
        "paths": flat_paths,
        "arcs": [
            {"cx": left, "cy": 2, "r": 2, "a0": 90, "a1": 270},
            {"cx": right, "cy": 2, "r": 2, "a0": -90, "a1": 90},
        ],
        "circles": [
            {"cx": 2.690, "cy": 2, "r": 0.55},
            {"cx": length / 2, "cy": 2, "r": 1.05},
            {"cx": length - 2.690, "cy": 2, "r": 0.55},
        ],
        "dims": [
            {"kind": "horizontal", "x1": 0, "x2": length, "y": -0.85, "ext": 0, "text": "9.667"},
            {"kind": "vertical", "y1": 0, "y2": width, "x": -0.85, "ext": 0, "text": "4.000"},
            {"kind": "leader", "x": 2.690, "y": 2.5, "tx": 1.15, "ty": 3.35, "text": "2.690", "anchor": "end"},
            {"kind": "leader", "x": length - 2.690, "y": 2.5, "tx": length - 1.15, "ty": 3.35, "text": "2.690"},
        ],
        "notes": [
            {"x": 2.15, "y": -0.28, "text": "B1", "size": 0.08, "anchor": "middle"},
            {"x": length - 2.15, "y": -0.28, "text": "B2", "size": 0.08, "anchor": "middle"},
        ],
    }
    front = {
        "paths": [
            {"pts": [[0, 3], [0, 0.612]], "layer": "OBJECT"},
            {"pts": [[0.612, 0], [4.263, 0]], "layer": "OBJECT"},
            {"pts": [[4.875, 0.612], [4.875, 3]], "layer": "OBJECT"},
            {"pts": [[0, 3], [0.375, 3]], "layer": "OBJECT"},
            {"pts": [[4.5, 3], [4.875, 3]], "layer": "OBJECT"},
            {"pts": [[0.375, 3], [0.375, 0.612]], "layer": "OBJECT"},
            {"pts": [[0.612, 0.375], [4.263, 0.375]], "layer": "OBJECT"},
            {"pts": [[4.5, 0.612], [4.5, 3]], "layer": "OBJECT"},
        ],
        "arcs": [
            {"cx": 0.612, "cy": 0.612, "r": 0.612, "a0": 180, "a1": 270},
            {"cx": 4.263, "cy": 0.612, "r": 0.612, "a0": 270, "a1": 360},
            {"cx": 0.612, "cy": 0.612, "r": 0.237, "a0": 180, "a1": 270},
            {"cx": 4.263, "cy": 0.612, "r": 0.237, "a0": 270, "a1": 360},
        ],
        "dims": [
            {"kind": "horizontal", "x1": 0, "x2": 4.875, "y": -0.65, "ext": 0, "text": "4.875"},
            {"kind": "vertical", "y1": 0, "y2": 3, "x": -0.7, "ext": 0, "text": "3.000"},
            {"kind": "leader", "x": 0.19, "y": 2.7, "tx": -1.15, "ty": 3.35, "text": "0.375"},
        ],
    }
    side = {
        "paths": [
            {"pts": [[0, 0], [4, 0], [4, 1.15]], "layer": "OBJECT"},
            {"pts": [[0, 1.15], [0, 0]], "layer": "OBJECT"},
        ],
        "arcs": [{"cx": 2, "cy": 1.15, "r": 2, "a0": 0, "a1": 180}],
        "circles": [{"cx": 2, "cy": 1.55, "r": 0.62}],
        "dims": [
            {"kind": "horizontal", "x1": 0, "x2": 4, "y": -0.6, "ext": 0, "text": "4.000"},
        ],
    }
    pairs = []
    # Outer U at z=0 and z=4, plus depth edges.
    outer = [(0, 3, 0), (0, 0.62, 0), (0.62, 0, 0), (4.26, 0, 0), (4.875, 0.62, 0), (4.875, 3, 0)]
    for z in (0, 4):
        ring = [(p[0], p[1], z) for p in outer]
        pairs.extend(zip(ring, ring[1:]))
    for px, py, _ in outer:
        pairs.append(((px, py, 0), (px, py, 4)))
    pairs.append(((0, 3, 0), (0.375, 3, 0)))
    pairs.append(((0, 3, 4), (0.375, 3, 4)))
    pairs.append(((4.5, 3, 0), (4.875, 3, 0)))
    pairs.append(((4.5, 3, 4), (4.875, 3, 4)))
    iso_paths = _segs(pairs)
    iso_paths.append(_ellipse(2.69, 1.6, 0.02, 0.45, "yz"))
    iso_paths.append(_ellipse(4.875 / 2, 0.02, 2.0, 0.85, "xz"))
    model = {
        "kind": "part",
        "overall": {"length": 9.667, "width": 4.0, "height": 3.0},
        "bends": [
            {"id": "1", "direction": "UP", "angle": "90", "radius": ".237"},
            {"id": "2", "direction": "UP", "angle": "90", "radius": ".237"},
        ],
        "views": {"flat": flat, "front": front, "side": side, "iso": {"paths": iso_paths}},
    }
    return _base(
        "norstar-cor438",
        "Norstar Ind.",
        r"T:\Engineering\Custom Projects\Norstar Ind.",
        "COR438 Center Pivot Plate.ipt",
        "ipt",
        "norstar-part",
        "SAMPLE — REBUILT FROM THE CREATING DRAWINGS SOP FIGURE. CONFIRM AGAINST THE INVENTOR MODEL BEFORE ISSUE.",
        _props(
            partNumber="COR438",
            description="C013718 Center Pivot Plate",
            material="Steel",
            thickness="0.375",
            mass="8.85 lbmass",
            drawnBy="Daniel Waldner",
            drawnDate="2025-07-08",
            designer="Randy Martens",
            designerDate="2009-03-10",
        ),
        model,
        ["flat", "front", "side", "iso"],
    )


def grt661():
    side = {
        "paths": [
            {"pts": [[0, 0], [119, 0], [119, 9.5], [0, 9.5], [0, 0]], "layer": "OBJECT"},
            {"pts": [[0, 8.3], [119, 8.3]], "layer": "THIN"},
            {"pts": [[0, 1.5], [119, 1.5]], "layer": "THIN"},
        ],
        "dims": [
            {"kind": "horizontal", "x1": 0, "x2": 119, "y": -1.4, "ext": 0, "text": "119.000"},
            {"kind": "vertical", "y1": 0, "y2": 9.5, "x": -1.6, "ext": 0, "text": "9.500"},
            {"kind": "leader", "x": 18, "y": 8.3, "tx": 18, "ty": 11.2, "text": "(Ø0.266)"},
        ],
        "welds": [
            {"x": 2, "y": 9.5, "tx": 8, "ty": 12, "size": "1/8", "tail": ""},
            {"x": 60, "y": 0.2, "tx": 68, "ty": -3.2, "size": "1/8", "tail": "TYP"},
        ],
        "balloons": [
            {"item": "2", "x": 70, "y": 5, "nx": 70, "ny": 13},
            {"item": "1", "x": 20, "y": 8.3, "nx": 28, "ny": 13.5},
        ],
    }
    end = {
        "paths": [
            {"pts": [[0, 0], [10, 0], [10, 9.5], [0, 9.5], [0, 0]], "layer": "OBJECT"},
            {"pts": [[1.5, 9.5], [1.5, 5]], "layer": "OBJECT"},
            {"pts": [[8.5, 5], [8.5, 9.5]], "layer": "OBJECT"},
        ],
        "arcs": [{"cx": 5, "cy": 5, "r": 3.5, "a0": 180, "a1": 360}],
        "dims": [
            {"kind": "horizontal", "x1": 0, "x2": 10, "y": -1.3, "ext": 0, "text": "10.000"},
            {"kind": "leader", "x": 8.5, "y": 5, "tx": 12.2, "ty": 7.2, "text": "Ø7.000"},
            {"kind": "leader", "x": 8.5, "y": 7.4, "tx": 12.2, "ty": 9.4, "text": "(Ø0.406)"},
        ],
        "balloons": [{"item": "3", "x": 1.2, "y": 9.2, "nx": -1.6, "ny": 11.4}],
    }
    detail = {
        "paths": [
            {"pts": [[0, 0], [3.2, 0], [3.2, 2.4], [0, 2.4], [0, 0]], "layer": "OBJECT"},
            {"pts": [[0.35, 0.35], [2.85, 0.35], [2.85, 2.05], [0.35, 2.05], [0.35, 0.35]], "layer": "THIN"},
        ],
        "notes": [
            {"x": 1.6, "y": 3.1, "text": "FLUSHED ON\nBOTH ENDS", "size": 0.09, "anchor": "middle"},
        ],
        "scale": "DETAIL A",
    }
    body = _segs([
        ((0, 0, 0), (119, 0, 0)),
        ((119, 0, 0), (119, 9.5, 0)),
        ((119, 9.5, 0), (0, 9.5, 0)),
        ((0, 9.5, 0), (0, 0, 0)),
        ((0, 0, 10), (119, 0, 10)),
        ((119, 0, 10), (119, 9.5, 10)),
        ((119, 9.5, 10), (0, 9.5, 10)),
        ((0, 9.5, 10), (0, 0, 10)),
        ((0, 0, 0), (0, 0, 10)),
        ((119, 0, 0), (119, 0, 10)),
        ((119, 9.5, 0), (119, 9.5, 10)),
        ((0, 9.5, 0), (0, 9.5, 10)),
    ])
    components = [
        {"item": "1", "partNumber": "14390", "description": '3/8" Weldnut', "qty": "6"},
        {"item": "2", "partNumber": "GRT662", "description": "CO20168 CCRB Inter Section Body 6in 10ga 10ft", "qty": "1"},
        {"item": "3", "partNumber": "GRT663", "description": "CO20168 CCRB Flange Inter 6in", "qty": "2"},
    ]
    model = {
        "kind": "weldment",
        "overall": {"length": 119.0, "width": 10.0, "height": 9.5},
        "welds": [{"size": "1/8", "type": "fillet", "note": "TYP"}],
        "components": components,
        "views": {"side": side, "end": end, "detail": detail, "iso": {"paths": body}},
    }
    return _base(
        "norstar-grt661",
        "Norstar Ind.",
        r"T:\Engineering\Custom Projects\Norstar Ind.",
        "GRT661 CCRB Body Weld.iam",
        "iam",
        "norstar-weldment",
        "SAMPLE — REBUILT FROM THE CREATING DRAWINGS SOP FIGURE. CONFIRM AGAINST THE INVENTOR MODEL BEFORE ISSUE.",
        _props(
            partNumber="GRT661",
            description="CO20168 CCRB Body Weld 6in 10ft 10Ga",
            material="Steel",
            drawnBy="Lei Zhang",
            drawnDate="2026-03-09",
            designer="Timothy Cummer",
            designerDate="2024-08-15",
        ),
        model,
        ["side", "end", "detail", "iso"],
    )


def grt647():
    side = {
        "paths": [
            {"pts": [[0, 0], [37.76, 0], [37.76, 8.2], [20, 12.33], [0, 12.33], [0, 0]], "layer": "OBJECT"},
            {"pts": [[0.513, 0], [0.513, 12.33]], "layer": "THIN"},
            {"pts": [[6, 3.2], [16, 3.2], [16, 9.2], [6, 9.2], [6, 3.2]], "layer": "OBJECT"},
        ],
        "dims": [
            {"kind": "horizontal", "x1": 0, "x2": 37.76, "y": -1.6, "ext": 0, "text": "37.760"},
            {"kind": "horizontal", "x1": 0, "x2": 20, "y": 13.4, "ext": 12.33, "text": "20.000"},
            {"kind": "horizontal", "x1": 0, "x2": 0.513, "y": -0.7, "ext": 0, "text": "0.513"},
            {"kind": "vertical", "y1": 0, "y2": 12.33, "x": -1.5, "ext": 0, "text": "12.330"},
        ],
    }
    top = {
        "paths": [
            {"pts": [[0, 0], [37.76, 0], [37.76, 10], [0, 10], [0, 0]], "layer": "OBJECT"},
            {"pts": [[0, 0.8], [37.76, 0.8]], "layer": "THIN"},
            {"pts": [[0, 9.2], [37.76, 9.2]], "layer": "THIN"},
        ],
        "circles": [{"cx": 4 + i * 5.2, "cy": 5, "r": 0.18} for i in range(6)],
        "dims": [
            {"kind": "vertical", "y1": 0, "y2": 10, "x": -1.2, "ext": 0, "text": "10.000"},
            {"kind": "leader", "x": 30, "y": 9.2, "tx": 33, "ty": 12, "text": "(Ø0.397)"},
        ],
    }
    end = {
        "paths": [
            {"pts": [[0, 0], [10, 0], [10, 12.33], [0, 12.33], [0, 0]], "layer": "OBJECT"},
            {"pts": [[1.5, 12.33], [1.5, 5.2]], "layer": "OBJECT"},
            {"pts": [[8.5, 5.2], [8.5, 12.33]], "layer": "OBJECT"},
        ],
        "arcs": [{"cx": 5, "cy": 5.2, "r": 3.5, "a0": 180, "a1": 360}],
        "dims": [
            {"kind": "vertical", "y1": 0, "y2": 12.33, "x": -1.4, "ext": 0, "text": "12.330"},
            {"kind": "leader", "x": 8.5, "y": 5.2, "tx": 12, "ty": 7.5, "text": "Ø7.000"},
            {"kind": "leader", "x": 9.2, "y": 9.5, "tx": 12, "ty": 10.2, "text": "(Ø0.406)"},
        ],
    }
    profile = [(0, 0), (37.76, 0), (37.76, 8.2), (20, 12.33), (0, 12.33)]
    pairs = []
    for z in (0, 10):
        ring = [(px, py, z) for px, py in profile]
        pairs.extend(zip(ring, ring[1:] + ring[:1]))
    for px, py in profile:
        pairs.append(((px, py, 0), (px, py, 10)))
    iso_paths = _segs(pairs)
    balloons = _balloons(iso_paths, ["1", "2", "3", "4", "5", "6"])
    components = [
        {"item": "1", "partNumber": "GRT654", "description": "CCRB Head Cover 10ga x 6in x 10ft", "qty": "1"},
        {"item": "2", "partNumber": "GRT656", "description": "CO20168 CCRB Tail Transition Body Cover", "qty": "1"},
        {"item": "3", "partNumber": "GRT660", "description": "CO20168 CCRB Head Paddle Rail WLDT", "qty": "1"},
        {"item": "4", "partNumber": "GRT672", "description": "CO20168 CCRB Cover Connector End Section to Transition", "qty": "1"},
        {"item": "5", "partNumber": "GRT686", "description": "CO20168 CCRB Head Weldment 6in", "qty": "1"},
        {"item": "6", "partNumber": "GRT687", "description": "CO20168 CCRB Tail Transition Body WLDT", "qty": "1"},
    ]
    model = {
        "kind": "assembly",
        "overall": {"length": 37.76, "width": 10.0, "height": 12.33},
        "components": components,
        "views": {
            "side": side,
            "top": top,
            "end": end,
            "iso": {"paths": iso_paths, "balloons": balloons},
        },
    }
    return _base(
        "norstar-grt647",
        "Norstar Ind.",
        r"T:\Engineering\Custom Projects\Norstar Ind.",
        "GRT647 CCRB Head Section Assembly.iam",
        "iam",
        "norstar-assembly",
        "SAMPLE — REBUILT FROM THE CREATING DRAWINGS SOP FIGURE. CONFIRM AGAINST THE INVENTOR MODEL BEFORE ISSUE.",
        _props(
            partNumber="GRT647",
            description="CO20168 CCRB Head Section Assembly",
            material="Steel",
            drawnBy="Lei Zhang",
            drawnDate="2026-03-05",
            designer="Lei Zhang",
            designerDate="2026-03-05",
        ),
        model,
        ["side", "top", "end", "iso"],
    )


def _flange(opening_note="8X Ø0.438 THRU"):
    outer, inner = 10.625, 8.125
    inset = (outer - inner) / 2
    holes = []
    for cx, cy in (
        (0.7, 0.7), (outer - 0.7, 0.7), (0.7, outer - 0.7), (outer - 0.7, outer - 0.7),
        (outer / 2, 0.7), (outer / 2, outer - 0.7), (0.7, outer / 2), (outer - 0.7, outer / 2),
    ):
        holes.append({"cx": cx, "cy": cy, "r": 0.219})
    return {
        "paths": [
            {"pts": [[0, 0], [outer, 0], [outer, outer], [0, outer], [0, 0]], "layer": "OBJECT"},
            {"pts": [[inset, inset], [outer - inset, inset], [outer - inset, outer - inset], [inset, outer - inset], [inset, inset]], "layer": "OBJECT"},
        ],
        "circles": holes,
        "dims": [
            {"kind": "horizontal", "x1": 0, "x2": outer, "y": -1.1, "ext": 0, "text": "10.625"},
            {"kind": "horizontal", "x1": inset, "x2": outer - inset, "y": outer + 0.8, "ext": outer, "text": "8.125"},
            {"kind": "leader", "x": outer - 0.7, "y": outer / 2, "tx": outer + 1.4, "ty": outer * 0.72, "text": opening_note},
        ],
    }


def _conveyor_side(sections, height, discharge_at):
    total = sum(length for _, length in sections)
    paths = [{"pts": [[0, 0], [total, 0], [total, height], [0, height], [0, 0]], "layer": "OBJECT"}]
    # Flighting zig-zag along the lower third. Kept coarse so the sheet stays readable.
    teeth = []
    x = 0
    pitch = max(total / 48, 4)
    up = False
    while x <= total:
        teeth.append([x, 1.2 if up else 0.35])
        up = not up
        x += pitch
    paths.append({"pts": teeth, "layer": "THIN"})
    cursor = 0
    dims = [
        {"kind": "horizontal", "x1": 0, "x2": total, "y": -6.5, "ext": 0, "text": f"{total:.2f}"},
        {"kind": "vertical", "y1": 0, "y2": height, "x": -4.5, "ext": 0, "text": f"{height:.2f}"},
    ]
    notes = [{"x": total / 2, "y": -5.3, "text": "OVERALL LENGTH", "size": 0.09, "anchor": "middle"}]
    for label, length in sections:
        dims.append({
            "kind": "horizontal",
            "x1": cursor,
            "x2": cursor + length,
            "y": -3.2,
            "ext": 0,
            "text": f"{length:.2f}",
        })
        notes.append({
            "x": cursor + length / 2,
            "y": height + 2.4,
            "text": label,
            "size": 0.09,
            "anchor": "middle",
            "bold": True,
        })
        if cursor:
            paths.append({"pts": [[cursor, 0], [cursor, height]], "layer": "THIN"})
        cursor += length
    # Center discharge opening.
    opening = 18
    dx = discharge_at - opening / 2
    paths.append({"pts": [[dx, 0], [dx, 2.2], [dx + opening, 2.2], [dx + opening, 0]], "layer": "OBJECT"})
    notes.append({"x": discharge_at, "y": -1.5, "text": "CENTER DISCHARGE", "size": 0.08, "anchor": "middle"})
    notes.append({"x": -2, "y": height + 2.4, "text": "DISCHARGE\nHEIGHT", "size": 0.08, "anchor": "end"})
    return {"paths": paths, "dims": dims, "notes": notes}


def avf002():
    sections = [("HEAD SECTION", 168), ("INTERMEDIATE SECTION", 236), ("INTERMEDIATE SECTION", 168)]
    side = _conveyor_side(sections, 36.42, 168 + 118)
    front = {
        "paths": [
            {"pts": [[0, 0], [22.66, 0], [22.66, 36.42], [0, 36.42], [0, 0]], "layer": "OBJECT"},
        ],
        "circles": [{"cx": 11.33, "cy": 22, "r": 6.2}],
        "dims": [
            {"kind": "horizontal", "x1": 0, "x2": 22.66, "y": -2.2, "ext": 0, "text": "22.66"},
            {"kind": "vertical", "y1": 0, "y2": 36.42, "x": -2.4, "ext": 0, "text": "36.42"},
        ],
        "notes": [{"x": 11.33, "y": 38, "text": "HEAD END", "size": 0.09, "anchor": "middle"}],
    }
    section = {
        "paths": [
            {"pts": [[0, 0], [22.66, 0], [22.66, 36.42], [0, 36.42], [0, 0]], "layer": "OBJECT"},
            {"pts": [[3, 4], [19.66, 4]], "layer": "OBJECT"},
            {"pts": [[3, 4], [3, 30], [19.66, 30], [19.66, 4]], "layer": "THIN"},
        ],
        "circles": [{"cx": 11.33, "cy": 8, "r": 3.1}],
        "hatch": [{"x": 0.4, "y": 0.4, "w": 1.3, "h": 35.6, "gap": 0.55}, {"x": 20.96, "y": 0.4, "w": 1.3, "h": 35.6, "gap": 0.55}],
        "dims": [
            {"kind": "horizontal", "x1": 0, "x2": 22.66, "y": -2.2, "ext": 0, "text": "22.66"},
            {"kind": "vertical", "y1": 0, "y2": 36.42, "x": -2.4, "ext": 0, "text": "36.42"},
        ],
    }
    model = {
        "kind": "signoff",
        "overall": {"length": 572, "width": 22.66, "height": 36.42},
        "sections": [{"label": label, "length": length} for label, length in sections],
        "views": {
            "side": side,
            "front": front,
            "section": section,
            "inlet": _flange(),
            "discharge": _flange(),
        },
    }
    return _base(
        "norstar-avf002",
        "Norstar Ind.",
        r"T:\Engineering\Custom Projects\Norstar Ind.",
        "AVF002 AVF CJT Conv Assy.iam",
        "iam",
        "norstar-signoff",
        "SAMPLE — REBUILT FROM THE CREATING DRAWINGS SOP FIGURE. CONFIRM AGAINST THE INVENTOR MODEL BEFORE ISSUE.",
        _props(
            partNumber="AVF002",
            description="AVF CJT Conv Assy 8in x 1in",
            material="Steel",
            productSeries="STANDARD DRAWING - IN",
            drawnBy="Timothy Cummer",
            drawnDate="2021-11-12",
            designer="Timothy Cummer",
            designerDate="2021-07-01",
            customer="AVENA FOODS LIMITED",
            orderNumber="CU20083",
            quoteNumber="",
            extras={
                "project": "CU20083",
                "construction": "STEEL",
                "head": "STEEL",
                "tail": "STEEL",
            },
        ),
        model,
        ["side", "front", "section", "inlet", "discharge"],
    )


def meridian_slide():
    flat = {
        "paths": [
            {"pts": [[0, 0], [12, 0], [12, 6], [0, 6], [0, 0]], "layer": "OBJECT"},
            {"pts": [[4.0, 0.15], [4.0, 5.85]], "layer": "CENTER", "bend": True},
        ],
        "circles": [{"cx": 8.5, "cy": 3, "r": 0.75}, {"cx": 2, "cy": 1.25, "r": 0.28}, {"cx": 2, "cy": 4.75, "r": 0.28}],
        "dims": [
            {"kind": "horizontal", "x1": 0, "x2": 12, "y": -0.8, "ext": 0, "text": "12.000"},
            {"kind": "vertical", "y1": 0, "y2": 6, "x": -0.8, "ext": 0, "text": "6.000"},
        ],
        "notes": [{"x": 4, "y": 6.35, "text": "B1", "size": 0.08, "anchor": "middle"}],
    }
    front = {
        "paths": [
            {"pts": [[0, 0], [4, 0], [4, 3.25], [4.1345, 3.25], [4.1345, 0.1345], [0.1345, 0.1345], [0.1345, 3.25], [0, 3.25], [0, 0]], "layer": "OBJECT"},
        ],
        "dims": [
            {"kind": "horizontal", "x1": 0, "x2": 4, "y": -0.6, "ext": 0, "text": "4.000"},
            {"kind": "vertical", "y1": 0, "y2": 3.25, "x": -0.65, "ext": 0, "text": "3.250"},
            {"kind": "leader", "x": 4.06, "y": 2.4, "tx": 5.1, "ty": 3.3, "text": "0.1345"},
        ],
    }
    iso = {"paths": _segs([
        ((0, 0, 0), (4, 0, 0)), ((4, 0, 0), (4, 3.25, 0)), ((4, 3.25, 0), (0, 3.25, 0)), ((0, 3.25, 0), (0, 0, 0)),
        ((0, 0, 6), (4, 0, 6)), ((4, 0, 6), (4, 3.25, 6)), ((4, 3.25, 6), (0, 3.25, 6)), ((0, 3.25, 6), (0, 0, 6)),
        ((0, 0, 0), (0, 0, 6)), ((4, 0, 0), (4, 0, 6)), ((4, 3.25, 0), (4, 3.25, 6)), ((0, 3.25, 0), (0, 3.25, 6)),
    ])}
    model = {
        "kind": "part",
        "overall": {"length": 12, "width": 6, "height": 3.25},
        "bends": [{"id": "1", "direction": "UP", "angle": "90", "radius": ".125"}],
        "views": {"flat": flat, "front": front, "side": {
            "paths": [{"pts": [[0, 0], [6, 0], [6, 3.25], [0, 3.25], [0, 0]], "layer": "OBJECT"}],
            "dims": [{"kind": "horizontal", "x1": 0, "x2": 6, "y": -0.55, "ext": 0, "text": "6.000"}],
        }, "iso": iso},
    }
    return _base(
        "meridian-me4412",
        "Meridian",
        r"T:\Engineering\Custom Projects\Meridian",
        "ME-4412 Inlet Slide.ipt",
        "ipt",
        "meridian-part",
        "SAMPLE JOB IN THE MERIDIAN CUSTOM-PROJECT PATTERN. NOT A RELEASED DRAWING.",
        _props(
            partNumber="ME-4412",
            description="Inlet Slide",
            material="Steel",
            thickness="10 GA",
            mass="",
            productSeries="CUSTOM PROJECT",
            drawnBy="",
            designer="",
        ),
        model,
        ["flat", "front", "side", "iso"],
    )


def meridian_utrough():
    sections = [("INLET", 120), ("TROUGH", 480), ("DISCHARGE", 120)]
    side = _conveyor_side(sections, 18, 120 + 240)
    section = {
        "paths": [
            {"pts": [[0, 0], [16.5, 0], [16.5, 18], [0, 18], [0, 0]], "layer": "OBJECT"},
            {"pts": [[1.25, 18], [1.25, 8]], "layer": "OBJECT"},
            {"pts": [[15.25, 8], [15.25, 18]], "layer": "OBJECT"},
        ],
        "arcs": [{"cx": 8.25, "cy": 8, "r": 7, "a0": 180, "a1": 360}],
        "dims": [
            {"kind": "horizontal", "x1": 0, "x2": 16.5, "y": -1.4, "ext": 0, "text": "16.500"},
            {"kind": "vertical", "y1": 0, "y2": 18, "x": -1.6, "ext": 0, "text": "18.000"},
            {"kind": "leader", "x": 15.25, "y": 8, "tx": 18.5, "ty": 11, "text": "Ø14.000"},
        ],
    }
    model = {
        "kind": "signoff",
        "overall": {"length": 720, "width": 16.5, "height": 18},
        "sections": [{"label": label, "length": length} for label, length in sections],
        "views": {"side": side, "section": section, "inlet": _flange("4X Ø0.500 THRU"), "discharge": _flange("4X Ø0.500 THRU")},
    }
    return _base(
        "meridian-ut140",
        "Meridian",
        r"T:\Engineering\Custom Projects\Meridian",
        "ME-UT-140 U-Trough Signoff.iam",
        "iam",
        "meridian-signoff-utrough",
        "SAMPLE JOB IN THE MERIDIAN CUSTOM-PROJECT PATTERN. NOT A RELEASED DRAWING.",
        _props(
            partNumber="ME-UT-140",
            description="14 in U-Trough Signoff",
            material="Steel",
            productSeries="CUSTOM PROJECT",
            customer="Sample Grain Cooperative",
            orderNumber="M-10482",
            quoteNumber="Q-7781",
            extras={"diameter": '14"', "capacity": "4500 bu/hr", "speed": "180 RPM", "construction": "STEEL", "cover": "BOLTED"},
        ),
        model,
        ["side", "section", "inlet", "discharge"],
    )


def meridian_elevator():
    # Broken elevation: boot, a short stand-in for the leg, and the head.
    paths = [
        {"pts": [[0, 0], [20, 0], [20, 8], [0, 8], [0, 0]], "layer": "OBJECT"},
        {"pts": [[2, 8], [2, 22], [18, 22], [18, 8]], "layer": "OBJECT"},
        {"pts": [[0, 22], [20, 22], [20, 30], [0, 30], [0, 22]], "layer": "OBJECT"},
        {"pts": [[1, 14], [3, 15], [1, 16], [3, 17]], "layer": "OBJECT"},
        {"pts": [[17, 14], [19, 15], [17, 16], [19, 17]], "layer": "OBJECT"},
    ]
    side = {
        "paths": paths,
        "circles": [{"cx": 10, "cy": 26, "r": 3.2}, {"cx": 10, "cy": 4, "r": 2.4}],
        "dims": [
            {"kind": "vertical", "y1": 0, "y2": 8, "x": -2.2, "ext": 0, "text": "48.00"},
            {"kind": "vertical", "y1": 8, "y2": 22, "x": -2.2, "ext": 0, "text": "240.00"},
            {"kind": "vertical", "y1": 22, "y2": 30, "x": -2.2, "ext": 0, "text": "36.00"},
            {"kind": "vertical", "y1": 0, "y2": 30, "x": -4.4, "ext": 0, "text": "324.00"},
            {"kind": "horizontal", "x1": 0, "x2": 20, "y": -1.6, "ext": 0, "text": "18.00"},
        ],
        "notes": [
            {"x": 10, "y": 8.4, "text": "BOOT", "size": 0.09, "anchor": "middle"},
            {"x": 10, "y": 18, "text": "LEG — LENGTH BROKEN", "size": 0.09, "anchor": "middle"},
            {"x": 10, "y": 30.8, "text": "HEAD", "size": 0.09, "anchor": "middle"},
            {"x": 22, "y": 28, "text": "OVERALL HEIGHT", "size": 0.08},
        ],
    }
    section = {
        "paths": [{"pts": [[0, 0], [18, 0], [18, 14], [0, 14], [0, 0]], "layer": "OBJECT"}],
        "hatch": [{"x": 0.35, "y": 0.35, "w": 0.8, "h": 13.3, "gap": 0.4}, {"x": 16.85, "y": 0.35, "w": 0.8, "h": 13.3, "gap": 0.4}],
        "dims": [
            {"kind": "horizontal", "x1": 0, "x2": 18, "y": -1.3, "ext": 0, "text": "18.00"},
            {"kind": "vertical", "y1": 0, "y2": 14, "x": -1.5, "ext": 0, "text": "14.00"},
        ],
    }
    model = {
        "kind": "signoff",
        "overall": {"length": 18, "width": 14, "height": 324},
        "sections": [
            {"label": "BOOT", "length": 48},
            {"label": "LEG", "length": 240},
            {"label": "HEAD", "length": 36},
        ],
        "views": {"side": side, "section": section, "inlet": _flange("INLET"), "discharge": _flange("DISCHARGE")},
    }
    return _base(
        "meridian-be220",
        "Meridian",
        r"T:\Engineering\Custom Projects\Meridian",
        "ME-BE-220 Bucket Elevator Signoff.iam",
        "iam",
        "meridian-signoff-elevator",
        "SAMPLE JOB IN THE MERIDIAN CUSTOM-PROJECT PATTERN. NOT A RELEASED DRAWING. LEG LENGTH IS BROKEN.",
        _props(
            partNumber="ME-BE-220",
            description="Bucket Elevator Signoff",
            material="Steel",
            productSeries="CUSTOM PROJECT",
            customer="Sample Grain Cooperative",
            orderNumber="M-22014",
            quoteNumber="Q-1904",
            extras={
                "capacity": "4000 bu/hr",
                "belt": "500 FPM",
                "bucket": "12 x 7",
                "casing": "18 x 14",
                "head": "24 in PULLEY",
                "boot": "18 in PULLEY",
            },
        ),
        model,
        ["side", "section", "inlet", "discharge"],
    )


def all_examples() -> list[dict]:
    return [cor438(), grt661(), grt647(), avf002(), meridian_slide(), meridian_utrough(), meridian_elevator()]


def example_by_id(example_id: str) -> dict | None:
    for example in all_examples():
        if example["id"] == example_id:
            return example
    return None
