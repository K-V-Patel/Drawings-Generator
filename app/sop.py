"""Checks from What To Include On A Drawing SOP."""

from __future__ import annotations


def _blank(value) -> bool:
    return not str(value or "").strip() or str(value).strip() in {"—", "-"}


def _view_roles(job: dict) -> list[str]:
    return list(job.get("selected_views") or [])


def _authored(model: dict, role: str) -> dict:
    return ((model.get("views") or {}).get(role)) or {}


def _has_profile(model: dict, role: str) -> bool:
    view = _authored(model, role)
    return bool(view.get("paths") or view.get("circles") or view.get("arcs"))


def _envelope_only(model: dict, roles: list[str]) -> bool:
    if not roles:
        return False
    return all(not _has_profile(model, role) for role in roles)


def _bend_lines(model: dict) -> int:
    count = 0
    for path in (_authored(model, "flat").get("paths") or []):
        if path.get("bend"):
            count += 1
    return count


def _symbols(model: dict, key: str) -> list:
    found = []
    for view in (model.get("views") or {}).values():
        found.extend(view.get(key) or [])
    return found


def review(template: dict, job: dict) -> list[dict]:
    drawing_type = template.get("drawing_type") or "part"
    props = job.get("properties") or {}
    model = job.get("model") or {}
    roles = _view_roles(job)
    checks: list[dict] = []

    def add(status: str, rule: str, detail: str):
        checks.append({"status": status, "rule": rule, "detail": detail})

    if len(roles) < 2:
        add("fail", "View count", "A production sheet needs at least 2 views.")
    else:
        add("pass", "View count", f"{len(roles)} views. Minimum is 2.")

    if _envelope_only(model, roles):
        add(
            "warn",
            "Profiles",
            "These views are the overall envelope. The file has no view curves.",
        )
    else:
        add("pass", "Profiles", "At least one view has model geometry.")

    if _blank(props.get("partNumber")) or _blank(props.get("description")):
        add("warn", "Drawing identity", "Part number and description both belong in the title block.")
    else:
        add("pass", "Drawing identity", f"{props.get('partNumber')} — {props.get('description')}")

    if drawing_type == "part":
        _part(add, props, model, roles)
    elif drawing_type == "weldment":
        _weldment(add, model, job, roles)
    elif drawing_type == "assembly":
        _assembly(add, job, roles)
    elif drawing_type == "signoff":
        _signoff(add, props, model, roles, template)
    return checks


def _part(add, props, model, roles):
    bends = model.get("bends") or []
    if _blank(props.get("material")):
        add("warn", "Material", "The title block needs the material type.")
    else:
        add("pass", "Material", str(props.get("material")))
    if _blank(props.get("thickness")):
        add("warn", "Thickness", "Dimension the thickness where it is easiest to read, and fill it in on the title block.")
    else:
        add("pass", "Thickness", str(props.get("thickness")))
    if bends:
        if "flat" not in roles:
            add("warn", "Flat view", "A part with bends needs a flat view as well as the formed views.")
        else:
            add("pass", "Flat view", "Flat pattern is on the sheet.")
        lines = _bend_lines(model)
        if lines < len(bends):
            add("warn", "Bend lines", "Bend lines and bend IDs need to be on the flat. Notch a bend that is not parallel to a flat face.")
        else:
            add("pass", "Bend lines", f"{lines} bend line(s) on the flat pattern.")
        down = [b for b in bends if str(b.get("direction", "")).upper() not in {"UP", "U"}]
        if down:
            add("warn", "Bend direction", "Bend direction should be up whenever possible.")
        else:
            add("pass", "Bend direction", "Bends are called out UP.")
        incomplete = [b for b in bends if _blank(b.get("id")) or _blank(b.get("angle")) or _blank(b.get("radius"))]
        if incomplete:
            add("warn", "Bend table", "Each bend needs an ID, direction, angle, and radius.")
        else:
            add("pass", "Bend table", f"{len(bends)} bend(s) in the table.")
    else:
        add("pass", "Bends", "No bends on this part. Side, front, and isometric are the usual set.")
    if "front" in roles and "side" in roles:
        add("pass", "Orthographic views", "Front and side are both on the sheet for overall height and width.")
    else:
        add("warn", "Orthographic views", "Dimension overall height and width on the side and front, and on the flat when there is one.")
    add("pass", "Laser cuts", "Cut-outs that are in the DXF do not need dimensions. Confirm before adding them.")


