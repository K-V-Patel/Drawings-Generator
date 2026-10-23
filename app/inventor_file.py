"""Read Inventor iProperties from an .ipt or .iam without Inventor.

The file is an OLE compound document. Property-set streams (MS-OLEPS) hold
the design-tracking fields and the exported parameters. Flat-pattern extents
are centimeters. Custom length, width, height, and thickness values carry
their own units and are the size used on the sheet.
"""

from __future__ import annotations

import io
import re
import struct

DESIGN_TRACKING = bytes.fromhex("0f3f85324434d1119e930060b03c1ca6")
SUMMARY_INFO = bytes.fromhex("e0859ff29f4f6810ab9108002b27b3d9")
USER_DEFINED = bytes.fromhex("b8ad299907643e41b3dccb9ad2f564b7")
DOCUMENT_SUMMARY = bytes.fromhex("05d5cdd59c2e1b10939708002b2cf9ae")

_LENGTH = {"length", "len", "oal", "overalllength"}
_WIDTH = {"width", "wid", "oaw", "overallwidth"}
_HEIGHT = {"height", "hgt", "oah", "overallheight"}
_DEPTH = {"depth", "deep", "oad", "overalldepth"}
_THICK = {"thickness", "thick", "thk", "stockthickness"}

_UNIT = re.compile(
    r"^\s*([+-]?(?:\d+(?:\.\d*)?|\.\d+))\s*(inch(?:es)?|in|mm|millimeters?|cm|centimeters?|ft|feet|foot|m|meters?|\"|')?\s*$",
    re.IGNORECASE,
)
_PART_FILE = re.compile(r"([^\\/:]+)\.(ipt|iam)\b", re.IGNORECASE)


def read_inventor_file(data: bytes, filename: str = "", kind: str = "ipt") -> dict:
    """Properties, overall inches, and an assembly parts list from the file."""
    empty = {"ok": False, "properties": {}, "overall": {}, "bomRows": []}
    if data[:8] != b"\xd0\xcf\x11\xe0\xa1\xb1\x1a\xe1":
        return empty
    try:
        import olefile
    except ImportError:
        return empty
    try:
        ole = olefile.OleFileIO(io.BytesIO(data))
    except Exception:
        return empty
    sets = []
    ufrx = b""
    try:
        for path in ole.listdir(streams=True, storages=False):
            try:
                blob = ole.openstream(path).read()
            except Exception:
                continue
            name = path[-1] if path else ""
            if name == "UFRxDoc":
                ufrx = blob
            if len(blob) < 28 or len(blob) > 2_000_000 or blob[:2] != b"\xfe\xff":
                continue
            sets.extend(parse_property_stream(blob))
    finally:
        ole.close()
    if not sets:
        return empty
    properties, overall = _map_sets(sets)
    rows = _assembly_rows(ufrx, filename) if kind == "iam" else []
    return {"ok": True, "properties": properties, "overall": overall, "bomRows": rows}


def inches_from(value, unitless: str = "in") -> float | None:
    """Convert a custom iProperty to inches. Unitless numbers are inches."""
    if isinstance(value, bool):
        return None
    if isinstance(value, (int, float)):
        number = float(value)
        unit = unitless
    else:
        match = _UNIT.match(str(value).strip().replace(",", ""))
        if not match:
            return None
        number = float(match.group(1))
        unit = (match.group(2) or unitless).lower()
    if unit in {"in", "inch", "inches", '"'}:
        return number
    if unit in {"mm", "millimeter", "millimeters"}:
        return number / 25.4
    if unit in {"cm", "centimeter", "centimeters"}:
        return number / 2.54
    if unit in {"m", "meter", "meters"}:
        return number * 39.37007874015748
    if unit in {"ft", "feet", "foot", "'"}:
        return number * 12
    return None


def parse_property_stream(blob: bytes) -> list[dict]:
    if len(blob) < 48 or blob[:2] != b"\xfe\xff":
        return []
    count = _u32(blob, 24)
    if count < 1 or count > 16:
        return []
    found = []
    for index in range(count):
        base = 28 + index * 20
        if base + 20 > len(blob):
            break
        fmtid = blob[base:base + 16]
        offset = _u32(blob, base + 16)
        parsed = _parse_set(blob, offset)
        if parsed:
            found.append({"fmtid": fmtid, **parsed})
    return found


