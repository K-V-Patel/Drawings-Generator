"""Drawing primitives in inches, origin at the lower left, Y up."""

from __future__ import annotations

from dataclasses import dataclass, field


@dataclass
class Prim:
    op: str
    layer: str = "OBJECT"
    x1: float = 0.0
    y1: float = 0.0
    x2: float = 0.0
    y2: float = 0.0
    r: float = 0.0
    a0: float = 0.0
    a1: float = 0.0
    pts: list = field(default_factory=list)
    text: str = ""
    size: float = 0.1
    anchor: str = "start"
    weight: float = 0.01
    dashed: bool = False
    bold: bool = False


LAYER_WEIGHT = {
    "BORDER": 0.02,
    "OBJECT": 0.014,
    "THIN": 0.007,
    "DIM": 0.005,
    "CENTER": 0.005,
    "TEXT": 0.005,
    "HATCH": 0.004,
    "TABLE": 0.008,
}

LAYER_PX = {
    "BORDER": 1.8,
    "OBJECT": 1.35,
    "THIN": 0.9,
    "DIM": 0.85,
    "CENTER": 0.85,
    "TEXT": 0.8,
    "HATCH": 0.7,
    "TABLE": 1.05,
}


def line(x1, y1, x2, y2, layer="OBJECT", dashed=False) -> Prim:
    return Prim("line", layer, x1=x1, y1=y1, x2=x2, y2=y2, weight=LAYER_WEIGHT[layer], dashed=dashed)


def rect(x, y, w, h, layer="TABLE") -> Prim:
    return Prim("rect", layer, x1=x, y1=y, x2=w, y2=h, weight=LAYER_WEIGHT[layer])


def circle(cx, cy, r, layer="OBJECT") -> Prim:
    return Prim("circle", layer, x1=cx, y1=cy, r=r, weight=LAYER_WEIGHT[layer])


def arc(cx, cy, r, a0, a1, layer="OBJECT") -> Prim:
    return Prim("arc", layer, x1=cx, y1=cy, r=r, a0=a0, a1=a1, weight=LAYER_WEIGHT[layer])


def poly(pts, layer="OBJECT", dashed=False) -> Prim:
    return Prim("poly", layer, pts=list(pts), weight=LAYER_WEIGHT[layer], dashed=dashed)


def solid(pts, layer="DIM") -> Prim:
    return Prim("solid", layer, pts=list(pts))


def text(x, y, value, size=0.1, anchor="start", layer="TEXT", bold=False) -> Prim:
    return Prim("text", layer, x1=x, y1=y, text=str(value), size=size, anchor=anchor, bold=bold)
