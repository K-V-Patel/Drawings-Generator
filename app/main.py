"""Drawings Generator API and the shop-floor page."""

from __future__ import annotations

import uuid
from contextlib import asynccontextmanager
from datetime import datetime, timezone
from pathlib import Path

from fastapi import FastAPI, Request
from fastapi.responses import FileResponse, JSONResponse, Response
from fastapi.staticfiles import StaticFiles

from app.db import connect, dumps, init_db, loads
from app.drawing.compose import compose
from app.drawing.export import to_dxf, to_pdf, to_svg
from app.examples_lib import all_examples, example_by_id
from app.inventor_templates import import_uploads, source_status, sync_if_reachable
from app.parser import from_drawgen, parse_upload
from app.seed import BEND_COLUMNS, seed_if_empty
from app.sop import review

STATIC = Path(__file__).resolve().parent.parent / "static"
SHEET_SIZES = {
    "A": (11, 8.5),
    "B": (17, 11),
    "C": (22, 17),
    "D": (34, 22),
    "E": (44, 34),
}


def now() -> str:
    return datetime.now(timezone.utc).isoformat()


def new_id() -> str:
    return uuid.uuid4().hex[:12]


@asynccontextmanager
async def lifespan(_app: FastAPI):
    init_db()
    seed_if_empty()
    sync_if_reachable()
    yield


app = FastAPI(title="Drawings Generator", lifespan=lifespan)


@app.exception_handler(ValueError)
async def _bad_request(_request: Request, exc: ValueError):
    return JSONResponse(status_code=400, content={"detail": str(exc)})


def _template_from_row(row) -> dict:
    body = loads(row["body_json"], {})
    return {
        "id": row["id"],
        "name": row["name"],
        "drawingType": row["drawing_type"],
        "appliesTo": row["applies_to"],
        "sheetWidthIn": row["sheet_width_in"],
        "sheetHeightIn": row["sheet_height_in"],
        "sheetLabel": row["sheet_label"],
        "company": body.get("company") or {},
        "views": body.get("views") or [],
        "defaultViews": body.get("default_views") or [],
        "table": body.get("table") or {"kind": "none"},
        "signoffFields": body.get("signoff_fields") or [],
        "sopNotes": body.get("sop_notes") or "",
        "source": body.get("source") or None,
        "updatedAt": row["updated_at"],
    }


def _compose_template(template: dict) -> dict:
    return {
        "sheet_width_in": template["sheetWidthIn"],
        "sheet_height_in": template["sheetHeightIn"],
        "sheet_label": template["sheetLabel"],
        "drawing_type": template["drawingType"],
        "company": template.get("company") or {},
        "views": template.get("views") or [],
        "table": template.get("table") or {},
        "signoff_fields": template.get("signoffFields") or [],
    }


def _format_from_row(row) -> dict:
    body = loads(row["body_json"], {})
    return {
        "id": row["id"],
        "name": row["name"],
        "isDefault": bool(row["is_default"]),
        "title": body.get("title") or "Parts List",
        "placement": body.get("placement") or "top-left",
        "showBalloons": bool(body.get("show_balloons", True)),
        "columns": body.get("columns") or [],
        "updatedAt": row["updated_at"],
    }


def _compose_format(fmt: dict | None) -> dict | None:
    if not fmt:
        return None
    return {"title": fmt["title"], "columns": fmt["columns"], "show_balloons": fmt["showBalloons"]}


def _job_from_row(row) -> dict:
    snapshot = loads(row["snapshot_json"], None)
    return {
        "id": row["id"],
        "createdAt": row["created_at"],
        "updatedAt": row["updated_at"],
        "sourceName": row["source_name"],
        "sourceKind": row["source_kind"],
        "exampleId": row["example_id"],
        "templateId": row["template_id"],
        "bomFormatId": row["bom_format_id"],
        "viewCount": row["view_count"],
        "selectedViews": loads(row["selected_views_json"], []),
        "properties": loads(row["properties_json"], {}),
        "model": loads(row["model_json"], {}),
        "bomRows": loads(row["bom_rows_json"], []),
        "warnings": loads(row["warnings_json"], []),
        "status": row["status"],
        "sample": bool(row["sample"]),
        "sampleNote": row["sample_note"] or "",
        "sop": loads(row["sop_json"], None),
        "hasSheet": snapshot is not None,
    }


