# Drawings Generator

Shop-floor app for production drawings of Inventor parts (`.ipt`) and assemblies (`.iam`).

## Open it

https://proprietary-piece-deny-calculated.trycloudflare.com

That address is a temporary tunnel to the copy of this app running with the project. It stays up while that machine is on. There is no sign-in, so the link is unlisted rather than private. The same app on this machine is at http://localhost:8000.

The flow matches the drawing note:

1. Drop an `.ipt` or an `.iam`.
2. Pick a drawing template. Templates are stored in the app and can be edited.
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

Open https://proprietary-piece-deny-calculated.trycloudflare.com, or `http://localhost:8000` on this machine.

## Worked examples

Norstar sheets are rebuilt from the figures in the Creating Drawings SOP (center pivot plate, CCRB body weldment, CCRB head assembly, AVF conveyor signoff).

Meridian sheets are sample jobs in that same pattern, standing in for `T:\Engineering\Custom Projects\Meridian`. That folder was not available when this app was built. Norstar's live models live under `T:\Engineering\Custom Projects\Norstar Ind.` and were not mounted here either. Sample sheets are marked on the border. Confirm them against the Inventor model before issue.

## Inventor export

Profiles, bend lines, and the assembly tree are not stored in a form this app can rebuild from the `.ipt` / `.iam` alone. The app reads summary properties and any property names it can see, then dimensions an overall envelope.

Run `tools/ExportDrawgen.vb` as an iLogic rule inside Inventor. It writes a `.drawgen.json` beside the model (overall size, iProperties, sheet-metal bends, structured BOM). Drop that file here for a sheet that carries the real BOM and bend table. View curves still need the model; the envelope is labeled so it is not mistaken for a finished profile.

## What is stored

SQLite in `data/drawings.sqlite` holds drawing templates, BOM formats, and issued jobs. A generated sheet keeps a snapshot of the template and BOM format, so later edits do not rewrite a sheet that was already issued.

## Checks

```bash
pytest
```