def _map_sets(sets: list[dict]) -> tuple[dict, dict]:
    props: dict[str, str] = {}
    custom: dict[str, object] = {}
    tracking: dict[int, object] = {}
    for item in sets:
        fmtid = item["fmtid"]
        if fmtid == DESIGN_TRACKING:
            tracking.update(item["props"])
        elif fmtid == SUMMARY_INFO:
            _copy_summary(props, item["props"])
        elif fmtid in {USER_DEFINED, DOCUMENT_SUMMARY}:
            for pid, name in item["names"].items():
                if pid in item["props"]:
                    custom[_norm(name)] = item["props"][pid]
    _copy_tracking(props, tracking)
    for key, label in (
        ("partnumber", "partNumber"),
        ("description", "description"),
        ("material", "material"),
        ("stocknumber", "stockNumber"),
        ("designer", "designer"),
        ("revision", "rev"),
        ("project", "project"),
        ("vendor", "vendor"),
        ("title", "title"),
        ("author", "drawnBy"),
    ):
        if label not in props and key in custom:
            text = _text(custom[key])
            if text:
                props[label] = text
    length = _named(custom, _LENGTH)
    width = _named(custom, _WIDTH)
    height = _named(custom, _HEIGHT)
    depth = _named(custom, _DEPTH)
    thickness = _named(custom, _THICK)
    if length is None:
        length = _cm(tracking.get(64)) or _cm(tracking.get(69))
    if width is None:
        width = _cm(tracking.get(63)) or _cm(tracking.get(68))
    if height is None and depth is not None:
        height = depth
    if height is None and thickness is not None:
        height = thickness
    if width is None and depth is not None and height is not None and depth != height:
        width = depth
    if thickness is not None:
        props["thickness"] = _trim(thickness)
    overall = {}
    if _positive(length) and _positive(width) and _positive(height):
        overall = {"length": _round(length), "width": _round(width), "height": _round(height)}
    return props, overall


def _copy_summary(props: dict, values: dict) -> None:
    _put(props, "title", values.get(2))
    _put(props, "subject", values.get(3))
    _put(props, "drawnBy", values.get(4))
    _put(props, "comments", values.get(6))
    _put(props, "rev", values.get(9))


def _copy_tracking(props: dict, values: dict) -> None:
    _put(props, "partNumber", values.get(5))
    _put(props, "project", values.get(7))
    _put(props, "material", values.get(20))
    _put(props, "description", values.get(29))
    _put(props, "vendor", values.get(30))
    _put(props, "designer", values.get(41))
    _put(props, "stockNumber", values.get(55))
    density = values.get(61)
    mass = values.get(58)
    valid = values.get(62)
    if (
        valid not in (None, 0, False)
        and isinstance(density, (int, float))
        and not isinstance(density, bool)
        and float(density) > 1.5
        and isinstance(mass, (int, float))
        and not isinstance(mass, bool)
        and float(mass) > 0
    ):
        props["mass"] = _trim(float(mass))


def _put(props: dict, key: str, value) -> None:
    text = _text(value)
    if text and key not in props:
        props[key] = text


def _text(value) -> str:
    if value is None or isinstance(value, bool):
        return ""
    if isinstance(value, float):
        return _trim(value)
    text = str(value).strip()
    if not text or len(text) > 240:
        return ""
    if any(ch in text for ch in "{}<>"):
        return ""
    lowered = text.lower()
    if "internalname" in lowered or "mnemonic=" in lowered or "\\" in text or text.startswith("*"):
        return ""
    return text


def _named(custom: dict, names: set[str]):
    for name in names:
        if name in custom:
            parsed = inches_from(custom[name])
            if parsed is not None and parsed > 0:
                return parsed
    return None


def _cm(value) -> float | None:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        return None
    number = float(value)
    if number <= 0:
        return None
    return number / 2.54


def _positive(value) -> bool:
    return isinstance(value, (int, float)) and value > 0


def _round(value: float) -> float:
    return round(float(value), 6)


def _trim(value: float) -> str:
    return f"{value:.4f}".rstrip("0").rstrip(".")


_SIZE_TOKEN = r"(?:\d+\s+\d+/\d+|\d+-\d+/\d+|\d+/\d+|\d+(?:\.\d+)?|\.\d+|¼|½|¾|⅛|⅜|⅝|⅞)"
_SIZE_TRIPLE = re.compile(
    rf"(?:^|[^\w.])(?P<a>{_SIZE_TOKEN})\s*(?P<ua>in(?:ch(?:es)?)?|mm|cm|\")?\s*[x×]\s*"
    rf"(?P<b>{_SIZE_TOKEN})\s*(?P<ub>in(?:ch(?:es)?)?|mm|cm|\")?\s*[x×]\s*"
    rf"(?P<c>{_SIZE_TOKEN})\s*(?P<uc>in(?:ch(?:es)?)?|mm|cm|\")?",
    re.IGNORECASE,
)
_UNICODE_FRACTIONS = {"¼": 0.25, "½": 0.5, "¾": 0.75, "⅛": 0.125, "⅜": 0.375, "⅝": 0.625, "⅞": 0.875}


