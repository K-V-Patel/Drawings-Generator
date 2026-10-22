# Drawings Generator

Shop-floor app for production drawings of Inventor parts (`.ipt`) and assemblies (`.iam`).

## About

https://k-v-patel.github.io/Drawings-Generator/

Open that link to use the app. It is published with GitHub Pages from the `main` branch, the same way as https://k-v-patel.github.io/KrupaPatel-/.

## Deploy (GitHub Pages — free)

1. Push `index.html` and the `static/` folder to the `main` branch.
2. Settings → Pages → Source: `main` / root.
3. Live at https://k-v-patel.github.io/Drawings-Generator/ within a minute or two.

Open that address in a browser. The app loads there. No local server is required.

The flow matches the drawing note:

1. Drop an `.ipt` or an `.iam`.
2. The sheet opens from the part number, material, thickness, and overall size saved in the file.
3. Download PDF, DXF, or SVG.

There are three drawing templates: Standard.idw, Standard.dwg, and Sign off. The sheet uses the template that matches the file. Customer, order, and quote on a sign off sheet are not stored in the part file.

Part, weldment, assembly, and signoff sheets follow *What To Include On A Drawing SOP*: overall size, thickness, bend table (direction up), weld symbols, a top-left parts list with balloons, and the signoff block (customer, order, quote, signature, date, plus the unit lines).

## Open

https://k-v-patel.github.io/Drawings-Generator/

The project on GitHub is https://github.com/K-V-Patel/Drawings-Generator.

## Saved database (optional)

A shop computer can keep templates and issued sheets on disk. The public page does not need this.

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
uvicorn app.main:app --host 0.0.0.0 --port 8000
```

## How a sheet is built

Part sheets use front, side, and isometric views, plus a flat view when the part has bends. Overall height and width are dimensioned, thickness goes where it is easiest to see, and laser cut-outs that are already in the DXF are not dimensioned. Bends are listed with direction up.

Assembly sheets use as many views as production needs, with overall height, width, and depth, and a parts list with balloons in the top left. Weld symbols go on the clearest view when the assembly is a weldment.

Sign off sheets use a side elevation, a front view, an end cross-section, and inlet and discharge faces. Customer, order number, quote number, signature, and date sit in the lower left.

A file with no profiles and no saved overall size does not generate a sheet.

## Inventor file

Dropping the `.ipt` or `.iam` reads the part number, description, material, and exported length, width, height, and thickness. Sheet-metal flat extents are used when those parameters were not exported. A description written as length x width x thickness, such as `3.75 x 3.75 x 1/4`, supplies the size when the file has no exported envelope. The views are the envelope of that size. No part parameter is typed in.

Profile curves, bend lines, and a structured assembly BOM are still written by `tools/ExportDrawgen.vb`. Run it as an iLogic rule inside Inventor. It writes a `.drawgen.json` beside the model. Drop that file for a sheet that carries the real bend table and parts list. The envelope is labeled so it is not mistaken for a finished profile.

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
