import importlib
import io
import json
import zipfile

import pytest
from fastapi.testclient import TestClient


@pytest.fixture()
def client(tmp_path, monkeypatch):
    monkeypatch.setenv("DRAWINGS_DATA", str(tmp_path))
    import app.db as db
    import app.main as main

    importlib.reload(db)
    importlib.reload(main)
    with TestClient(main.app) as test_client:
        yield test_client


def test_part_example_sheet_carries_sop_content(client):
    created = client.post("/api/jobs", json={"exampleId": "norstar-cor438"})
    assert created.status_code == 200, created.text
    job = created.json()
    assert job["sourceKind"] == "ipt"
    assert job["viewCount"] == 4
    assert len(job["model"]["bends"]) == 2
    generated = client.post(f"/api/jobs/{job['id']}/generate")
    assert generated.status_code == 200, generated.text
    body = generated.json()
    assert body["status"] == "ready"
    svg = client.get(f"/api/jobs/{job['id']}/sheet.svg").text
    for expected in ("COR438", "C013718 Center Pivot Plate", "BEND ID", "THIRD ANGLE", "9.667", "Steel", "FLAT PATTERN"):
        assert expected in svg
    pdf = client.get(f"/api/jobs/{job['id']}/sheet.pdf")
    assert pdf.content.startswith(b"%PDF")
    dxf = client.get(f"/api/jobs/{job['id']}/sheet.dxf").text
    assert "COR438" in dxf
    assert "ENTITIES" in dxf


def test_assembly_bom_uses_saved_format_and_can_be_edited(client):
    created = client.post("/api/jobs", json={"exampleId": "norstar-grt647"}).json()
    assert created["bomReady"] is True
    assert created["bomRows"][0]["partNumber"] == "GRT654"
    formats = client.get("/api/bom-formats").json()
    fmt = formats[0]
    fmt["columns"][1]["heading"] = "PART NO."
    saved = client.put(f"/api/bom-formats/{fmt['id']}", json=fmt)
    assert saved.status_code == 200, saved.text
    updated = client.put(f"/api/jobs/{created['id']}", json={
        "templateId": created["templateId"],
        "bomFormatId": fmt["id"],
        "viewCount": 2,
        "selectedViews": ["side", "iso"],
        "properties": created["properties"],
        "model": created["model"],
        "bomRows": created["bomRows"],
    })
    assert updated.status_code == 200, updated.text
    assert updated.json()["viewCount"] == 2
    generated = client.post(f"/api/jobs/{created['id']}/generate")
    assert generated.status_code == 200, generated.text
    svg = client.get(f"/api/jobs/{created['id']}/sheet.svg").text
    assert "PART NO." in svg
    assert "GRT647" in svg
    assert "Parts List" in svg
    csv = client.get(f"/api/jobs/{created['id']}/bom.csv").text
    assert "PART NO." in csv
    assert "GRT654" in csv


def test_view_count_below_two_is_rejected(client):
    created = client.post("/api/jobs", json={"exampleId": "norstar-cor438"}).json()
    response = client.put(f"/api/jobs/{created['id']}", json={
        "templateId": created["templateId"],
        "viewCount": 1,
        "selectedViews": ["front"],
        "properties": created["properties"],
        "model": created["model"],
        "bomRows": [],
    })
    assert response.status_code == 400


def test_template_edit_is_used_on_the_next_sheet(client):
    templates = client.get("/api/templates").json()
    part = next(item for item in templates if item["id"] == "norstar-part")
    part["company"]["proprietary"] = "SHOP NOTICE SAMPLE"
    saved = client.put("/api/templates/norstar-part", json=part)
    assert saved.status_code == 200, saved.text
    created = client.post("/api/jobs", json={"exampleId": "norstar-cor438"}).json()
    client.post(f"/api/jobs/{created['id']}/generate")
    svg = client.get(f"/api/jobs/{created['id']}/sheet.svg").text
    assert "SHOP NOTICE SAMPLE" in svg


def test_inventor_upload_reads_properties_and_builds_an_envelope(client):
    payload = "Part Number".encode("utf-16le") + b"\x00\x00" + "ME-100".encode("utf-16le")
    payload += "Description".encode("utf-16le") + b"\x00\x00" + "Test Slide".encode("utf-16le")
    response = client.post("/api/jobs", files={"file": ("ME-100.ipt", payload, "application/octet-stream")})
    assert response.status_code == 200, response.text
    job = response.json()
    assert job["properties"]["partNumber"] == "ME-100"
    assert job["properties"]["description"] == "Test Slide"
    assert job["bomReady"] is False
    job["model"]["overall"] = {"length": 8, "width": 3, "height": 1.5}
    updated = client.put(f"/api/jobs/{job['id']}", json={
        "templateId": job["templateId"],
        "viewCount": 2,
        "selectedViews": job["selectedViews"][:2],
        "properties": job["properties"],
        "model": job["model"],
        "bomRows": [],
    })
    assert updated.status_code == 200, updated.text
    generated = client.post(f"/api/jobs/{job['id']}/generate").json()
    assert any(item["rule"] == "Profiles" and item["status"] == "warn" for item in generated["sop"])
    svg = client.get(f"/api/jobs/{job['id']}/sheet.svg").text
    assert "ME-100" in svg
    assert "ENVELOPE" in svg


