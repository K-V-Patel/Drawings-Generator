import importlib
import json
import subprocess
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

ROOT = Path(__file__).resolve().parents[1]


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


def test_ipt_sheet_has_no_parts_list_and_description_can_grow(client):
    description = (
        "Solid Square Cover Plate - End cover on the outrigger - 3.75 x 3.75 x 1/4. Corner 0.5rad"
    )
    created = client.post("/api/jobs", json={
        "fileName": "T12454.ipt",
        "fileKind": "ipt",
        "properties": {
            "partNumber": "T12454",
            "description": description,
            "material": "Steel, Mild",
            "thickness": "0.25",
        },
        "model": {
            "kind": "part",
            "overall": {"length": 3.75, "width": 3.75, "height": 0.25},
            "bends": [],
            "views": {},
        },
        "bomRows": [{"item": "1", "partNumber": "SHOULD-NOT-SHOW", "description": "Hidden row", "qty": "4"}],
    })
    assert created.status_code == 200, created.text
    job = created.json()
    assert job["bomReady"] is False
    generated = client.post(f"/api/jobs/{job['id']}/generate")
    assert generated.status_code == 200, generated.text
    svg = client.get(f"/api/jobs/{job['id']}/sheet.svg").text
    assert "T12454" in svg
    assert "Solid Square Cover Plate" in svg
    assert "Steel, Mild" in svg
    assert "THIRD ANGLE" in svg
    assert ">A</text>" in svg
    assert ">8</text>" in svg
    assert "BEND ID" not in svg
    assert "Parts List" not in svg
    assert "ITEM QTY" not in svg
    assert "SHOULD-NOT-SHOW" not in svg
    from app.drawing.frame import BLOCK_W, description_lines, title_block_height

    short = title_block_height({"description": "Center plate"}, BLOCK_W)
    long_text = " ".join(["Cover plate note"] * 12)
    assert len(long_text) <= 240
    assert len(description_lines(description, BLOCK_W)) == 2
    assert len(description_lines(long_text, BLOCK_W)) > 2
    assert title_block_height({"description": long_text}, BLOCK_W) > short
    tall = client.post("/api/jobs", json={
        "fileName": "Long.ipt",
        "fileKind": "ipt",
        "properties": {"partNumber": "LONG-1", "description": long_text, "material": "Steel"},
        "model": {"kind": "part", "overall": {"length": 10, "width": 4, "height": 0.25}, "bends": [], "views": {}},
    })
    assert tall.status_code == 200, tall.text
    tall_id = tall.json()["id"]
    assert client.post(f"/api/jobs/{tall_id}/generate").status_code == 200
    tall_svg = client.get(f"/api/jobs/{tall_id}/sheet.svg").text
    for line in description_lines(long_text, BLOCK_W):
        assert line in tall_svg
    assert "BEND ID" not in tall_svg


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
    assert "FRONT" in svg
    assert "SCALE" in svg
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
    assert 'src="static/inventor.js"' in html
    assert 'src="static/browser.js"' in html
    assert 'src="static/app.js"' in html
    assert html.index('src="static/inventor.js"') < html.index('src="static/browser.js"')
    assert "https://k-v-patel.github.io/Drawings-Generator/" in html
    assert 'href="/static/' not in html
    assert 'src="/static/' not in html


def test_ipt_parameters_are_read_and_the_sheet_opens(client):
    data = (ROOT / "tests/fixtures/inventor_sample_file.ipt").read_bytes()
    response = client.post(
        "/api/jobs",
        files={"file": ("inventor_sample_file.ipt", data, "application/octet-stream")},
    )
    assert response.status_code == 200, response.text
    job = response.json()
    assert job["properties"]["partNumber"] == "box"
    assert job["properties"]["material"] == "Generic"
    assert float(job["properties"]["thickness"]) == pytest.approx(0.5)
    overall = job["model"]["overall"]
    assert overall["length"] == pytest.approx(24)
    assert overall["width"] == pytest.approx(36)
    assert overall["height"] == pytest.approx(12)
    assert "Enter" not in " ".join(job["warnings"])
    generated = client.post(f"/api/jobs/{job['id']}/generate")
    assert generated.status_code == 200, generated.text
    svg = client.get(f"/api/jobs/{job['id']}/sheet.svg").text
    assert "box" in svg
    assert "Generic" in svg
    assert "FRONT" in svg
    assert "SCALE" in svg
    assert "NO PROFILE" not in svg