def _weldment(add, model, job, roles):
    _overall(add, model)
    _parts_list(add, job, model)
    welds = model.get("welds") or []
    symbols = _symbols(model, "welds")
    if not welds and not symbols:
        add("warn", "Weld symbols", "Add the weld symbols on the clearest view, or coordinate with the welding department.")
    elif symbols:
        add("pass", "Weld symbols", "Weld symbols are placed on a view.")
    else:
        add("warn", "Weld symbols", "Welds are listed but not shown on a view yet.")
    if len(roles) < 3:
        add("warn", "Weldment views", "Use as many views as production needs. Side, front or back, top or bottom, and an isometric is typical.")
    else:
        add("pass", "Weldment views", "Enough views are selected to describe the weldment.")


def _assembly(add, job, roles):
    model = job.get("model") or {}
    _overall(add, model)
    _parts_list(add, job, model)
    if len(roles) < 3:
        add("warn", "Assembly views", "Use as many views as production needs. Side, front or back, top or bottom, and an isometric is typical.")
    else:
        add("pass", "Assembly views", "Enough views are selected to describe the assembly.")


def _parts_list(add, job, model):
    rows = job.get("bom_rows") or []
    if not rows:
        add("warn", "Parts list", "The parts list in the top left needs every part and quantity.")
        return
    add("pass", "Parts list", f"{len(rows)} item(s) in the saved BOM format.")
    balloons = _symbols(model, "balloons")
    item_ids = {str(row.get("item")) for row in rows}
    balloon_ids = {str(b.get("item")) for b in balloons}
    if not balloons:
        add("warn", "Balloons", "Numbered balloons should point at each part in the list.")
    elif item_ids - balloon_ids:
        missing = ", ".join(sorted(item_ids - balloon_ids))
        add("warn", "Balloons", f"No balloon yet for item {missing}.")
    else:
        add("pass", "Balloons", "Every parts-list item has a balloon.")


def _overall(add, model):
    overall = model.get("overall") or {}
    missing = [name for name in ("length", "width", "height") if not overall.get(name)]
    if missing:
        add("warn", "Overall size", "Dimension overall height, width, and depth. Missing: " + ", ".join(missing) + ".")
    else:
        add("pass", "Overall size", "Length, width, and height are on the model card.")


def _signoff(add, props, model, roles, template):
    needed = {"side", "section"}
    faces = {"inlet", "discharge"}
    if not needed <= set(roles):
        add("warn", "Signoff views", "Show a side view and an end cross-section, plus a front view.")
    else:
        add("pass", "Signoff views", "Side and end cross-section are selected.")
    if not faces & set(roles):
        add("warn", "Flange faces", "Show face views of the inlet and the discharge with flange size and opening size.")
    else:
        add("pass", "Flange faces", "A flange face view is on the sheet.")
    sections = model.get("sections") or []
    if len(sections) < 2:
        add("warn", "Sections", "On the side view, dimension each section length and label the section.")
    else:
        add("pass", "Sections", f"{len(sections)} section lengths are labeled.")
    for key, label in (
        ("customer", "Customer name"),
        ("orderNumber", "Order number"),
        ("quoteNumber", "Quote number"),
    ):
        if _blank(props.get(key)):
            add("warn", label, f"{label} belongs in the lower-left signoff block.")
        else:
            add("pass", label, str(props.get(key)))
    add("pass", "Signature and date", "Signature and date lines are part of the signoff block.")
    if not template.get("signoff_fields"):
        add("warn", "Unit info", "Add the unit-specific lines for this product. Chain conveyor, u-trough, and bucket elevator each differ.")
