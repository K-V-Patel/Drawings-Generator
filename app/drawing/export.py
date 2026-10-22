"""Write a primitive list to SVG, PDF, and DXF."""

from __future__ import annotations

import math
from xml.sax.saxutils import escape

from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.pdfgen import canvas as pdfcanvas

from app.drawing.prims import LAYER_PX, Prim

_FONT = "NotoSans"
_FONT_BOLD = "NotoSans-Bold"
_FONTS_READY = False


def _fonts() -> None:
    global _FONTS_READY
    if _FONTS_READY:
        return
    pdfmetrics.registerFont(TTFont(_FONT, "/usr/share/fonts/truetype/noto/NotoSans-Regular.ttf"))
    pdfmetrics.registerFont(TTFont(_FONT_BOLD, "/usr/share/fonts/truetype/noto/NotoSans-Bold.ttf"))
    _FONTS_READY = True


def _arc_points(cx: float, cy: float, r: float, a0: float, a1: float, steps: int = 28) -> list[tuple[float, float]]:
    sweep = a1 - a0
    if sweep <= 0:
        sweep += 360
    pts = []
    n = max(6, int(steps * sweep / 360))
    for i in range(n + 1):
        a = math.radians(a0 + sweep * i / n)
        pts.append((cx + r * math.cos(a), cy + r * math.sin(a)))
    return pts


def to_svg(prims: list[Prim], width: float, height: float) -> str:
    parts = [
        f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {width:.4f} {height:.4f}" '
        f'width="100%" height="100%" role="img">',
        "<rect width='100%' height='100%' fill='#fbfaf6'/>",
        f'<g transform="translate(0 {height:.4f}) scale(1 -1)" fill="none" stroke="#1b1916" '
        f'stroke-linecap="round" stroke-linejoin="round">',
    ]
    for prim in prims:
        if prim.op == "line":
            dash = ' stroke-dasharray="4 3"' if prim.dashed or prim.layer == "CENTER" else ""
            parts.append(
                f'<line x1="{prim.x1:.4f}" y1="{prim.y1:.4f}" x2="{prim.x2:.4f}" y2="{prim.y2:.4f}" '
                f'stroke-width="{LAYER_PX.get(prim.layer, 1)}px" vector-effect="non-scaling-stroke"{dash}/>'
            )
        elif prim.op == "rect":
            parts.append(
                f'<rect x="{prim.x1:.4f}" y="{prim.y1:.4f}" width="{prim.x2:.4f}" height="{prim.y2:.4f}" '
                f'stroke-width="{LAYER_PX.get(prim.layer, 1)}px" vector-effect="non-scaling-stroke"/>'
            )
        elif prim.op == "circle":
            dash = ' stroke-dasharray="4 3"' if prim.layer == "CENTER" else ""
            parts.append(
                f'<circle cx="{prim.x1:.4f}" cy="{prim.y1:.4f}" r="{prim.r:.4f}" '
                f'stroke-width="{LAYER_PX.get(prim.layer, 1)}px" vector-effect="non-scaling-stroke"{dash}/>'
            )
        elif prim.op == "arc":
            pts = _arc_points(prim.x1, prim.y1, prim.r, prim.a0, prim.a1)
            d = " ".join(f"{x:.4f},{y:.4f}" for x, y in pts)
            parts.append(
                f'<polyline points="{d}" stroke-width="{LAYER_PX.get(prim.layer, 1)}px" '
                f'vector-effect="non-scaling-stroke"/>'
            )
        elif prim.op == "poly":
            d = " ".join(f"{x:.4f},{y:.4f}" for x, y in prim.pts)
            dash = ' stroke-dasharray="5 3"' if prim.dashed or prim.layer == "CENTER" else ""
            parts.append(
                f'<polyline points="{d}" stroke-width="{LAYER_PX.get(prim.layer, 1)}px" '
                f'vector-effect="non-scaling-stroke"{dash}/>'
            )
        elif prim.op == "solid":
            d = " ".join(f"{x:.4f},{y:.4f}" for x, y in prim.pts)
            parts.append(f'<polygon points="{d}" fill="#1b1916" stroke="none"/>')
        elif prim.op == "text" and prim.text:
            weight = "700" if prim.bold else "500"
            anchor = {"start": "start", "middle": "middle", "end": "end"}.get(prim.anchor, "start")
            lines = str(prim.text).split("\n")
            for i, line_text in enumerate(lines):
                yy = prim.y1 - i * prim.size * 1.25
                parts.append(
                    f'<g transform="translate({prim.x1:.4f} {yy:.4f}) scale(1 -1)">'
                    f'<text x="0" y="0" fill="#1b1916" stroke="none" '
                    f'font-family="Inter, Noto Sans, sans-serif" font-weight="{weight}" '
                    f'font-size="{prim.size:.4f}" text-anchor="{anchor}">{escape(line_text)}</text></g>'
                )
    parts.append("</g></svg>")
    return "".join(parts)