def test_flat_pattern_extents_fill_a_missing_custom_size():
    from app.inventor_file import DESIGN_TRACKING, USER_DEFINED, _map_sets, inches_from

    assert inches_from("25.4 mm") == pytest.approx(1)
    assert inches_from("2.54 cm") == pytest.approx(1)
    assert inches_from(5) == pytest.approx(5)
    props, overall = _map_sets([
        {"fmtid": DESIGN_TRACKING, "props": {5: "PLATE", 63: 25.4, 64: 50.8}, "names": {}},
        {"fmtid": USER_DEFINED, "props": {3: "0.25 in"}, "names": {3: "thickness"}},
    ])
    assert props["partNumber"] == "PLATE"
    assert props["thickness"] == "0.25"
    assert overall["length"] == pytest.approx(20)
    assert overall["width"] == pytest.approx(10)
    assert overall["height"] == pytest.approx(0.25)
    _, incomplete = _map_sets([
        {"fmtid": DESIGN_TRACKING, "props": {63: 25.4, 64: 50.8}, "names": {}},
    ])
    assert incomplete == {}


def test_description_supplies_the_overall_size(client):
    from app.inventor_file import size_from_text

    text = "Solid Square Cover Plate - End cover on the outrigger - 3.75 x 3.75 x 1/4. Corner 0.5rad"
    found = size_from_text(text)
    assert found["length"] == pytest.approx(3.75)
    assert found["width"] == pytest.approx(3.75)
    assert found["height"] == pytest.approx(0.25)
    assert size_from_text("Corner 0.5rad") == {}
    assert size_from_text("1-1/2 x 2 x 1/8") == {
        "length": pytest.approx(1.5),
        "width": pytest.approx(2),
        "height": pytest.approx(0.125),
    }
    payload = "Description".encode("utf-16le") + b"\x00\x00" + text.encode("utf-16le")
    uploaded = client.post("/api/jobs", files={"file": ("T12454.ipt", payload, "application/octet-stream")})
    assert uploaded.status_code == 200, uploaded.text
    job = uploaded.json()
    assert job["properties"]["partNumber"] == "T12454"
    assert job["properties"]["description"].startswith("Solid Square Cover Plate")
    assert job["model"]["overall"]["length"] == pytest.approx(3.75)
    assert job["model"]["overall"]["width"] == pytest.approx(3.75)
    assert job["model"]["overall"]["height"] == pytest.approx(0.25)
    assert float(job["properties"]["thickness"]) == pytest.approx(0.25)
    saved = client.post("/api/jobs", json={
        "fileName": "T12454.ipt",
        "fileKind": "ipt",
        "properties": {"partNumber": "T12454", "description": text},
        "model": {"kind": "part", "overall": {}, "views": {}},
    })
    assert saved.status_code == 200, saved.text
    generated = client.post(f"/api/jobs/{saved.json()['id']}/generate")
    assert generated.status_code == 200, generated.text
    assert generated.json()["model"]["overall"]["height"] == pytest.approx(0.25)
    svg = client.get(f"/api/jobs/{saved.json()['id']}/sheet.svg").text
    assert "T12454" in svg
    assert "FRONT" in svg
    assert "SCALE" in svg
    assert "3.750" in svg or "3.75" in svg
    beam = "UPDATE***I-beam - W 6 x 9 (5.9 x 3.94) - 31.6"
    beam_size = size_from_text(beam)
    assert beam_size["length"] == pytest.approx(31.6)
    assert beam_size["width"] == pytest.approx(3.94)
    assert beam_size["height"] == pytest.approx(5.9)
    assert set(beam_size) == {"length", "width", "height"}
    caster = "2408T71_Easy-Turn Caster with 6-5-8 x 4-3-4 Plate"
    caster_size = size_from_text(caster)
    assert caster_size["length"] == pytest.approx(6.625)
    assert caster_size["width"] == pytest.approx(4.75)
    assert "height" not in caster_size
    assert size_from_text("W 6 x 9") == {}
    caster_job = client.post("/api/jobs", json={
        "fileName": "T12455.ipt",
        "fileKind": "ipt",
        "properties": {"partNumber": "T12455", "description": caster},
        "model": {"kind": "part", "overall": {}, "views": {}},
    })
    assert caster_job.status_code == 200, caster_job.text
    caster_sheet = client.post(f"/api/jobs/{caster_job.json()['id']}/generate")
    assert caster_sheet.status_code == 200, caster_sheet.text
    assert caster_sheet.json()["model"]["overall"]["length"] == pytest.approx(6.625)
    assert caster_sheet.json()["model"]["overall"]["width"] == pytest.approx(4.75)
    assert not str(caster_sheet.json()["properties"].get("thickness") or "").strip()
    caster_svg = client.get(f"/api/jobs/{caster_job.json()['id']}/sheet.svg").text
    assert "6.625" in caster_svg
    assert "4.75" in caster_svg
    assert "FRONT" in caster_svg
    assert "SIDE" in caster_svg
    assert "SCALE" in caster_svg
    assert "Parts List" not in caster_svg