def test_template_source_points_at_the_inventor_2025_folder(client):
    source = client.get("/api/template-source").json()
    assert source["path"] == r"C:\Users\Public\Documents\Autodesk\Inventor 2025\Templates\en-US"
    assert source["reachable"] is False
    assert source["drawings"] == []
    missing = client.post("/api/template-source/sync")
    assert missing.status_code == 400
    assert "ExportTemplates.vb" in missing.json()["detail"]


def test_import_inventor_template_catalog_keeps_later_edits(client):
    catalog = {
        "schema": "drawgen-templates/1",
        "folder": r"C:\Users\Public\Documents\Autodesk\Inventor 2025\Templates\en-US",
        "templates": [
            {
                "fileName": "Standard.idw",
                "relativePath": "Standard.idw",
                "sheetWidthIn": 17,
                "sheetHeightIn": 11,
                "titleBlock": "NORSTAR",
                "border": "ANSI",
            },
            {
                "fileName": "Signoff.idw",
                "relativePath": r"Custom\Signoff.idw",
                "sheetWidthIn": 34,
                "sheetHeightIn": 22,
            },
        ],
    }
    imported = client.post(
        "/api/templates/import",
        files={"file": ("drawgen-templates.json", json.dumps(catalog), "application/json")},
    )
    assert imported.status_code == 200, imported.text
    body = imported.json()
    assert body["imported"] == 2
    standard = next(item for item in body["templates"] if item["id"] == "inv-standard-idw")
    assert standard["appliesTo"] == "both"
    assert standard["sheetLabel"] == "B"
    assert standard["source"]["sheetSizeRead"] is True
    assert standard["source"]["folder"].endswith(r"Templates\en-US")
    assert standard["company"]["name"] == "NORSTAR"
    signoff = next(item for item in body["templates"] if item["id"] == "inv-custom-signoff-idw")
    assert signoff["drawingType"] == "signoff"
    assert signoff["name"] == "Custom / Signoff.idw"
    assert signoff["sheetLabel"] == "D"
    standard["drawingType"] = "assembly"
    saved = client.put(f"/api/templates/{standard['id']}", json=standard)
    assert saved.status_code == 200, saved.text
    catalog["templates"][0]["sheetWidthIn"] = 22
    catalog["templates"][0]["sheetHeightIn"] = 17
    again = client.post(
        "/api/templates/import",
        files={"file": ("drawgen-templates.json", json.dumps(catalog), "application/json")},
    )
    assert again.status_code == 200, again.text
    updated = next(item for item in again.json()["templates"] if item["id"] == "inv-standard-idw")
    assert again.json()["updated"] == 2
    assert updated["drawingType"] == "assembly"
    assert updated["sheetWidthIn"] == 22
    assert updated["sheetLabel"] == "C"
    assert any(item["id"] == "norstar-part" for item in again.json()["templates"])


def test_zip_of_the_template_folder_uses_drawing_file_names(client):
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w") as archive:
        archive.writestr("en-US/Standard.dwg", b"")
        archive.writestr("en-US/Weldment.idw", b"")
        archive.writestr("en-US/Standard.ipt", b"")
    response = client.post(
        "/api/templates/import",
        files={"file": ("templates.zip", buffer.getvalue(), "application/zip")},
    )
    assert response.status_code == 200, response.text
    templates = response.json()["templates"]
    assert "Standard.dwg" in {item["name"] for item in templates}
    weld = next(item for item in templates if item["name"] == "Weldment.idw")
    assert weld["drawingType"] == "weldment"
    assert weld["appliesTo"] == "iam"
    assert weld["source"]["sheetSizeRead"] is False
    assert weld["sheetLabel"] == "B"


def test_mounted_template_folder_is_read_on_startup(tmp_path, monkeypatch):
    folder = tmp_path / "en-US"
    folder.mkdir()
    (folder / "Standard.idw").write_bytes(b"")
    (folder / "Weldment.idw").write_bytes(b"")
    nested = folder / "Metric"
    nested.mkdir()
    (nested / "ANSI.dwg").write_bytes(b"")
    (folder / "Standard.ipt").write_bytes(b"")
    monkeypatch.setenv("DRAWINGS_DATA", str(tmp_path / "data"))
    monkeypatch.setenv("DRAWINGS_TEMPLATE_DIR", str(folder))
    import app.db as db
    import app.main as main

    importlib.reload(db)
    importlib.reload(main)
    with TestClient(main.app) as mounted:
        source = mounted.get("/api/template-source").json()
        assert source["reachable"] is True
        assert source["path"] == r"C:\Users\Public\Documents\Autodesk\Inventor 2025\Templates\en-US"
        assert "Standard.idw" in source["drawings"]
        assert r"Metric\ANSI.dwg" in source["drawings"]
        assert source["otherCount"] == 1
        templates = mounted.get("/api/templates").json()
        standard = next(item for item in templates if item["name"] == "Standard.idw")
        assert standard["appliesTo"] == "both"
        assert standard["source"]["sheetSizeRead"] is False
        ansi = next(item for item in templates if item["name"] == "Metric / ANSI.dwg")
        assert ansi["appliesTo"] == "both"


def test_signoff_example_includes_customer_block(client):
    created = client.post("/api/jobs", json={"exampleId": "norstar-avf002"}).json()
    assert created["properties"]["customer"] == "AVENA FOODS LIMITED"
    assert len(created["selectedViews"]) >= 2
    client.post(f"/api/jobs/{created['id']}/generate")
    svg = client.get(f"/api/jobs/{created['id']}/sheet.svg").text
    assert "AVENA FOODS LIMITED" in svg
    assert "SECTION A-A" in svg
    assert "CU20083" in svg