_SIZE_PAIR = re.compile(
    rf"\((?P<a>{_SIZE_TOKEN})\s*(?P<ua>in(?:ch(?:es)?)?|mm|cm|\")?\s*[x×]\s*"
    rf"(?P<b>{_SIZE_TOKEN})\s*(?P<ub>in(?:ch(?:es)?)?|mm|cm|\")?\)",
    re.IGNORECASE,
)
_SIZE_LENGTH = re.compile(
    rf"[-–—]\s*(?P<n>{_SIZE_TOKEN})\s*(?P<u>in(?:ch(?:es)?)?|mm|cm|\")?",
    re.IGNORECASE,
)


def size_from_text(text: str) -> dict:
    """Overall inches from a description.

    A plate is written 3.75 x 3.75 x 1/4. A beam is written
    W 6 x 9 (5.9 x 3.94) - 31.6: the parentheses are the section and the
    number after the dash is the cut length. The W 6 x 9 name is not the size.
    """
    if not text:
        return {}
    raw = str(text)
    match = _SIZE_TRIPLE.search(raw)
    if match:
        length = _token_inches(match.group("a"), match.group("ua"))
        width = _token_inches(match.group("b"), match.group("ub"))
        height = _token_inches(match.group("c"), match.group("uc"))
        if _positive(length) and _positive(width) and _positive(height):
            return {"length": _round(length), "width": _round(width), "height": _round(height)}
    pair = _SIZE_PAIR.search(raw)
    if not pair:
        return {}
    length_match = _SIZE_LENGTH.search(raw[pair.end():])
    if not length_match:
        return {}
    depth = _token_inches(pair.group("a"), pair.group("ua"))
    flange = _token_inches(pair.group("b"), pair.group("ub"))
    length = _token_inches(length_match.group("n"), length_match.group("u"))
    if not (_positive(depth) and _positive(flange) and _positive(length)):
        return {}
    return {"length": _round(length), "width": _round(flange), "height": _round(depth)}


def apply_described_size(properties: dict | None, overall: dict | None) -> tuple[dict, dict, bool]:
    """Fill a missing envelope from a description such as 3.75 x 3.75 x 1/4."""
    props = dict(properties or {})
    size = dict(overall or {})
    if all(_positive(size.get(key)) for key in ("length", "width", "height")):
        return props, size, False
    text = " ".join(str(props.get(key) or "") for key in ("description", "title", "subject", "comments"))
    found = size_from_text(text)
    if not found:
        return props, size, False
    changed = False
    for key in ("length", "width", "height"):
        if not _positive(size.get(key)):
            size[key] = found[key]
            changed = True
    # The third number of a plate is the thickness. A beam depth is not.
    if changed and not str(props.get("thickness") or "").strip() and _SIZE_TRIPLE.search(text):
        props["thickness"] = _trim(found["height"])
    return props, size, changed


def _token_inches(token: str, unit: str | None) -> float | None:
    token = token.strip()
    if token in _UNICODE_FRACTIONS:
        number = _UNICODE_FRACTIONS[token]
    else:
        mixed = re.fullmatch(r"(\d+)[\s-](\d+)/(\d+)", token)
        if mixed:
            denominator = float(mixed.group(3))
            if denominator == 0:
                return None
            number = float(mixed.group(1)) + float(mixed.group(2)) / denominator
        elif re.fullmatch(r"\d+/\d+", token):
            numerator, denominator = token.split("/")
            if float(denominator) == 0:
                return None
            number = float(numerator) / float(denominator)
        else:
            number = float(token)
    if unit:
        return inches_from(f"{number} {unit}")
    return inches_from(number)


def _norm(name: str) -> str:
    return re.sub(r"[\s_\-]+", "", name or "").lower()


def _assembly_rows(blob: bytes, filename: str) -> list[dict]:
    own = filename.rsplit(".", 1)[0].lower()
    counts: dict[str, int] = {}
    order: list[str] = []
    for text in _utf16_strings(blob):
        lowered = text.lower().replace("/", "\\")
        if ".ipt" not in lowered and ".iam" not in lowered:
            continue
        if "\\templates\\" in lowered:
            continue
        for match in _PART_FILE.finditer(text):
            stem = match.group(1).strip()
            key = stem.lower()
            if not stem or key == own or key.startswith("standard"):
                continue
            if key not in counts:
                counts[key] = 0
                order.append(stem)
            counts[key] += 1
    return [
        {"item": str(index), "partNumber": stem, "description": "", "qty": str(counts[stem.lower()])}
        for index, stem in enumerate(order, start=1)
    ]


