"""Read what an Inventor file will give up without Inventor.

.ipt and .iam files are OLE compound documents. Part number, description,
material, thickness, and overall size are read from the property sets.
Profile curves still come from a drawgen.json written by tools/ExportDrawgen.vb.
"""

from __future__ import annotations

import io
import json
import zipfile

from app.inventor_file import apply_described_size, read_inventor_file

_SCHEMA_MARKERS = (
    "internalname",
    "mnemonic=",
    "categoryparameter",
    "displayname=",
    "propfmtid",
    "propertyset",
)


def acceptable_property(value) -> bool:
    """True when a string can be shown in a title block.

    Inventor files contain the property schema (InternalName, Mnemonic) as
    text. That schema is not a part number, description, or material.
    """
    text = str(value or "").strip()
    if not text or len(text) > 240:
        return False
    lowered = text.lower()
    if any(marker in lowered for marker in _SCHEMA_MARKERS):
        return False
    if any(ch in text for ch in "{}<>"):
        return False
    if lowered.startswith("key:") or text.startswith("*"):
        return False
    return True


def sanitize_properties(props: dict | None, fallback_name: str = "") -> dict:
    cleaned = dict(props or {})
    for key in (
        "partNumber", "description", "material", "title", "subject", "designer",
        "drawnBy", "rev", "project", "stockNumber", "comments", "vendor",
        "mass", "thickness", "productSeries", "customer", "orderNumber", "quoteNumber",
    ):
        if key in cleaned and cleaned.get(key) not in (None, "") and not acceptable_property(cleaned.get(key)):
            cleaned[key] = ""
    if not acceptable_property(cleaned.get("partNumber")):
        stem = str(fallback_name or "").rsplit(".", 1)[0].strip()
        cleaned["partNumber"] = stem if acceptable_property(stem) else ""
    return cleaned


PROP_NAMES = {
    "Part Number": "partNumber",
    "PartNumber": "partNumber",
    "Description": "description",
    "Title": "title",
    "Subject": "subject",
    "Designer": "designer",
    "Author": "drawnBy",
    "Material": "material",
    "Stock Number": "stockNumber",
    "Revision Number": "rev",
    "Revision": "rev",
    "Project": "project",
    "Comments": "comments",
    "Keywords": "keywords",
    "Vendor": "vendor",
}


def parse_upload(filename: str, data: bytes) -> dict:
    lower = filename.lower()
    if lower.endswith(".zip"):
        return _from_zip(filename, data)
    if lower.endswith(".json"):
        return from_drawgen(json.loads(data.decode("utf-8")), filename)
    kind = "iam" if lower.endswith(".iam") else "ipt"
    return from_inventor(filename, data, kind)


def from_inventor(filename: str, data: bytes, kind: str) -> dict:
    warnings: list[str] = []
    props: dict[str, str] = {}
    overall: dict = {}
    bom_rows: list[dict] = []
    read = {"ok": False}
    if data[:8] == b"\xd0\xcf\x11\xe0\xa1\xb1\x1a\xe1":
        read = read_inventor_file(data, filename, kind)
        props.update(read.get("properties") or {})
        overall = dict(read.get("overall") or {})
        bom_rows = list(read.get("bomRows") or [])
        if not read.get("ok"):
            props.update(_ole_summary(data, warnings))
    else:
        warnings.append("This file is not an OLE compound document. Inventor parts and assemblies usually are.")
    if not read.get("ok"):
        for key, value in _scrape_properties(data).items():
            props.setdefault(key, value)
    if not props.get("partNumber"):
        stem = filename.rsplit(".", 1)[0]
        props["partNumber"] = stem
        warnings.append("Part number was taken from the file name.")
    description = props.get("description") or props.get("subject") or props.get("title") or ""
    props, overall, _described = apply_described_size(props, overall)
    sized = all(float(overall.get(key) or 0) > 0 for key in ("length", "width", "height"))
    if not sized:
        overall = {}
        warnings.append("This file has no saved overall size. A sheet is not generated.")
    else:
        warnings.append("Overall size, part number, and material were read from the file. Views show that envelope.")
    model_kind = "part" if kind == "ipt" else "assembly"
    return {
        "fileName": filename,
        "fileKind": kind,
        "properties": _clean_props(props, description),
        "model": {
            "kind": model_kind,
            "overall": overall,
            "bends": [],
            "welds": [],
            "components": list(bom_rows),
            "views": {},
            "sections": [],
        },
        "bomRows": bom_rows,
        "warnings": warnings,
        "sample": False,
        "sampleNote": "",
    }


