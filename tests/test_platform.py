import importlib
import json

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


def _part_export():
    return {
        "schema": "drawgen/1",
        "fileName": "Plate.ipt",
        "fileKind": "ipt",
        "properties": {
            "partNumber": "PL-100",
            "description": "Center plate",
            "material": "Steel",
            "thickness": "0.375",
            "rev": "A",
        },
        "model": {
            "kind": "part",
            "overall": {"length": 9.667, "width": 4, "height": 3},
            "bends": [
                {"id": "1", "direction": "UP", "angle": "90", "radius": "0.237"},
                {"id": "2", "direction": "UP", "angle": "90", "radius": "0.237"},
            ],
            "welds": [],
            "components": [],
            "sections": [],
            "views": {
                "flat": {"paths": [{"pts": [[0, 0], [9.667, 0], [9.667, 4], [0, 4], [0, 0]], "layer": "OBJECT", "bend": True}]},
                "front": {"paths": [{"pts": [[0, 0], [4.875, 0], [4.875, 3], [0, 3], [0, 0]], "layer": "OBJECT"}]},
                "side": {"paths": [{"pts": [[0, 0], [4, 0], [4, 3], [0, 3], [0, 0]], "layer": "OBJECT"}]},
                "iso": {"paths": [{"pts": [[0, 0], [1, 1]], "layer": "OBJECT"}]},
            },
        },
    }


def test_templates_are_two_standard_and_one_signoff(client):
    templates = client.get("/api/templates").json()
    assert [item["name"] for item in templates] == ["Standard.idw", "Standard.dwg", "Sign off"]
    assert [item["id"] for item in templates] == ["standard-idw", "standard-dwg", "signoff"]
    assert all(item["appliesTo"] == "both" for item in templates)
    blob = json.dumps(templates).lower()
    assert "norstar" not in blob
    assert "meridian" not in blob
    formats = client.get("/api/bom-formats").json()
    assert formats[0]["name"] == "Parts list"
    assert "norstar" not in formats[0]["name"].lower()
    assert client.get("/api/examples").json() == []


def test_part_sheet_uses_standard_template_and_bend_table(client):
    created = client.post("/api/jobs", json=_part_export())
    assert created.status_code == 200, created.text
    job = created.json()
    assert job["templateId"] == "standard-idw"
    assert job["sourceKind"] == "ipt"
    assert "flat" in job["selectedViews"]
    generated = client.post(f"/api/jobs/{job['id']}/generate")
    assert generated.status_code == 200, generated.text
    svg = client.get(f"/api/jobs/{job['id']}/sheet.svg").text
    for expected in ("PL-100", "Center plate", "BEND ID", "THIRD ANGLE", "Steel", "FLAT PATTERN"):
        assert expected in svg
    assert "NORSTAR" not in svg
    assert "MERIDIAN" not in svg
    assert "NO PROFILE" not in svg
    pdf = client.get(f"/api/jobs/{job['id']}/sheet.pdf")
    assert pdf.content.startswith(b"%PDF")
    dxf = client.get(f"/api/jobs/{job['id']}/sheet.dxf").text
    assert "PL-100" in dxf
    assert "ENTITIES" in dxf


def test_assembly_bom_uses_saved_format(client):
    created = client.post("/api/jobs", json={
        "fileName": "Head.iam",
        "fileKind": "iam",
        "properties": {"partNumber": "HD-200", "description": "Head section"},
        "model": {
            "kind": "assembly",
            "overall": {"length": 37.76, "width": 10, "height": 12.33},
            "bends": [],
            "components": [{"item": "1", "partNumber": "HD-201", "description": "Body", "qty": "1"}],
            "views": {},
        },
        "bomRows": [{"item": "1", "partNumber": "HD-201", "description": "Body", "qty": "1"}],
    })
    assert created.status_code == 200, created.text
    job = created.json()
    assert job["bomReady"] is True
    assert job["selectedViews"] == ["side", "front", "end", "iso"]
    formats = client.get("/api/bom-formats").json()
    fmt = formats[0]
    fmt["columns"][1]["heading"] = "PART NO."
    saved = client.put(f"/api/bom-formats/{fmt['id']}", json=fmt)
    assert saved.status_code == 200, saved.text
    updated = client.put(f"/api/jobs/{job['id']}", json={
        "templateId": "standard-dwg",
        "bomFormatId": fmt["id"],
        "viewCount": 2,
        "selectedViews": ["side", "iso"],
        "properties": job["properties"],
        "model": job["model"],
        "bomRows": job["bomRows"],
    })
    assert updated.status_code == 200, updated.text
    generated = client.post(f"/api/jobs/{job['id']}/generate")
    assert generated.status_code == 200, generated.text
    svg = client.get(f"/api/jobs/{job['id']}/sheet.svg").text
    assert "PART NO." in svg
    assert "HD-200" in svg
    assert "Parts List" in svg
    assert "NORSTAR" not in svg
    csv = client.get(f"/api/jobs/{job['id']}/bom.csv").text
    assert "PART NO." in csv
    assert "HD-201" in csv


def test_view_count_below_two_is_rejected(client):
    created = client.post("/api/jobs", json=_part_export()).json()
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
    standard = next(item for item in templates if item["id"] == "standard-idw")
    standard["company"]["proprietary"] = "SHOP NOTICE SAMPLE"
    saved = client.put("/api/templates/standard-idw", json=standard)
    assert saved.status_code == 200, saved.text
    created = client.post("/api/jobs", json=_part_export()).json()
    client.post(f"/api/jobs/{created['id']}/generate")
    svg = client.get(f"/api/jobs/{created['id']}/sheet.svg").text
    assert "SHOP NOTICE SAMPLE" in svg