def _utf16_strings(data: bytes) -> list[str]:
    found = []
    index = 0
    limit = len(data) - 1
    while index < limit:
        chars: list[str] = []
        cursor = index
        while cursor < limit:
            code = data[cursor] | (data[cursor + 1] << 8)
            if 32 <= code <= 126:
                chars.append(chr(code))
                cursor += 2
            else:
                break
        if len(chars) >= 3:
            found.append("".join(chars))
            index = cursor + 2
        else:
            index += 1
    return found


def _parse_set(blob: bytes, offset: int) -> dict | None:
    if offset < 0 or offset + 8 > len(blob):
        return None
    count = _u32(blob, offset + 4)
    if count > 10000 or offset + 8 + count * 8 > len(blob):
        return None
    entries = []
    for index in range(count):
        pos = offset + 8 + index * 8
        entries.append((_u32(blob, pos), _u32(blob, pos + 4)))
    codepage = 1200
    for pid, rel in entries:
        if pid == 1:
            value = _variant(blob, offset + rel)
            if isinstance(value, int):
                codepage = value
            break
    props = {}
    names = {}
    for pid, rel in entries:
        absolute = offset + rel
        if pid == 0:
            names = _dictionary(blob, absolute, codepage)
        elif pid != 1:
            value = _variant(blob, absolute)
            if value is not None:
                props[pid] = value
    return {"props": props, "names": names}


def _dictionary(blob: bytes, offset: int, codepage: int) -> dict:
    if offset + 4 > len(blob):
        return {}
    count = _u32(blob, offset)
    if count > 10000:
        return {}
    pos = offset + 4
    names = {}
    unicode = codepage == 1200
    for _ in range(count):
        if pos + 8 > len(blob):
            break
        pid = _u32(blob, pos)
        length = _u32(blob, pos + 4)
        pos += 8
        if length <= 0 or length > 10000:
            break
        if unicode:
            size = length * 2
            if pos + size > len(blob):
                break
            text = blob[pos:pos + size].decode("utf-16le", errors="ignore").rstrip("\x00").strip()
            pos += size
        else:
            if pos + length > len(blob):
                break
            text = blob[pos:pos + length].split(b"\x00", 1)[0].decode("latin1", errors="ignore").strip()
            pos += length
        if pos % 4:
            pos += 4 - (pos % 4)
        if text:
            names[pid] = text
    return names


def _variant(blob: bytes, offset: int):
    if offset < 0 or offset + 4 > len(blob):
        return None
    kind = _u16(blob, offset)
    if kind & 0xF000:
        return None
    data = offset + 4
    if kind == 31:
        if data + 4 > len(blob):
            return None
        chars = _u32(blob, data)
        size = chars * 2
        if chars <= 0 or chars > 100000 or data + 4 + size > len(blob):
            return None
        return blob[data + 4:data + 4 + size].decode("utf-16le", errors="ignore").rstrip("\x00").strip()
    if kind == 30:
        if data + 4 > len(blob):
            return None
        size = _u32(blob, data)
        if size <= 0 or size > 100000 or data + 4 + size > len(blob):
            return None
        return blob[data + 4:data + 4 + size].split(b"\x00", 1)[0].decode("latin1", errors="ignore").strip()
    if kind == 8:
        if data + 4 > len(blob):
            return None
        size = _u32(blob, data)
        if size > 100000 or data + 4 + size > len(blob):
            return None
        raw = blob[data + 4:data + 4 + size]
        if size % 2 == 0:
            text = raw.decode("utf-16le", errors="ignore").rstrip("\x00").strip()
            if text:
                return text
        return raw.split(b"\x00", 1)[0].decode("latin1", errors="ignore").strip()
    if kind == 2:
        return _i16(blob, data) if data + 2 <= len(blob) else None
    if kind in {3, 22}:
        return _i32(blob, data) if data + 4 <= len(blob) else None
    if kind == 19:
        return _u32(blob, data) if data + 4 <= len(blob) else None
    if kind == 11:
        return bool(_u16(blob, data)) if data + 2 <= len(blob) else None
    if kind == 4:
        return struct.unpack_from("<f", blob, data)[0] if data + 4 <= len(blob) else None
    if kind == 5:
        return struct.unpack_from("<d", blob, data)[0] if data + 8 <= len(blob) else None
    if kind == 16:
        return struct.unpack_from("<b", blob, data)[0] if data < len(blob) else None
    if kind == 17:
        return blob[data] if data < len(blob) else None
    return None


def _u16(blob: bytes, offset: int) -> int:
    return struct.unpack_from("<H", blob, offset)[0]


def _i16(blob: bytes, offset: int) -> int:
    return struct.unpack_from("<h", blob, offset)[0]


def _u32(blob: bytes, offset: int) -> int:
    return struct.unpack_from("<I", blob, offset)[0]


def _i32(blob: bytes, offset: int) -> int:
    return struct.unpack_from("<i", blob, offset)[0]