def test_beam_sheet_and_inventor_view_styles(client):
    beam = "UPDATE***I-beam - W 6 x 9 (5.9 x 3.94) - 31.6"
    saved = client.post("/api/jobs", json={
        "fileName": "T12452.ipt",
        "fileKind": "ipt",
        "properties": {"partNumber": "T12452", "description": beam},
        "model": {"kind": "part", "overall": {}, "views": {}},
    })
    assert saved.status_code == 200, saved.text
    job = saved.json()
    generated = client.post(f"/api/jobs/{job['id']}/generate")
    assert generated.status_code == 200, generated.text
    body = generated.json()
    assert body["model"]["overall"]["length"] == pytest.approx(31.6)
    assert body["model"]["overall"]["width"] == pytest.approx(3.94)
    assert body["model"]["overall"]["height"] == pytest.approx(5.9)
    assert not str(body["properties"].get("thickness") or "").strip()
    svg = client.get(f"/api/jobs/{job['id']}/sheet.svg").text
    assert "31.6" in svg
    assert "5.9" in svg
    assert "3.94" in svg
    assert "Parts List" not in svg
    assert "FRONT" in svg
    assert "SCALE" in svg
    assert "RASTER" not in svg
    roles = [view["role"] for view in client.get("/api/templates").json()[0]["views"]]
    for role in ("front", "side", "top", "bottom", "back", "end", "iso", "flat"):
        assert role in roles
    styled = client.put(f"/api/jobs/{job['id']}", json={
        "templateId": job["templateId"],
        "viewCount": 3,
        "selectedViews": ["front", "side", "iso"],
        "properties": body["properties"],
        "model": {
            "kind": "part",
            "overall": body["model"]["overall"],
            "views": {},
            "display": {"viewStyle": "raster", "annotationSize": 0.18, "annotationStyle": "bold", "balloons": True, "partsList": True},
        },
        "bomRows": [{"item": "1", "partNumber": "SHOULD-NOT-LIST", "description": "no", "qty": "1"}],
    })
    assert styled.status_code == 200, styled.text
    again = client.post(f"/api/jobs/{job['id']}/generate")
    assert again.status_code == 200, again.text
    raster = client.get(f"/api/jobs/{job['id']}/sheet.svg").text
    assert "RASTER" in raster
    assert 'font-size="0.1800"' in raster
    assert "#b7b2a8" in raster
    assert "Parts List" not in raster
    assert "SHOULD-NOT-LIST" not in raster
    hidden = client.put(f"/api/jobs/{job['id']}", json={
        "templateId": job["templateId"],
        "selectedViews": ["front", "iso"],
        "viewCount": 2,
        "properties": body["properties"],
        "model": {
            "kind": "part",
            "overall": body["model"]["overall"],
            "views": {},
            "display": {"viewStyle": "hidden-line", "annotationSize": 0.12},
        },
    })
    assert hidden.status_code == 200, hidden.text
    client.post(f"/api/jobs/{job['id']}/generate")
    dashed = client.get(f"/api/jobs/{job['id']}/sheet.svg").text
    assert "HIDDEN LINE" in dashed
    assert "stroke-dasharray" in dashed