def _load_template(template_id: str) -> dict:
    with connect() as conn:
        row = conn.execute("SELECT * FROM templates WHERE id = ?", (template_id,)).fetchone()
    if not row:
        raise ValueError("That drawing template is no longer in the library.")
    return _template_from_row(row)


def _load_format(format_id: str | None) -> dict | None:
    with connect() as conn:
        if format_id:
            row = conn.execute("SELECT * FROM bom_formats WHERE id = ?", (format_id,)).fetchone()
        else:
            row = conn.execute("SELECT * FROM bom_formats WHERE is_default = 1 ORDER BY updated_at LIMIT 1").fetchone()
        if not row:
            row = conn.execute("SELECT * FROM bom_formats ORDER BY name LIMIT 1").fetchone()
    return _format_from_row(row) if row else None


def _templates() -> list[dict]:
    with connect() as conn:
        rows = conn.execute("SELECT * FROM templates ORDER BY name").fetchall()
    return [_template_from_row(row) for row in rows]


def _choose_template(parsed: dict) -> dict:
    templates = _templates()
    if not templates:
        raise ValueError("Add a drawing template before starting a sheet.")
    wanted = parsed.get("templateId")
    if wanted:
        match = next((item for item in templates if item["id"] == wanted), None)
        if match:
            return match
    kind = parsed.get("fileKind")
    model_kind = (parsed.get("model") or {}).get("kind")
    if kind == "ipt" or model_kind == "part":
        pool = [item for item in templates if item["drawingType"] == "part"]
    elif model_kind == "weldment":
        pool = [item for item in templates if item["drawingType"] == "weldment"]
    elif model_kind == "signoff":
        pool = [item for item in templates if item["drawingType"] == "signoff"]
    else:
        pool = [item for item in templates if item["drawingType"] == "assembly"]
    return (pool or templates)[0]


def _views_for(template: dict, parsed: dict) -> list[str]:
    order = [view["role"] for view in template.get("views") or []]
    requested = parsed.get("selectedViews")
    if requested is None:
        requested = parsed.get("views")
    count = parsed.get("viewCount")
    if count is not None:
        try:
            count = int(count)
        except (TypeError, ValueError) as exc:
            raise ValueError("View count has to be a number.") from exc
        if count < 2:
            raise ValueError("At least 2 views are required.")
    if requested:
        chosen = [role for role in requested if role in order]
        if len(chosen) < 2:
            raise ValueError("At least 2 views are required.")
        if count and len(chosen) > count:
            chosen = chosen[:count]
        return chosen
    chosen = [role for role in (template.get("defaultViews") or order) if role in order]
    if count and len(chosen) > count:
        chosen = chosen[:count]
    if len(chosen) < 2:
        raise ValueError("This template needs at least two views before a sheet can be made.")
    return chosen


