# Drawings Generator

Shop-floor app for production drawings of Inventor parts (`.ipt`) and assemblies (`.iam`).

## About

https://k-v-patel.github.io/Drawings-Generator/

Open that link to use the app. It is published with GitHub Pages from the `main` branch, the same way as https://k-v-patel.github.io/KrupaPatel-/.

## Deploy (GitHub Pages — free)

1. Push `index.html` and the `static/` folder to the `main` branch.
2. Settings → Pages → Source: `main` / root.
3. Live at https://k-v-patel.github.io/Drawings-Generator/ within a minute or two.

Sheets opened from that link stay in the browser. The shop computer can still run the Python app below; that copy keeps a database on disk.

The flow matches the drawing note:

1. Drop an `.ipt` or an `.iam`.
2. Pick a drawing template. There are three: Standard.idw, Standard.dwg, and Sign off.
3. For an assembly, the BOM is built immediately in the saved column format. Edit the cells before the sheet is issued.
4. Say how many views are needed. The minimum is 2.
5. Generate the sheet. Download PDF, DXF, or SVG.

Part, weldment, assembly, and signoff sheets follow *What To Include On A Drawing SOP*: overall size, thickness, bend table (direction up), weld symbols, a top-left parts list with balloons, and the signoff block (customer, order, quote, signature, date, plus the unit lines).

## Run

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
uvicorn app.main:app --port 8000
```

Open http://localhost:8000. The public page is https://k-v-patel.github.io/Drawings-Generator/. The project on GitHub is https://github.com/K-V-Patel/Drawings-Generator.

The same page also opens with no install:

```bash
python3 -m http.server 8000
```

## How a sheet is built

Part sheets use front, side, and isometric views, plus a flat view when the part has bends. Overall height and width are dimensioned, thickness goes where it is easiest to see, and laser cut-outs that are already in the DXF are not dimensioned. Bends are listed with direction up.

Assembly sheets use as many views as production needs, with overall height, width, and depth, and a parts list with balloons in the top left. Weld symbols go on the clearest view when the assembly is a weldment.

Sign off sheets use a side elevation, a front view, an end cross-section, and inlet and discharge faces. Customer, order number, quote number, signature, and date sit in the lower left.

A file with no profiles and no overall size does not generate a sheet. Enter the size, or drop the `.drawgen.json` from Inventor.

## Inventor export

Profiles, bend lines, and the assembly tree are not stored in a form this app can rebuild from the `.ipt` / `.iam` alone. The app reads summary properties and any property names it can see, then dimensions an overall envelope.

Run `tools/ExportDrawgen.vb` as an iLogic rule inside Inventor. It writes a `.drawgen.json` beside the model (overall size, iProperties, sheet-metal bends, structured BOM). Drop that file here for a sheet that carries the real BOM and bend table. View curves still need the model; the envelope is labeled so it is not mistaken for a finished profile.

## Drawing templates

The app offers three templates:

- Standard.idw
- Standard.dwg
- Sign off

The two standard files are the English Inventor templates in `C:\Users\Public\Documents\Autodesk\Inventor 2025\Templates\en-US`. Sign off is the third sheet, for a unit approval drawing. Sheet size, views, and the title block of each one can be edited. The list does not grow past these three.

## What is stored

SQLite in `data/drawings.sqlite` holds drawing templates, BOM formats, and issued jobs. A generated sheet keeps a snapshot of the template and BOM format, so later edits do not rewrite a sheet that was already issued.

## Checks

```bash
pytest
```