def test_browser_reader_matches_the_sample_part():
    script = r"""
const fs = require("fs");
eval(fs.readFileSync("static/inventor.js", "utf8"));
const data = fs.readFileSync("tests/fixtures/inventor_sample_file.ipt");
const read = globalThis.drawgenInventor.read(data, "inventor_sample_file.ipt", "ipt");
console.log(JSON.stringify({
  partNumber: read.properties.partNumber,
  material: read.properties.material,
  thickness: read.properties.thickness,
  overall: read.overall,
  ok: read.ok
}));
"""
    completed = subprocess.run(
        ["node", "-e", script],
        cwd=ROOT,
        check=True,
        capture_output=True,
        text=True,
    )
    payload = json.loads(completed.stdout)
    assert payload["ok"] is True
    assert payload["partNumber"] == "box"
    assert payload["material"] == "Generic"
    assert float(payload["thickness"]) == pytest.approx(0.5)
    assert payload["overall"]["length"] == pytest.approx(24)
    assert payload["overall"]["width"] == pytest.approx(36)
    assert payload["overall"]["height"] == pytest.approx(12)


def test_browser_uses_the_description_size():
    script = r"""
const fs = require("fs");
const vm = require("vm");
const context = {
  console, TextDecoder, TextEncoder, URL, Blob,
  crypto: require("crypto").webcrypto,
};
context.globalThis = context;
context.window = context;
vm.createContext(context);
vm.runInContext(fs.readFileSync("static/inventor.js", "utf8"), context);
vm.runInContext(fs.readFileSync("static/browser.js", "utf8"), context);
const description = "Solid Square Cover Plate - End cover on the outrigger - 3.75 x 3.75 x 1/4. Corner 0.5rad";
const found = context.drawgenInventor.sizeFromText(description);
context.drawgenBrowser.handle("api/jobs", {
  method: "POST",
  headers: { "Content-Type": "application/json" },
  body: JSON.stringify({
    fileName: "T12454.ipt",
    fileKind: "ipt",
    properties: { partNumber: "T12454", description },
    model: { kind: "part", overall: {}, views: {} },
  }),
}).then((job) => context.drawgenBrowser.handle("api/jobs/" + job.id + "/generate", { method: "POST" }))
  .then((sheet) => {
    console.log(JSON.stringify({
      length: found.length,
      width: found.width,
      height: found.height,
      overall: sheet.model.overall,
      thickness: sheet.properties.thickness,
      partNumber: sheet.properties.partNumber,
    }));
  }).catch((error) => {
    console.error(error);
    process.exit(1);
  });
"""
    completed = subprocess.run(["node", "-e", script], cwd=ROOT, check=True, capture_output=True, text=True)
    payload = json.loads(completed.stdout)
    assert payload["length"] == pytest.approx(3.75)
    assert payload["width"] == pytest.approx(3.75)
    assert payload["height"] == pytest.approx(0.25)
    assert payload["overall"]["length"] == pytest.approx(3.75)
    assert payload["overall"]["height"] == pytest.approx(0.25)
    assert float(payload["thickness"]) == pytest.approx(0.25)
    assert payload["partNumber"] == "T12454"
    beam_script = r"""
const fs = require("fs");
const vm = require("vm");
const context = { console, TextDecoder, TextEncoder, URL, Blob, crypto: require("crypto").webcrypto };
context.globalThis = context;
context.window = context;
vm.createContext(context);
vm.runInContext(fs.readFileSync("static/inventor.js", "utf8"), context);
vm.runInContext(fs.readFileSync("static/browser.js", "utf8"), context);
const beam = "UPDATE***I-beam - W 6 x 9 (5.9 x 3.94) - 31.6";
const found = context.drawgenInventor.sizeFromText(beam);
context.drawgenBrowser.handle("api/jobs", {
  method: "POST",
  headers: { "Content-Type": "application/json" },
  body: JSON.stringify({
    fileName: "T12452.ipt",
    fileKind: "ipt",
    properties: { partNumber: "T12452", description: beam },
    model: { kind: "part", overall: {}, views: {}, display: { viewStyle: "raster", annotationSize: 0.18, balloons: true, partsList: true } },
  }),
}).then((job) => context.drawgenBrowser.handle("api/jobs/" + job.id + "/generate", { method: "POST" }))
  .then((sheet) => {
    const file = context.drawgenBrowser.buildFile(sheet.id, "sheet.svg");
    const svg = String(file.body);
    console.log(JSON.stringify({
      length: found.length, width: found.width, height: found.height, plate: found.plate,
      caster: context.drawgenInventor.sizeFromText("2408T71_Easy-Turn Caster with 6-5-8 x 4-3-4 Plate"),
      overall: sheet.model.overall,
      thickness: sheet.properties.thickness || "",
      raster: svg.includes("RASTER"),
      size: svg.includes('font-size="0.1800"'),
      fill: svg.includes("#b7b2a8"),
      parts: svg.includes("Parts List"),
      dim: svg.includes("31.6") && svg.includes("5.9") && svg.includes("3.94"),
    }));
  }).catch((error) => { console.error(error); process.exit(1); });
"""
    beam = subprocess.run(["node", "-e", beam_script], cwd=ROOT, check=True, capture_output=True, text=True)
    beam_payload = json.loads(beam.stdout)
    assert beam_payload["plate"] is False
    assert beam_payload["caster"]["length"] == pytest.approx(6.625)
    assert beam_payload["caster"]["width"] == pytest.approx(4.75)
    assert "height" not in beam_payload["caster"]
    assert beam_payload["length"] == pytest.approx(31.6)
    assert beam_payload["width"] == pytest.approx(3.94)
    assert beam_payload["height"] == pytest.approx(5.9)
    assert beam_payload["overall"]["length"] == pytest.approx(31.6)
    assert beam_payload["thickness"] == ""
    assert beam_payload["raster"] is True
    assert beam_payload["size"] is True
    assert beam_payload["fill"] is True
    assert beam_payload["parts"] is False
    assert beam_payload["dim"] is True


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