def test_inventor_schema_text_is_not_a_part_number(client):
    schema = '* InternalName="{016b6077-bfbe-49bd-92c9-d8d59c39c941}" Mnemonic="PARTNUMBER"/>'
    payload = "Part Number".encode("utf-16le") + b"\x00\x00" + schema.encode("utf-16le")
    payload += "Material".encode("utf-16le") + b"\x00\x00" + 'Key: InternalName="{5c8fadab-9d2b-4535-b8d7}" Mnemonic="MATERIAL:KEY"'.encode("utf-16le")
    response = client.post("/api/jobs", files={"file": ("Plate.ipt", payload, "application/octet-stream")})
    assert response.status_code == 200, response.text
    job = response.json()
    assert job["properties"]["partNumber"] == "Plate"
    assert "InternalName" not in json.dumps(job["properties"])
    assert job["properties"]["material"] == ""
    blocked = client.post(f"/api/jobs/{job['id']}/generate")
    assert blocked.status_code == 400
    assert "overall size" in blocked.json()["detail"]
    job["model"]["overall"] = {"length": 8, "width": 3, "height": 1.5}
    updated = client.put(f"/api/jobs/{job['id']}", json={
        "templateId": job["templateId"],
        "viewCount": 2,
        "selectedViews": ["front", "side"],
        "properties": job["properties"],
        "model": job["model"],
        "bomRows": [],
    })
    assert updated.status_code == 200, updated.text
    generated = client.post(f"/api/jobs/{job['id']}/generate")
    assert generated.status_code == 200, generated.text
    svg = client.get(f"/api/jobs/{job['id']}/sheet.svg").text
    assert "Plate" in svg
    assert "InternalName" not in svg
    assert "ENVELOPE" in svg
    assert "NO PROFILE" not in svg


def test_real_inventor_properties_still_read(client):
    payload = "Part Number".encode("utf-16le") + b"\x00\x00" + "ME-100".encode("utf-16le")
    payload += "Description".encode("utf-16le") + b"\x00\x00" + "Test Slide".encode("utf-16le")
    response = client.post("/api/jobs", files={"file": ("ME-100.ipt", payload, "application/octet-stream")})
    assert response.status_code == 200, response.text
    job = response.json()
    assert job["properties"]["partNumber"] == "ME-100"
    assert job["properties"]["description"] == "Test Slide"


def test_signoff_template_draws_the_customer_block(client):
    created = client.post("/api/jobs", json={
        "fileName": "Conv.iam",
        "fileKind": "iam",
        "templateId": "signoff",
        "properties": {
            "partNumber": "CV-8",
            "description": "Conveyor assembly",
            "customer": "North Grain",
            "orderNumber": "CU20083",
            "quoteNumber": "Q-100",
        },
        "model": {
            "kind": "assembly",
            "overall": {"length": 572, "width": 22.66, "height": 36.42},
            "sections": [{"label": "HEAD", "length": 168}, {"label": "TAIL", "length": 168}],
            "views": {},
        },
    })
    assert created.status_code == 200, created.text
    job = created.json()
    assert job["templateId"] == "signoff"
    assert "section" in job["selectedViews"]
    generated = client.post(f"/api/jobs/{job['id']}/generate")
    assert generated.status_code == 200, generated.text
    svg = client.get(f"/api/jobs/{job['id']}/sheet.svg").text
    assert "North Grain" in svg
    assert "CU20083" in svg
    assert "SECTION A-A" in svg


def test_home_page_is_ready_for_github_pages(client):
    page = client.get("/")
    assert page.status_code == 200
    html = page.text
    assert 'href="static/styles.css"' in html
    assert 'src="static/browser.js"' in html
    assert 'src="static/app.js"' in html
    assert "https://k-v-patel.github.io/Drawings-Generator/" in html
    assert 'href="/static/' not in html
    assert 'src="/static/' not in html


def test_extra_templates_are_refused(client):
    response = client.post("/api/templates/standard-idw/duplicate")
    assert response.status_code == 400
    removed = client.delete("/api/templates/signoff")
    assert removed.status_code == 400
    assert [item["id"] for item in client.get("/api/templates").json()] == ["standard-idw", "standard-dwg", "signoff"]


def test_old_branded_templates_are_replaced(tmp_path, monkeypatch):
    monkeypatch.setenv("DRAWINGS_DATA", str(tmp_path))
    import app.db as db
    import app.main as main

    importlib.reload(db)
    db.init_db()
    with db.connect() as conn:
        conn.execute(
            """
            INSERT INTO templates
            (id, name, drawing_type, applies_to, sheet_width_in, sheet_height_in, sheet_label, body_json, updated_at)
            VALUES ('norstar-part', 'Norstar part', 'part', 'ipt', 17, 11, 'B', '{}', '2020-01-01T00:00:00+00:00')
            """
        )
        conn.execute(
            "INSERT INTO bom_formats (id, name, is_default, body_json, updated_at) VALUES ('norstar-parts-list', 'Norstar parts list', 1, '{}', '2020-01-01T00:00:00+00:00')"
        )
    importlib.reload(main)
    with TestClient(main.app) as replaced:
        names = [item["name"] for item in replaced.get("/api/templates").json()]
        assert names == ["Standard.idw", "Standard.dwg", "Sign off"]
        assert replaced.get("/api/bom-formats").json()[0]["name"] == "Parts list"