def _insert_job(parsed: dict) -> dict:
    template = _choose_template(parsed)
    fmt = _load_format(parsed.get("bomFormatId"))
    views = _views_for(template, parsed)
    props = dict(parsed.get("properties") or {})
    if not props.get("productSeries"):
        props["productSeries"] = (template.get("company") or {}).get("productSeries") or ""
    props.setdefault("extras", {})
    # A signoff template's extra lines should exist even when the file didn't carry them.
    extras = dict(props.get("extras") or {})
    for field in template.get("signoffFields") or []:
        extras.setdefault(field.get("key"), "")
    props["extras"] = extras
    bom_rows = list(parsed.get("bomRows") or [])
    if parsed.get("fileKind") == "iam" and not bom_rows:
        bom_rows = []
    job_id = new_id()
    timestamp = now()
    with connect() as conn:
        conn.execute(
            """
            INSERT INTO jobs (
                id, created_at, updated_at, source_name, source_kind, example_id,
                template_id, bom_format_id, view_count, selected_views_json,
                properties_json, model_json, bom_rows_json, warnings_json,
                status, sample, sample_note, sop_json, snapshot_json
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                job_id, timestamp, timestamp, parsed.get("fileName"), parsed.get("fileKind"), parsed.get("exampleId"),
                template["id"], fmt["id"] if fmt else None, len(views), dumps(views),
                dumps(props), dumps(parsed.get("model") or {}), dumps(bom_rows), dumps(parsed.get("warnings") or []),
                "draft", 1 if parsed.get("sample") else 0, parsed.get("sampleNote") or "", None, None,
            ),
        )
        row = conn.execute("SELECT * FROM jobs WHERE id = ?", (job_id,)).fetchone()
    return _present(row)


def _present(row) -> dict:
    job = _job_from_row(row)
    template = _load_template(job["templateId"]) if job["templateId"] else None
    if job["sop"] is None and template:
        job["sop"] = review(_compose_template(template), _for_rules(job))
    job["bomReady"] = job["sourceKind"] == "iam" or (template or {}).get("table", {}).get("kind") == "parts"
    return job


def _for_rules(job: dict) -> dict:
    return {
        "selected_views": job["selectedViews"],
        "properties": job["properties"],
        "model": job["model"],
        "bom_rows": job["bomRows"],
    }


def _get_job(job_id: str):
    with connect() as conn:
        row = conn.execute("SELECT * FROM jobs WHERE id = ?", (job_id,)).fetchone()
    if not row:
        raise ValueError("That drawing could not be found.")
    return row


@app.get("/api/health")
def health():
    return {"ok": True}


@app.get("/api/template-source")
def template_source():
    return source_status()


@app.post("/api/template-source/sync")
def template_source_sync():
    status = source_status()
    if not status["reachable"]:
        raise ValueError(
            "This machine cannot open "
            + status["path"]
            + ". Run tools/ExportTemplates.vb in Inventor and drop the JSON here, or zip that folder and drop it."
        )
    result = sync_if_reachable() or {"imported": 0, "updated": 0, "skipped": []}
    result["templates"] = _templates()
    result["source"] = source_status()
    return result


@app.post("/api/templates/import")
async def import_template_files(request: Request):
    content_type = request.headers.get("content-type", "")
    if "multipart/form-data" not in content_type:
        raise ValueError("Drop a template list (.json), a zip of the template folder, or an .idw / .dwg file.")
    form = await request.form()
    uploads = form.getlist("file")
    files = []
    for upload in uploads:
        if upload is None or not getattr(upload, "filename", None):
            continue
        data = await upload.read()
        files.append((upload.filename, data))
    result = import_uploads(files)
    result["templates"] = _templates()
    result["source"] = source_status()
    return result


@app.get("/api/templates")
def list_templates():
    return _templates()


@app.get("/api/templates/{template_id}")
def get_template(template_id: str):
    return _load_template(template_id)


@app.put("/api/templates/{template_id}")
async def update_template(template_id: str, request: Request):
    current = _load_template(template_id)
    body = await request.json()
    merged = {**current, **body}
    _validate_template(merged)
    saved = _write_template(template_id, merged, now())
    return saved


@app.post("/api/templates/{template_id}/duplicate")
def duplicate_template(template_id: str):
    current = _load_template(template_id)
    current["name"] = f"{current['name']} copy"
    current["source"] = None
    template_id = new_id()
    return _write_template(template_id, current, now())


@app.delete("/api/templates/{template_id}")
def delete_template(template_id: str):
    with connect() as conn:
        count = conn.execute("SELECT COUNT(*) AS n FROM templates").fetchone()["n"]
        if count <= 1:
            raise ValueError("Keep at least one drawing template.")
        conn.execute("DELETE FROM templates WHERE id = ?", (template_id,))
    return {"ok": True}


@app.get("/api/bom-formats")
def list_formats():
    with connect() as conn:
        rows = conn.execute("SELECT * FROM bom_formats ORDER BY name").fetchall()
    return [_format_from_row(row) for row in rows]


@app.put("/api/bom-formats/{format_id}")
async def update_format(format_id: str, request: Request):
    body = await request.json()
    current = _load_format(format_id)
    if not current or current["id"] != format_id:
        raise ValueError("That BOM format is no longer in the library.")
    merged = {**current, **body}
    merged["columns"] = _normalize_columns(merged.get("columns") or [])
    if not merged["columns"]:
        raise ValueError("A BOM format needs at least one column.")
    _write_format(format_id, merged, now())
    return _load_format(format_id)


@app.post("/api/bom-formats/{format_id}/duplicate")
def duplicate_format(format_id: str):
    current = _load_format(format_id)
    if not current:
        raise ValueError("That BOM format is no longer in the library.")
    current["name"] = f"{current['name']} copy"
    current["isDefault"] = False
    format_id = new_id()
    _write_format(format_id, current, now())
    return _load_format(format_id)


@app.delete("/api/bom-formats/{format_id}")
def delete_format(format_id: str):
    with connect() as conn:
        count = conn.execute("SELECT COUNT(*) AS n FROM bom_formats").fetchone()["n"]
        if count <= 1:
            raise ValueError("Keep at least one BOM format.")
        row = conn.execute("SELECT is_default FROM bom_formats WHERE id = ?", (format_id,)).fetchone()
        conn.execute("DELETE FROM bom_formats WHERE id = ?", (format_id,))
        if row and row["is_default"]:
            conn.execute(
                "UPDATE bom_formats SET is_default = 1 WHERE id = (SELECT id FROM bom_formats ORDER BY name LIMIT 1)"
            )
    return {"ok": True}


@app.get("/api/examples")
def list_examples():
    summaries = []
    for example in all_examples():
        summaries.append({
            "id": example["id"],
            "group": example["group"],
            "sourcePath": example["sourcePath"],
            "fidelity": example["fidelity"],
            "fileName": example["fileName"],
            "fileKind": example["fileKind"],
            "description": (example.get("properties") or {}).get("description") or "",
            "partNumber": (example.get("properties") or {}).get("partNumber") or "",
            "templateId": example.get("templateId"),
        })
    return summaries


@app.get("/api/jobs")
def list_jobs():
    with connect() as conn:
        rows = conn.execute("SELECT * FROM jobs ORDER BY updated_at DESC").fetchall()
    listed = []
    for row in rows:
        job = _job_from_row(row)
        listed.append({
            "id": job["id"],
            "updatedAt": job["updatedAt"],
            "sourceName": job["sourceName"],
            "sourceKind": job["sourceKind"],
            "partNumber": (job["properties"] or {}).get("partNumber") or "",
            "description": (job["properties"] or {}).get("description") or "",
            "status": job["status"],
            "viewCount": job["viewCount"],
            "hasSheet": job["hasSheet"],
            "sample": job["sample"],
        })
    return listed


@app.post("/api/jobs")
async def create_job(request: Request):
    content_type = request.headers.get("content-type", "")
    if "multipart/form-data" in content_type:
        form = await request.form()
        upload = form.get("file")
        if upload is None:
            raise ValueError("Drop an .ipt, .iam, .json, or .zip file.")
        data = await upload.read()
        if len(data) > 40 * 1024 * 1024:
            raise ValueError("File is larger than 40 MB.")
        parsed = parse_upload(upload.filename or "model.ipt", data)
    else:
        body = await request.json()
        if body.get("exampleId"):
            example = example_by_id(body["exampleId"])
            if not example:
                raise ValueError("That example is not in the library.")
            parsed = example
        else:
            parsed = from_drawgen(body, body.get("fileName") or "model.json")
    return _insert_job(parsed)


@app.get("/api/jobs/{job_id}")
def get_job(job_id: str):
    return _present(_get_job(job_id))


@app.put("/api/jobs/{job_id}")
async def update_job(job_id: str, request: Request):
    row = _get_job(job_id)
    job = _job_from_row(row)
    body = await request.json()
    template_id = body.get("templateId") or job["templateId"]
    template = _load_template(template_id)
    fmt = _load_format(body.get("bomFormatId") or job["bomFormatId"])
    selected = body.get("selectedViews", job["selectedViews"])
    count = body.get("viewCount", len(selected))
    views = _views_for(template, {"selectedViews": selected, "viewCount": count})
    props = body.get("properties", job["properties"]) or {}
    props.setdefault("extras", {})
    model = body.get("model", job["model"]) or {}
    bom_rows = body.get("bomRows", job["bomRows"]) or []
    timestamp = now()
    with connect() as conn:
        conn.execute(
            """
            UPDATE jobs SET updated_at = ?, template_id = ?, bom_format_id = ?, view_count = ?,
                selected_views_json = ?, properties_json = ?, model_json = ?, bom_rows_json = ?,
                status = 'draft', sop_json = NULL
            WHERE id = ?
            """,
            (
                timestamp, template["id"], fmt["id"] if fmt else None, len(views), dumps(views),
                dumps(props), dumps(model), dumps(bom_rows), job_id,
            ),
        )
        saved = conn.execute("SELECT * FROM jobs WHERE id = ?", (job_id,)).fetchone()
    return _present(saved)


@app.post("/api/jobs/{job_id}/generate")
def generate_job(job_id: str):
    row = _get_job(job_id)
    job = _job_from_row(row)
    if len(job["selectedViews"]) < 2:
        raise ValueError("Ask for at least 2 views before generating the sheet.")
    template = _load_template(job["templateId"])
    fmt = _load_format(job["bomFormatId"])
    rules_job = _for_rules(job)
    sop = review(_compose_template(template), rules_job)
    status = "ready" if all(item["status"] == "pass" for item in sop) else "review"
    snapshot = {"template": template, "bomFormat": fmt, "generatedAt": now()}
    with connect() as conn:
        conn.execute(
            "UPDATE jobs SET status = ?, sop_json = ?, snapshot_json = ?, updated_at = ? WHERE id = ?",
            (status, dumps(sop), dumps(snapshot), snapshot["generatedAt"], job_id),
        )
        saved = conn.execute("SELECT * FROM jobs WHERE id = ?", (job_id,)).fetchone()
    presented = _present(saved)
    presented["sop"] = sop
    return presented


def _render(job_id: str):
    row = _get_job(job_id)
    job = _job_from_row(row)
    snapshot = loads(row["snapshot_json"], None)
    if not snapshot:
        raise ValueError("Generate the sheet before downloading it.")
    template = snapshot["template"]
    fmt = snapshot.get("bomFormat")
    prims = compose(_compose_template(template), _compose_format(fmt), {
        "properties": job["properties"],
        "model": job["model"],
        "bom_rows": job["bomRows"],
        "selected_views": job["selectedViews"],
        "sample_note": job["sampleNote"] if job["sample"] else "",
    })
    width = float(template["sheetWidthIn"])
    height = float(template["sheetHeightIn"])
    title = (job["properties"] or {}).get("partNumber") or job["sourceName"] or "Drawing"
    return prims, width, height, title, fmt, job


@app.get("/api/jobs/{job_id}/sheet.svg")
def sheet_svg(job_id: str):
    prims, width, height, _title, _fmt, _job = _render(job_id)
    return Response(to_svg(prims, width, height), media_type="image/svg+xml")


@app.get("/api/jobs/{job_id}/sheet.pdf")
def sheet_pdf(job_id: str):
    prims, width, height, title, _fmt, _job = _render(job_id)
    filename = f"{title}.pdf".replace(" ", "_")
    return Response(
        to_pdf(prims, width, height, title=title),
        media_type="application/pdf",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )


@app.get("/api/jobs/{job_id}/sheet.dxf")
def sheet_dxf(job_id: str):
    prims, width, height, title, _fmt, _job = _render(job_id)
    filename = f"{title}.dxf".replace(" ", "_")
    return Response(
        to_dxf(prims, width, height),
        media_type="application/dxf",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )


@app.get("/api/jobs/{job_id}/bom.csv")
def bom_csv(job_id: str):
    _prims, _w, _h, title, fmt, job = _render(job_id)
    columns = (fmt or {}).get("columns") or []
    header = ",".join(_csv(col.get("heading") or col.get("key") or "") for col in columns)
    lines = [header]
    for row in job["bomRows"]:
        lines.append(",".join(_csv(row.get(col.get("key"), "")) for col in columns))
    filename = f"{title}-bom.csv".replace(" ", "_")
    return Response("\n".join(lines) + "\n", media_type="text/csv", headers={"Content-Disposition": f'attachment; filename="{filename}"'})


def _csv(value) -> str:
    text = str(value if value is not None else "")
    if any(ch in text for ch in ",\"\n"):
        return '"' + text.replace('"', '""') + '"'
    return text


def _validate_template(template: dict) -> None:
    if not str(template.get("name") or "").strip():
        raise ValueError("Give the template a name.")
    if template.get("drawingType") not in {"part", "weldment", "assembly", "signoff"}:
        raise ValueError("Drawing type must be part, weldment, assembly, or signoff.")
    if template.get("appliesTo") not in {"ipt", "iam", "both"}:
        raise ValueError("A template applies to .ipt parts, .iam assemblies, or both.")
    views = template.get("views") or []
    if len(views) < 2:
        raise ValueError("A template needs at least two views.")
    label = str(template.get("sheetLabel") or "").upper()
    if label in SHEET_SIZES and not template.get("sheetWidthIn"):
        template["sheetWidthIn"], template["sheetHeightIn"] = SHEET_SIZES[label]
    try:
        width = float(template.get("sheetWidthIn"))
        height = float(template.get("sheetHeightIn"))
    except (TypeError, ValueError) as exc:
        raise ValueError("Sheet width and height need to be numbers, in inches.") from exc
    if width < 8 or height < 6:
        raise ValueError("Sheet size is smaller than an A-size landscape sheet.")
    template["sheetWidthIn"] = width
    template["sheetHeightIn"] = height
    table = template.get("table") or {}
    if table.get("kind") == "bend":
        table["columns"] = _normalize_columns(table.get("columns") or [dict(column) for column in BEND_COLUMNS])
        table.setdefault("title", "TABLE")
        template["table"] = table


def _write_template(template_id: str, template: dict, timestamp: str) -> dict:
    body = {
        "company": template.get("company") or {},
        "views": template.get("views") or [],
        "default_views": template.get("defaultViews") or [view["role"] for view in template.get("views") or []],
        "table": template.get("table") or {"kind": "none"},
        "signoff_fields": template.get("signoffFields") or [],
        "sop_notes": template.get("sopNotes") or "",
        "source": template.get("source") or None,
    }
    with connect() as conn:
        conn.execute(
            """
            INSERT INTO templates
            (id, name, drawing_type, applies_to, sheet_width_in, sheet_height_in, sheet_label, body_json, updated_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(id) DO UPDATE SET
                name = excluded.name,
                drawing_type = excluded.drawing_type,
                applies_to = excluded.applies_to,
                sheet_width_in = excluded.sheet_width_in,
                sheet_height_in = excluded.sheet_height_in,
                sheet_label = excluded.sheet_label,
                body_json = excluded.body_json,
                updated_at = excluded.updated_at
            """,
            (
                template_id, template["name"], template["drawingType"], template["appliesTo"],
                template["sheetWidthIn"], template["sheetHeightIn"], template.get("sheetLabel") or "",
                dumps(body), timestamp,
            ),
        )
        row = conn.execute("SELECT * FROM templates WHERE id = ?", (template_id,)).fetchone()
    return _template_from_row(row)


def _normalize_columns(columns: list[dict]) -> list[dict]:
    cleaned = []
    for column in columns:
        key = str(column.get("key") or "").strip()
        heading = str(column.get("heading") or "").strip()
        if not key or not heading:
            continue
        try:
            width = float(column.get("width") or 0)
        except (TypeError, ValueError):
            width = 0
        cleaned.append({"key": key, "heading": heading, "width": width})
    total = sum(column["width"] for column in cleaned) or len(cleaned) or 1
    if total <= 0:
        total = 1
    for column in cleaned:
        if column["width"] <= 0:
            column["width"] = 1
        column["width"] = round(column["width"] / total, 4)
    # Fix a rounding drift on the last column.
    if cleaned:
        drift = round(1 - sum(column["width"] for column in cleaned), 4)
        cleaned[-1]["width"] = round(cleaned[-1]["width"] + drift, 4)
    return cleaned


def _write_format(format_id: str, fmt: dict, timestamp: str) -> None:
    body = {
        "title": fmt.get("title") or "Parts List",
        "placement": fmt.get("placement") or "top-left",
        "show_balloons": bool(fmt.get("showBalloons", True)),
        "columns": fmt.get("columns") or [],
    }
    make_default = 1 if fmt.get("isDefault") else 0
    with connect() as conn:
        if make_default:
            conn.execute("UPDATE bom_formats SET is_default = 0")
        conn.execute(
            """
            INSERT INTO bom_formats (id, name, is_default, body_json, updated_at)
            VALUES (?, ?, ?, ?, ?)
            ON CONFLICT(id) DO UPDATE SET
                name = excluded.name,
                is_default = excluded.is_default,
                body_json = excluded.body_json,
                updated_at = excluded.updated_at
            """,
            (format_id, fmt.get("name") or "Parts list", make_default, dumps(body), timestamp),
        )


@app.get("/")
def index():
    return FileResponse(STATIC / "index.html")


app.mount("/static", StaticFiles(directory=STATIC), name="static")