def test_inventor_json_export_keeps_the_gantry_description_and_parts_list(client):
    description = (
        "1,000 lb H-frame gantry crane. Easy-Turn casters with a 7.75 in mounting height. "
        "Steel frame is 11 ft 0 in from the bottom of the outrigger to the top of the runway. "
        "Caster plates are welded to the outrigger ends. Casters are fillet-welded to those plates. "
        "Hoist and runway trolleys stay loose."
    )
    assert len(description) > 240
    payload = {
        "schema": "drawgen/1",
        "fileName": "PGC H Frame Gantry Crane.iam",
        "fileKind": "iam",
        "properties": {
            "partNumber": "PGC H Frame Gantry Crane",
            "description": description,
            "material": "",
            "thickness": "",
            "designer": "Krupa Patel",
            "drawnBy": "Krupa Patel",
        },
        "model": {
            "kind": "assembly",
            "overall": {"length": 181.875, "width": 145.95, "height": 60.5},
            "bends": [],
            "components": [
                {"item": "3", "partNumber": "T12455", "description": "2468T71_Easy-Turn Caster with 6-5-8 x 4-3-4 Plate", "qty": "4"},
                {"item": "5", "partNumber": "T12461", "description": "PGC H Frame Gantry Crane Frame Weldment", "qty": "1"},
            ],
            "views": {},
        },
    }
    raw = "\ufeff".encode("utf-8") + json.dumps(payload).encode("utf-8")
    uploaded = client.post(
        "/api/jobs",
        files={"file": ("PGC H Frame Gantry Crane.drawgen.json", raw, "application/json")},
    )
    assert uploaded.status_code == 200, uploaded.text
    job = uploaded.json()
    assert job["sourceKind"] == "iam"
    assert job["bomReady"] is True
    assert job["properties"]["description"] == description
    assert job["model"]["overall"]["length"] == pytest.approx(181.875)
    assert [row["partNumber"] for row in job["bomRows"]] == ["T12455", "T12461"]
    generated = client.post(f"/api/jobs/{job['id']}/generate")
    assert generated.status_code == 200, generated.text
    sheet = generated.json()
    assert sheet["model"]["overall"]["length"] == pytest.approx(181.875)
    assert sheet["model"]["overall"]["width"] == pytest.approx(145.95)
    assert sheet["model"]["overall"]["height"] == pytest.approx(60.5)
    svg = client.get(f"/api/jobs/{job['id']}/sheet.svg").text
    assert "H-frame gantry crane" in svg
    assert "T12455" in svg
    assert "Parts List" in svg
    assert "181.875" in svg
    assert "60.5" in svg
    assert "1 : 100" not in svg
    assert "SCALE 1 :" in svg
    assert any("no view curves" in item["detail"] for item in sheet["sop"])