def to_pdf(prims: list[Prim], width: float, height: float, title: str = "Drawing") -> bytes:
    _fonts()
    from io import BytesIO

    buf = BytesIO()
    c = pdfcanvas.Canvas(buf, pagesize=(width * 72, height * 72))
    c.setTitle(title)
    c.setFillColorRGB(0.106, 0.098, 0.086)
    c.setStrokeColorRGB(0.106, 0.098, 0.086)

    def X(v: float) -> float:
        return v * 72

    def Y(v: float) -> float:
        return v * 72

    for prim in prims:
        c.setLineWidth(max(0.15, prim.weight * 72))
        c.setDash(1.6, 1.2) if (prim.dashed or prim.layer == "CENTER") else c.setDash()
        if prim.op == "line":
            c.line(X(prim.x1), Y(prim.y1), X(prim.x2), Y(prim.y2))
        elif prim.op == "rect":
            c.rect(X(prim.x1), Y(prim.y1), X(prim.x2), Y(prim.y2), stroke=1, fill=0)
        elif prim.op == "circle":
            c.circle(X(prim.x1), Y(prim.y1), X(prim.r), stroke=1, fill=0)
        elif prim.op == "arc":
            pts = _arc_points(prim.x1, prim.y1, prim.r, prim.a0, prim.a1)
            path = c.beginPath()
            path.moveTo(X(pts[0][0]), Y(pts[0][1]))
            for px, py in pts[1:]:
                path.lineTo(X(px), Y(py))
            c.drawPath(path, stroke=1, fill=0)
        elif prim.op == "poly":
            if len(prim.pts) < 2:
                continue
            path = c.beginPath()
            path.moveTo(X(prim.pts[0][0]), Y(prim.pts[0][1]))
            for px, py in prim.pts[1:]:
                path.lineTo(X(px), Y(py))
            c.drawPath(path, stroke=1, fill=0)
        elif prim.op == "solid" and len(prim.pts) >= 3:
            path = c.beginPath()
            path.moveTo(X(prim.pts[0][0]), Y(prim.pts[0][1]))
            for px, py in prim.pts[1:]:
                path.lineTo(X(px), Y(py))
            path.close()
            c.drawPath(path, stroke=0, fill=1)
        elif prim.op == "text" and prim.text:
            font = _FONT_BOLD if prim.bold else _FONT
            c.setFont(font, prim.size * 72)
            lines = str(prim.text).split("\n")
            for i, line_text in enumerate(lines):
                yy = Y(prim.y1 - i * prim.size * 1.25)
                xx = X(prim.x1)
                if prim.anchor == "middle":
                    c.drawCentredString(xx, yy, line_text)
                elif prim.anchor == "end":
                    c.drawRightString(xx, yy, line_text)
                else:
                    c.drawString(xx, yy, line_text)
    c.save()
    return buf.getvalue()


def _dxf_text(value: str) -> str:
    return value.replace("\\", "\\\\").replace("\n", " ")


def to_dxf(prims: list[Prim], width: float, height: float) -> str:
    out = [
        "0", "SECTION", "2", "HEADER",
        "9", "$INSUNITS", "70", "1",
        "9", "$EXTMIN", "10", "0", "20", "0",
        "9", "$EXTMAX", "10", f"{width:.4f}", "20", f"{height:.4f}",
        "0", "ENDSEC",
        "0", "SECTION", "2", "ENTITIES",
    ]

    def ent(code_pairs: list[tuple[str, str]]) -> None:
        for code, val in code_pairs:
            out.extend([code, val])

    for prim in prims:
        layer = prim.layer or "0"
        if prim.op == "line":
            ent([
                ("0", "LINE"), ("8", layer),
                ("10", f"{prim.x1:.4f}"), ("20", f"{prim.y1:.4f}"),
                ("11", f"{prim.x2:.4f}"), ("21", f"{prim.y2:.4f}"),
            ])
        elif prim.op == "rect":
            x, y, w, h = prim.x1, prim.y1, prim.x2, prim.y2
            corners = [(x, y), (x + w, y), (x + w, y + h), (x, y + h), (x, y)]
            for (x1, y1), (x2, y2) in zip(corners, corners[1:]):
                ent([
                    ("0", "LINE"), ("8", layer),
                    ("10", f"{x1:.4f}"), ("20", f"{y1:.4f}"),
                    ("11", f"{x2:.4f}"), ("21", f"{y2:.4f}"),
                ])
        elif prim.op == "circle":
            ent([
                ("0", "CIRCLE"), ("8", layer),
                ("10", f"{prim.x1:.4f}"), ("20", f"{prim.y1:.4f}"),
                ("40", f"{prim.r:.4f}"),
            ])
        elif prim.op == "arc":
            a0, a1 = prim.a0 % 360, prim.a1 % 360
            if a1 <= a0:
                a1 += 360
            ent([
                ("0", "ARC"), ("8", layer),
                ("10", f"{prim.x1:.4f}"), ("20", f"{prim.y1:.4f}"),
                ("40", f"{prim.r:.4f}"),
                ("50", f"{a0:.4f}"), ("51", f"{a1:.4f}"),
            ])
        elif prim.op in {"poly", "solid"}:
            pts = prim.pts
            for (x1, y1), (x2, y2) in zip(pts, pts[1:]):
                ent([
                    ("0", "LINE"), ("8", layer),
                    ("10", f"{x1:.4f}"), ("20", f"{y1:.4f}"),
                    ("11", f"{x2:.4f}"), ("21", f"{y2:.4f}"),
                ])
        elif prim.op == "text" and prim.text:
            ent([
                ("0", "TEXT"), ("8", "TEXT"),
                ("10", f"{prim.x1:.4f}"), ("20", f"{prim.y1:.4f}"),
                ("40", f"{prim.size:.4f}"),
                ("1", _dxf_text(prim.text)[:240]),
            ])
            if prim.anchor == "middle":
                out.extend(["72", "1", "11", f"{prim.x1:.4f}", "21", f"{prim.y1:.4f}"])
    out.extend(["0", "ENDSEC", "0", "EOF"])
    return "\n".join(out) + "\n"