def from_drawgen(payload: dict, filename: str) -> dict:
    if not isinstance(payload, dict):
        raise ValueError("The JSON export has to be an object.")
    props = dict(payload.get("properties") or {})
    model = dict(payload.get("model") or {})
    kind = payload.get("fileKind")
    if kind not in {"ipt", "iam"}:
        model_kind = model.get("kind")
        kind = "ipt" if model_kind == "part" else "iam"
    rows = payload.get("bomRows")
    if rows is None:
        rows = [_component_row(item) for item in model.get("components") or []]
    return {
        "fileName": payload.get("fileName") or filename,
        "fileKind": kind,
        "templateId": payload.get("templateId"),
        "bomFormatId": payload.get("bomFormatId"),
        "viewCount": payload.get("viewCount"),
        "selectedViews": payload.get("views") or payload.get("selectedViews"),
        "properties": props,
        "model": model,
        "bomRows": rows,
        "warnings": list(payload.get("warnings") or []),
        "sample": bool(payload.get("sample")),
        "sampleNote": payload.get("sampleNote") or "",
        "exampleId": payload.get("id"),
    }


def _component_row(item: dict) -> dict:
    return {
        "item": str(item.get("item", "")),
        "partNumber": item.get("partNumber", ""),
        "description": item.get("description", ""),
        "qty": str(item.get("qty", "")),
    }


def _clean_props(props: dict, description: str) -> dict:
    props = sanitize_properties(props)
    if not acceptable_property(description):
        description = ""
    return {
        "partNumber": props.get("partNumber") or "",
        "description": description,
        "material": props.get("material") or "",
        "thickness": props.get("thickness") or "",
        "mass": props.get("mass") or "",
        "rev": props.get("rev") or "",
        "drawnBy": props.get("drawnBy") or "",
        "drawnDate": "",
        "designer": props.get("designer") or "",
        "designerDate": "",
        "checker": "",
        "scale": "SEE ABOVE",
        "sheetNumber": "1",
        "sheetCount": "1",
        "productSeries": "",
        "customer": "",
        "orderNumber": "",
        "quoteNumber": "",
        "signature": "",
        "signDate": "",
        "extras": {},
    }


def _ole_summary(data: bytes, warnings: list[str]) -> dict:
    try:
        import olefile
    except ImportError:
        warnings.append("olefile is not installed, so summary properties were skipped.")
        return {}
    found = {}
    try:
        ole = olefile.OleFileIO(io.BytesIO(data))
        meta = ole.get_metadata()
        if meta.title and acceptable_property(meta.title):
            found["title"] = str(meta.title).strip()
        if meta.subject and acceptable_property(meta.subject):
            found["subject"] = str(meta.subject).strip()
        if meta.author and acceptable_property(meta.author):
            found["drawnBy"] = str(meta.author).strip()
        if meta.comments and acceptable_property(meta.comments):
            found["comments"] = str(meta.comments).strip()
        ole.close()
    except Exception as exc:
        warnings.append(f"Summary properties could not be read ({exc}).")
    return found


def _utf16_strings(data: bytes) -> list[str]:
    found = []
    i = 0
    limit = len(data) - 1
    while i < limit:
        chars: list[str] = []
        j = i
        while j < limit:
            code = data[j] | (data[j + 1] << 8)
            if 32 <= code <= 126:
                chars.append(chr(code))
                j += 2
            else:
                break
        if len(chars) >= 3:
            found.append("".join(chars))
            i = j + 2
        else:
            i += 1
    return found


def _split_property_names(strings: list[str]) -> list[str]:
    names = sorted(PROP_NAMES, key=len, reverse=True)
    pieces: list[str] = []
    for value in strings:
        remaining = value
        while remaining:
            found_at = None
            found_name = None
            for name in names:
                index = remaining.find(name)
                if index > 0 and (found_at is None or index < found_at):
                    found_at = index
                    found_name = name
            if found_at is None:
                pieces.append(remaining)
                break
            pieces.append(remaining[:found_at])
            pieces.append(found_name)
            remaining = remaining[found_at + len(found_name):]
    return pieces


def _scrape_properties(data: bytes) -> dict:
    strings = _split_property_names(_utf16_strings(data))
    props = {}
    for index, value in enumerate(strings):
        key = PROP_NAMES.get(value)
        if not key or index + 1 >= len(strings):
            continue
        nxt = strings[index + 1].strip()
        if nxt in PROP_NAMES or not acceptable_property(nxt):
            continue
        props.setdefault(key, nxt)
    return props


def _from_zip(filename: str, data: bytes) -> dict:
    try:
        with zipfile.ZipFile(io.BytesIO(data)) as bundle:
            names = [name for name in bundle.namelist() if name.lower().endswith(".json") and not name.startswith("__MACOSX")]
            if not names:
                raise ValueError("The zip needs a drawgen.json export.")
            payload = json.loads(bundle.read(names[0]).decode("utf-8"))
            parsed = from_drawgen(payload, names[0].split("/")[-1])
            cad = [name for name in bundle.namelist() if name.lower().endswith((".ipt", ".iam"))]
            if cad and not parsed.get("fileName"):
                parsed["fileName"] = cad[0].split("/")[-1]
            return parsed
    except ValueError:
        raise
    except Exception as exc:
        raise ValueError(f"Could not read the zip export ({exc}).") from exc
