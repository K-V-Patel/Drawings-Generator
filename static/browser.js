/* Browser copy of the shop API, used when GitHub Pages has no Python server. */
(function () {
  const SHOP = "C:\\Users\\Public\\Documents\\Autodesk\\Inventor 2025\\Templates\\en-US";
  const LOCKED = "The drawing templates are Standard.idw, Standard.dwg, and Sign off.";
  const KEY = "drawings-generator-v1";
  const SCHEMA = ["internalname", "mnemonic=", "categoryparameter", "displayname=", "propfmtid", "propertyset"];
  const PROP_NAMES = {
    "Part Number": "partNumber",
    PartNumber: "partNumber",
    Description: "description",
    Title: "title",
    Subject: "subject",
    Designer: "designer",
    Author: "drawnBy",
    Material: "material",
    "Stock Number": "stockNumber",
    "Revision Number": "rev",
    Revision: "rev",
    Project: "project",
    Comments: "comments",
    Keywords: "keywords",
    Vendor: "vendor",
  };
  const LAYER_PX = { BORDER: 1.8, OBJECT: 1.35, THIN: 0.9, DIM: 0.85, CENTER: 0.85, HIDDEN: 0.85, TEXT: 0.8, HATCH: 0.7, TABLE: 1.05 };
  const BEND_COLUMNS = [
    { key: "id", heading: "BEND ID", width: 0.18 },
    { key: "direction", heading: "BEND DIRECTION", width: 0.32 },
    { key: "angle", heading: "BEND ANGLE", width: 0.25 },
    { key: "radius", heading: "BEND RADIUS", width: 0.25 },
  ];
  const COMPANY = {
    name: "",
    sub: "",
    mark: "none",
    productSeries: "",
    standard: "THIS DRAWING CONFORMS TO ASME Y14.5M-1994 FOR DOCUMENTATION PRACTICES",
    proprietary: "",
    tolerances: [],
  };
  const STANDARD_VIEWS = [
    { role: "front", label: "FRONT" },
    { role: "side", label: "SIDE" },
    { role: "top", label: "TOP" },
    { role: "end", label: "END" },
    { role: "iso", label: "ISOMETRIC" },
    { role: "flat", label: "FLAT PATTERN" },
    { role: "bottom", label: "BOTTOM" },
    { role: "back", label: "BACK" },
  ];
  const SIGNOFF_VIEWS = [
    { role: "side", label: "SIDE ELEVATION" },
    { role: "front", label: "FRONT" },
    { role: "section", label: "SECTION A-A" },
    { role: "inlet", label: "INLET FLANGE" },
    { role: "discharge", label: "DISCHARGE FLANGE" },
  ];
  const STANDARD_NOTES = "Standard drawing. A part uses front, side, and isometric, plus a flat view when it has bends. Dimension overall height and width, and thickness where it is easiest to see. Do not dimension laser cut-outs that are also in the DXF. An assembly uses as many views as production needs, with overall height, width, and depth, and a parts list with balloons in the top left. A weldment adds weld symbols on the clearest view.";
  const SIGNOFF_NOTES = "Sign off sheet. Side elevation with overall length and height, discharge height, and each section length. Front view, an end cross-section of the ordered height and width, and face views of the inlet and discharge with flange size and the opening. Customer, order number, quote number, signature, and date sit in the lower left.";
  const ROLE_LABELS = {
    flat: "FLAT PATTERN", front: "FRONT", side: "SIDE", top: "TOP", bottom: "BOTTOM", back: "BACK",
    end: "END", iso: "ISOMETRIC", section: "SECTION A-A", inlet: "INLET FLANGE", discharge: "DISCHARGE FLANGE", detail: "DETAIL",
  };

  function stamp() {
    return new Date().toISOString();
  }

  function newId() {
    const bytes = new Uint8Array(6);
    if (globalThis.crypto && crypto.getRandomValues) crypto.getRandomValues(bytes);
    else for (let i = 0; i < bytes.length; i += 1) bytes[i] = Math.floor(Math.random() * 256);
    return [...bytes].map((b) => b.toString(16).padStart(2, "0")).join("");
  }

  function clone(value) {
    return JSON.parse(JSON.stringify(value));
  }

  function num(value, fallback = 0) {
    const parsed = Number(value);
    return Number.isFinite(parsed) ? parsed : fallback;
  }

  function blank(value) {
    const text = String(value ?? "").trim();
    return !text || text === "—" || text === "-";
  }

  function acceptable(value) {
    const text = String(value ?? "").trim();
    if (!text || text.length > 800) return false;
    const lowered = text.toLowerCase();
    if (SCHEMA.some((marker) => lowered.includes(marker))) return false;
    if (/[{}<>]/.test(text)) return false;
    if (lowered.startsWith("key:") || text.startsWith("*")) return false;
    return true;
  }

  function sanitize(props, fallbackName) {
    const cleaned = { ...(props || {}) };
    ["partNumber", "description", "material", "title", "subject", "designer", "drawnBy", "rev", "project", "stockNumber", "comments", "vendor", "mass", "thickness", "productSeries", "customer", "orderNumber", "quoteNumber"].forEach((key) => {
      if (cleaned[key] != null && cleaned[key] !== "" && !acceptable(cleaned[key])) cleaned[key] = "";
    });
    if (!acceptable(cleaned.partNumber)) {
      const stem = String(fallbackName || "").replace(/\.[^.]+$/, "").trim();
      cleaned.partNumber = acceptable(stem) ? stem : "";
    }
    return cleaned;
  }

  function template(id, name, drawingType, appliesTo, width, height, label, views, table, notes, defaults) {
    return {
      id, name, drawingType, appliesTo, sheetWidthIn: width, sheetHeightIn: height, sheetLabel: label,
      company: clone(COMPANY), views, defaultViews: defaults, table, signoffFields: [], sopNotes: notes,
      source: null, updatedAt: stamp(),
    };
  }

  function seedState() {
    return {
      templates: [
        template("standard-idw", "Standard.idw", "standard", "both", 17, 11, "B", STANDARD_VIEWS, { kind: "auto" }, STANDARD_NOTES, ["front", "side", "iso"]),
        template("standard-dwg", "Standard.dwg", "standard", "both", 17, 11, "B", STANDARD_VIEWS, { kind: "auto" }, STANDARD_NOTES, ["front", "side", "iso"]),
        template("signoff", "Sign off", "signoff", "both", 34, 22, "D", SIGNOFF_VIEWS, { kind: "signoff" }, SIGNOFF_NOTES, ["side", "front", "section", "inlet", "discharge"]),
      ],
      formats: [{
        id: "parts-list", name: "Parts list", isDefault: true, title: "Parts List", placement: "top-left",
        showBalloons: true, updatedAt: stamp(),
        columns: [
          { key: "item", heading: "ITEM", width: 0.12 },
          { key: "partNumber", heading: "PART NUMBER", width: 0.24 },
          { key: "description", heading: "DESCRIPTION", width: 0.48 },
          { key: "qty", heading: "ITEM QTY", width: 0.16 },
        ],
      }],
      jobs: [],
    };
  }

  function memoryStore() {
    const box = {};
    return {
      getItem: (key) => (key in box ? box[key] : null),
      setItem: (key, value) => { box[key] = String(value); },
      removeItem: (key) => { delete box[key]; },
    };
  }

  function store() {
    try {
      if (typeof localStorage !== "undefined") {
        const probe = `${KEY}-probe`;
        localStorage.setItem(probe, "1");
        localStorage.removeItem(probe);
        return localStorage;
      }
    } catch (error) {
      /* private mode */
    }
    if (!memoryStore.current) memoryStore.current = memoryStore();
    return memoryStore.current;
  }

  function load() {
    let saved = null;
    try { saved = JSON.parse(store().getItem(KEY) || "null"); } catch (error) { saved = null; }
    const fresh = seedState();
    if (!saved || !Array.isArray(saved.jobs)) return fresh;
    const kept = new Map((saved.templates || []).map((item) => [item.id, item]));
    fresh.templates = fresh.templates.map((item) => {
      const saved = kept.get(item.id);
      if (!saved) return item;
      const views = (saved.views || []).slice();
      const have = new Set(views.map((view) => view.role));
      (item.views || []).forEach((view) => { if (!have.has(view.role)) views.push(view); });
      return { ...saved, views };
    });
    if (Array.isArray(saved.formats) && saved.formats.length) fresh.formats = saved.formats;
    fresh.jobs = saved.jobs;
    return fresh;
  }

  function save(state) {
    store().setItem(KEY, JSON.stringify(state));
  }

  function read() {
    const state = load();
    return state;
  }

  function write(state) {
    save(state);
    return state;
  }

  function templates() {
    const order = { "standard-idw": 0, "standard-dwg": 1, signoff: 2 };
    return read().templates.slice().sort((a, b) => (order[a.id] ?? 9) - (order[b.id] ?? 9) || a.name.localeCompare(b.name));
  }

  function formats() {
    return read().formats.slice().sort((a, b) => a.name.localeCompare(b.name));
  }

  function templateById(id) {
    const found = templates().find((item) => item.id === id);
    if (!found) throw new Error("That drawing template is no longer in the library.");
    return found;
  }

  function formatById(id) {
    const all = formats();
    if (id) {
      const found = all.find((item) => item.id === id);
      if (found) return found;
    }
    return all.find((item) => item.isDefault) || all[0] || null;
  }

  function normalizeColumns(columns) {
    const cleaned = [];
    (columns || []).forEach((column) => {
      const key = String(column.key || "").trim();
      const heading = String(column.heading || "").trim();
      if (!key || !heading) return;
      cleaned.push({ key, heading, width: num(column.width) });
    });
    const total = cleaned.reduce((sum, column) => sum + column.width, 0) || cleaned.length || 1;
    cleaned.forEach((column) => {
      if (column.width <= 0) column.width = 1;
      column.width = Math.round((column.width / total) * 10000) / 10000;
    });
    if (cleaned.length) {
      const drift = Math.round((1 - cleaned.reduce((sum, column) => sum + column.width, 0)) * 10000) / 10000;
      cleaned[cleaned.length - 1].width = Math.round((cleaned[cleaned.length - 1].width + drift) * 10000) / 10000;
    }
    return cleaned;
  }

  function resolvedType(item, job) {
    const kind = item.drawingType || "part";
    if (kind !== "standard") return kind;
    const modelKind = job.model && job.model.kind;
    if (modelKind === "weldment") return "weldment";
    if (job.sourceKind === "iam" || modelKind === "assembly") return "assembly";
    return "part";
  }

  function effective(item, job) {
    const drawing = resolvedType(item, job);
    let table = { ...(item.table || {}) };
    if (item.drawingType === "standard" || !table.kind || table.kind === "auto") {
      if (drawing === "part") table = { kind: "bend", title: "TABLE", columns: clone(BEND_COLUMNS) };
      else if (drawing === "signoff") table = { kind: "signoff" };
      else table = { kind: "parts", title: "Parts List" };
    }
    return { ...item, drawingType: drawing, table };
  }

  function defaultViews(item, parsed) {
    const order = (item.views || []).map((view) => view.role);
    if (item.drawingType === "standard") {
      const modelKind = parsed.model && parsed.model.kind;
      let preferred = ["front", "side", "iso"];
      if (parsed.fileKind === "iam" || modelKind === "assembly" || modelKind === "weldment") preferred = ["side", "front", "end", "iso"];
      else if (parsed.model && parsed.model.bends && parsed.model.bends.length) preferred = ["front", "side", "iso", "flat"];
      return preferred.filter((role) => order.includes(role));
    }
    return (item.defaultViews || order).filter((role) => order.includes(role));
  }

  function viewsFor(item, parsed) {
    const order = (item.views || []).map((view) => view.role);
    let requested = parsed.selectedViews;
    if (requested == null) requested = parsed.views;
    let count = parsed.viewCount;
    if (count != null) {
      count = Number(count);
      if (!Number.isFinite(count)) throw new Error("View count has to be a number.");
      if (count < 2) throw new Error("At least 2 views are required.");
    }
    if (requested) {
      let chosen = requested.filter((role) => order.includes(role));
      if (chosen.length < 2) throw new Error("At least 2 views are required.");
      if (count && chosen.length > count) chosen = chosen.slice(0, count);
      return chosen;
    }
    let chosen = defaultViews(item, parsed);
    if (count && chosen.length > count) chosen = chosen.slice(0, count);
    if (chosen.length < 2) throw new Error("This template needs at least two views before a sheet can be made.");
    return chosen;
  }

  function chooseTemplate(parsed) {
    const all = templates();
    if (!all.length) throw new Error("Add a drawing template before starting a sheet.");
    if (parsed.templateId) {
      const match = all.find((item) => item.id === parsed.templateId);
      if (match) return match;
    }
    if (parsed.model && parsed.model.kind === "signoff") {
      const match = all.find((item) => item.drawingType === "signoff");
      if (match) return match;
    }
    return all.find((item) => item.id === "standard-idw") || all[0];
  }

  function geometry(view) {
    return !!(view && (view.paths || view.circles || view.arcs || view.hatch));
  }

  function describedOverall(props, overall) {
    const size = { ...(overall || {}) };
    const inventor = typeof globalThis !== "undefined" ? globalThis.drawgenInventor : null;
    if (!inventor || !inventor.sizeFromText) return size;
    if (["length", "width", "height"].every((key) => Number(size[key]) > 0)) return size;
    const text = [props.description, props.title, props.subject, props.comments].filter(Boolean).join(" ");
    const found = inventor.sizeFromText(text);
    if (!found) return size;
    ["length", "width", "height"].forEach((key) => {
      if (!(Number(size[key]) > 0)) size[key] = found[key];
    });
    if (found.plate && !props.thickness) props.thickness = String(Math.round(found.height * 10000) / 10000);
    return size;
  }

  function applyDescribedSize(job) {
    const model = job.model || {};
    const props = job.properties || {};
    const before = JSON.stringify(model.overall || {});
    const overall = describedOverall(props, model.overall || {});
    const changed = JSON.stringify(overall) !== before || (props.thickness && !(job.properties || {}).thickness);
    model.overall = overall;
    job.model = model;
    job.properties = props;
    return num(overall.length) > 0 && num(overall.width) > 0 && (changed || before === "{}");
  }

  function drawable(job) {
    const overall = (job.model && job.model.overall) || {};
    const sized = num(overall.length) > 0 && num(overall.width) > 0;
    if (sized) return true;
    return Object.values((job.model && job.model.views) || {}).some((view) => view && typeof view === "object" && geometry(view));
  }

  function present(job) {
    const item = job.templateId ? templateById(job.templateId) : null;
    const copy = {
      ...job,
      properties: sanitize(job.properties, job.sourceName || ""),
      sop: job.sop,
      hasSheet: !!job.snapshot,
    };
    if (copy.sop == null && item) copy.sop = review(effective(item, copy), forRules(copy));
    copy.bomReady = copy.sourceKind === "iam";
    if (copy.sourceKind === "ipt") copy.bomRows = [];
    return copy;
  }

  function forRules(job) {
    return { selected_views: job.selectedViews, properties: job.properties, model: job.model, bom_rows: job.bomRows };
  }

  function cleanProps(props, description) {
    const cleaned = sanitize(props);
    return {
      partNumber: cleaned.partNumber || "",
      description: acceptable(description) ? description : "",
      material: cleaned.material || "",
      thickness: cleaned.thickness || "",
      mass: cleaned.mass || "",
      rev: cleaned.rev || "",
      drawnBy: cleaned.drawnBy || "",
      drawnDate: "",
      designer: cleaned.designer || "",
      designerDate: "",
      checker: "",
      scale: "SEE ABOVE",
      sheetNumber: "1",
      sheetCount: "1",
      productSeries: "",
      customer: "",
      orderNumber: "",
      quoteNumber: "",
      signature: "",
      signDate: "",
      extras: {},
    };
  }

  function fromDrawgen(payload, filename) {
    if (!payload || typeof payload !== "object" || Array.isArray(payload)) throw new Error("The JSON export has to be an object.");
    const props = { ...(payload.properties || {}) };
    const model = { ...(payload.model || {}) };
    let kind = payload.fileKind;
    if (kind !== "ipt" && kind !== "iam") kind = model.kind === "part" ? "ipt" : "iam";
    const rows = payload.bomRows != null ? payload.bomRows : (model.components || []).map((item) => ({
      item: String(item.item ?? ""), partNumber: item.partNumber || "", description: item.description || "", qty: String(item.qty ?? ""),
    }));
    return {
      fileName: payload.fileName || filename,
      fileKind: kind,
      templateId: payload.templateId,
      bomFormatId: payload.bomFormatId,
      viewCount: payload.viewCount,
      selectedViews: payload.views || payload.selectedViews,
      properties: props,
      model,
      bomRows: kind === "ipt" ? [] : rows,
      warnings: payload.warnings || [],
      sample: !!payload.sample,
      sampleNote: payload.sampleNote || "",
      exampleId: payload.id,
    };
  }

  function utf16Strings(data) {
    const found = [];
    const bytes = new Uint8Array(data);
    let i = 0;
    while (i < bytes.length - 1) {
      let chars = "";
      let j = i;
      while (j < bytes.length - 1) {
        const code = bytes[j] | (bytes[j + 1] << 8);
        if (code >= 32 && code <= 126) {
          chars += String.fromCharCode(code);
          j += 2;
        } else break;
      }
      if (chars.length >= 3) {
        found.push(chars);
        i = j + 2;
      } else i += 1;
    }
    return found;
  }

  function splitNames(strings) {
    const names = Object.keys(PROP_NAMES).sort((a, b) => b.length - a.length);
    const pieces = [];
    strings.forEach((value) => {
      let remaining = value;
      while (remaining) {
        let foundAt = -1;
        let foundName = "";
        names.forEach((name) => {
          const index = remaining.indexOf(name);
          if (index > 0 && (foundAt < 0 || index < foundAt)) {
            foundAt = index;
            foundName = name;
          }
        });
        if (foundAt < 0) {
          pieces.push(remaining);
          break;
        }
        pieces.push(remaining.slice(0, foundAt), foundName);
        remaining = remaining.slice(foundAt + foundName.length);
      }
    });
    return pieces;
  }

  function scrape(data) {
    const strings = splitNames(utf16Strings(data));
    const props = {};
    strings.forEach((value, index) => {
      const key = PROP_NAMES[value];
      if (!key || index + 1 >= strings.length) return;
      const next = strings[index + 1].trim();
      if (PROP_NAMES[next] || !acceptable(next)) return;
      if (props[key] == null) props[key] = next;
    });
    return props;
  }

  function fromInventor(filename, data, kind) {
    const warnings = [];
    const bytes = new Uint8Array(data);
    const ole = bytes.length >= 8 && bytes[0] === 0xd0 && bytes[1] === 0xcf && bytes[2] === 0x11 && bytes[3] === 0xe0;
    const props = {};
    let overall = {};
    let bomRows = [];
    let parsed = false;
    if (!ole) warnings.push("This file is not an OLE compound document. Inventor parts and assemblies usually are.");
    const inventor = typeof globalThis !== "undefined" ? globalThis.drawgenInventor : null;
    if (ole && inventor) {
      const read = inventor.read(bytes, filename, kind);
      parsed = !!(read && read.ok);
      Object.assign(props, (read && read.properties) || {});
      overall = (read && read.overall) || {};
      bomRows = (read && read.bomRows) || [];
    }
    if (!parsed) {
      const scraped = scrape(data);
      Object.keys(scraped).forEach((key) => {
        if (!props[key]) props[key] = scraped[key];
      });
    }
    if (!props.partNumber) {
      props.partNumber = filename.replace(/\.[^.]+$/, "");
      warnings.push("Part number was taken from the file name.");
    }
    overall = describedOverall(props, overall);
    const face = num(overall.length) > 0 && num(overall.width) > 0;
    const full = face && num(overall.height) > 0;
    if (!face) {
      overall = {};
      warnings.push("This file has no saved overall size. A sheet is not generated.");
    } else if (!full) warnings.push("Length and width were read from the file. Thickness was not in the file.");
    else warnings.push("Overall size, part number, and material were read from the file. Views show that envelope.");
    if (kind === "ipt") bomRows = [];
    const description = props.description || props.subject || props.title || "";
    return {
      fileName: filename,
      fileKind: kind,
      properties: cleanProps(props, description),
      model: {
        kind: kind === "ipt" ? "part" : "assembly",
        overall,
        bends: [],
        welds: [],
        components: bomRows.map((row) => ({ ...row })),
        views: {},
        sections: [],
      },
      bomRows,
      warnings,
      sample: false,
      sampleNote: "",
    };
  }

  async function unzipJson(buffer) {
    const bytes = new Uint8Array(buffer);
    const view = new DataView(bytes.buffer, bytes.byteOffset, bytes.byteLength);
    let eocd = -1;
    for (let i = bytes.length - 22; i >= Math.max(0, bytes.length - 22 - 65535); i -= 1) {
      if (view.getUint32(i, true) === 0x06054b50) { eocd = i; break; }
    }
    if (eocd < 0) throw new Error("Could not read the zip export.");
    const count = view.getUint16(eocd + 10, true);
    let cursor = view.getUint32(eocd + 16, true);
    const entries = [];
    for (let n = 0; n < count; n += 1) {
      if (view.getUint32(cursor, true) !== 0x02014b50) throw new Error("Could not read the zip export.");
      const method = view.getUint16(cursor + 10, true);
      const compSize = view.getUint32(cursor + 20, true);
      const nameLen = view.getUint16(cursor + 28, true);
      const extraLen = view.getUint16(cursor + 30, true);
      const commentLen = view.getUint16(cursor + 32, true);
      const localOff = view.getUint32(cursor + 42, true);
      const name = new TextDecoder().decode(bytes.subarray(cursor + 46, cursor + 46 + nameLen));
      entries.push({ name, method, compSize, localOff });
      cursor += 46 + nameLen + extraLen + commentLen;
    }
    const jsons = entries.filter((item) => item.name.toLowerCase().endsWith(".json") && !item.name.startsWith("__MACOSX"));
    if (!jsons.length) throw new Error("The zip needs a drawgen.json export.");
    const entry = jsons[0];
    const nameLen = view.getUint16(entry.localOff + 26, true);
    const extraLen = view.getUint16(entry.localOff + 28, true);
    const method = view.getUint16(entry.localOff + 8, true);
    const compSize = view.getUint32(entry.localOff + 18, true);
    const start = entry.localOff + 30 + nameLen + extraLen;
    const slice = bytes.subarray(start, start + compSize);
    let text;
    if (method === 0) text = new TextDecoder().decode(slice);
    else if (method === 8 && typeof DecompressionStream !== "undefined") {
      const stream = new Blob([slice]).stream().pipeThrough(new DecompressionStream("deflate-raw"));
      text = new TextDecoder().decode(await new Response(stream).arrayBuffer());
    } else throw new Error("Could not read the zip export.");
    const parsed = fromDrawgen(parseJsonText(text), entry.name.split("/").pop());
    const cad = entries.find((item) => /\.(ipt|iam)$/i.test(item.name));
    if (cad && !parsed.fileName) parsed.fileName = cad.name.split("/").pop();
    return parsed;
  }

  function parseJsonText(text) {
    return JSON.parse(String(text).replace(/^\uFEFF/, ""));
  }

  async function parseUpload(file) {
    const name = file.name || "model.ipt";
    if (file.size > 40 * 1024 * 1024) throw new Error("File is larger than 40 MB.");
    const lower = name.toLowerCase();
    const data = await file.arrayBuffer();
    if (lower.endsWith(".zip")) return unzipJson(data);
    if (lower.endsWith(".json")) return fromDrawgen(parseJsonText(new TextDecoder().decode(data)), name);
    return fromInventor(name, data, lower.endsWith(".iam") ? "iam" : "ipt");
  }

  function insertJob(parsed) {
    const item = chooseTemplate(parsed);
    const fmt = formatById(parsed.bomFormatId);
    const views = viewsFor(item, parsed);
    const props = sanitize(parsed.properties || {}, parsed.fileName || "");
    if (!props.productSeries) props.productSeries = (item.company && item.company.productSeries) || "";
    props.extras = { ...(props.extras || {}) };
    (item.signoffFields || []).forEach((field) => { if (props.extras[field.key] == null) props.extras[field.key] = ""; });
    const now = stamp();
    const job = {
      id: newId(), createdAt: now, updatedAt: now, sourceName: parsed.fileName, sourceKind: parsed.fileKind,
      exampleId: parsed.exampleId || null, templateId: item.id, bomFormatId: fmt ? fmt.id : null,
      viewCount: views.length, selectedViews: views, properties: props, model: parsed.model || {},
      bomRows: parsed.bomRows || [], warnings: parsed.warnings || [], status: "draft", sample: !!parsed.sample,
      sampleNote: parsed.sampleNote || "", sop: null, snapshot: null,
    };
    const state = read();
    state.jobs.unshift(job);
    write(state);
    return present(job);
  }

  function jobById(id) {
    const job = read().jobs.find((item) => item.id === id);
    if (!job) throw new Error("That drawing could not be found.");
    return job;
  }

  function replaceJob(job) {
    const state = read();
    const index = state.jobs.findIndex((item) => item.id === job.id);
    if (index < 0) throw new Error("That drawing could not be found.");
    state.jobs[index] = job;
    write(state);
  }

  function review(item, job) {
    const drawing = item.drawingType || "part";
    const props = job.properties || {};
    const model = job.model || {};
    const roles = job.selected_views || [];
    const checks = [];
    const add = (status, rule, detail) => checks.push({ status, rule, detail });
    const authored = (role) => ((model.views || {})[role]) || {};
    const hasProfile = (role) => !!(authored(role).paths || authored(role).circles || authored(role).arcs);
    if (roles.length < 2) add("fail", "View count", "A production sheet needs at least 2 views.");
    else add("pass", "View count", `${roles.length} views. Minimum is 2.`);
    if (roles.length && roles.every((role) => !hasProfile(role))) {
      add("warn", "Profiles", "These views are the overall envelope. The file has no view curves. Run CreateDrawing.vb in Inventor to place the real views on Standard.idw.");
    } else add("pass", "Profiles", "At least one view has model geometry.");
    if (blank(props.partNumber) || blank(props.description)) add("warn", "Drawing identity", "Part number and description both belong in the title block.");
    else add("pass", "Drawing identity", `${props.partNumber} — ${props.description}`);
    if (drawing === "part") partChecks(add, props, model, roles, authored);
    else if (drawing === "weldment") weldChecks(add, model, job, roles);
    else if (drawing === "assembly") assemblyChecks(add, job, roles);
    else if (drawing === "signoff") signoffChecks(add, props, model, roles, item);
    return checks;
  }

  function partChecks(add, props, model, roles, authored) {
    const bends = model.bends || [];
    if (blank(props.material)) add("warn", "Material", "The title block needs the material type.");
    else add("pass", "Material", String(props.material));
    if (blank(props.thickness)) add("warn", "Thickness", "Dimension the thickness where it is easiest to read, and fill it in on the title block.");
    else add("pass", "Thickness", String(props.thickness));
    if (bends.length) {
      if (!roles.includes("flat")) add("warn", "Flat view", "A part with bends needs a flat view as well as the formed views.");
      else add("pass", "Flat view", "Flat pattern is on the sheet.");
      const lines = ((authored("flat").paths) || []).filter((path) => path.bend).length;
      if (lines < bends.length) add("warn", "Bend lines", "Bend lines and bend IDs need to be on the flat. Notch a bend that is not parallel to a flat face.");
      else add("pass", "Bend lines", `${lines} bend line(s) on the flat pattern.`);
      if (bends.some((bend) => !["UP", "U"].includes(String(bend.direction || "").toUpperCase()))) add("warn", "Bend direction", "Bend direction should be up whenever possible.");
      else add("pass", "Bend direction", "Bends are called out UP.");
      if (bends.some((bend) => blank(bend.id) || blank(bend.angle) || blank(bend.radius))) add("warn", "Bend table", "Each bend needs an ID, direction, angle, and radius.");
      else add("pass", "Bend table", `${bends.length} bend(s) in the table.`);
    } else add("pass", "Bends", "No bends on this part. Side, front, and isometric are the usual set.");
    if (roles.includes("front") && roles.includes("side")) add("pass", "Orthographic views", "Front and side are both on the sheet for overall height and width.");
    else add("warn", "Orthographic views", "Dimension overall height and width on the side and front, and on the flat when there is one.");
    add("pass", "Laser cuts", "Cut-outs that are in the DXF do not need dimensions. Confirm before adding them.");
  }

  function symbols(model, key) {
    const found = [];
    Object.values(model.views || {}).forEach((view) => found.push(...((view && view[key]) || [])));
    return found;
  }

  function overallCheck(add, model) {
    const overall = model.overall || {};
    const missing = ["length", "width", "height"].filter((name) => !overall[name]);
    if (missing.length) add("warn", "Overall size", `Dimension overall height, width, and depth. Missing: ${missing.join(", ")}.`);
    else add("pass", "Overall size", "Length, width, and height are on the model card.");
  }

  function partsList(add, job, model) {
    const rows = job.bom_rows || [];
    if (!rows.length) {
      add("warn", "Parts list", "The parts list in the top left needs every part and quantity.");
      return;
    }
    add("pass", "Parts list", `${rows.length} item(s) in the saved BOM format.`);
    if (rows.length < 2) {
      add("pass", "Balloons", "One part does not need item balloons.");
      return;
    }
    const balloons = symbols(model, "balloons");
    const items = new Set(rows.map((row) => String(row.item)));
    const marked = new Set(balloons.map((balloon) => String(balloon.item)));
    if (!balloons.length) add("warn", "Balloons", "Numbered balloons should point at each part in the list.");
    else if ([...items].some((item) => !marked.has(item))) {
      const missing = [...items].filter((item) => !marked.has(item)).sort().join(", ");
      add("warn", "Balloons", `No balloon yet for item ${missing}.`);
    } else add("pass", "Balloons", "Every parts-list item has a balloon.");
  }

  function weldChecks(add, model, job, roles) {
    overallCheck(add, model);
    partsList(add, job, model);
    const welds = model.welds || [];
    const placed = symbols(model, "welds");
    if (!welds.length && !placed.length) add("warn", "Weld symbols", "Add the weld symbols on the clearest view, or coordinate with the welding department.");
    else if (placed.length) add("pass", "Weld symbols", "Weld symbols are placed on a view.");
    else add("warn", "Weld symbols", "Welds are listed but not shown on a view yet.");
    if (roles.length < 3) add("warn", "Weldment views", "Use as many views as production needs. Side, front or back, top or bottom, and an isometric is typical.");
    else add("pass", "Weldment views", "Enough views are selected to describe the weldment.");
  }

  function assemblyChecks(add, job, roles) {
    overallCheck(add, job.model || {});
    partsList(add, job, job.model || {});
    if (roles.length < 3) add("warn", "Assembly views", "Use as many views as production needs. Side, front or back, top or bottom, and an isometric is typical.");
    else add("pass", "Assembly views", "Enough views are selected to describe the assembly.");
  }

  function signoffChecks(add, props, model, roles, item) {
    const selected = new Set(roles);
    if (![...["side", "section"]].every((role) => selected.has(role))) add("warn", "Signoff views", "Show a side view and an end cross-section, plus a front view.");
    else add("pass", "Signoff views", "Side and end cross-section are selected.");
    if (!selected.has("inlet") && !selected.has("discharge")) add("warn", "Flange faces", "Show face views of the inlet and the discharge with flange size and opening size.");
    else add("pass", "Flange faces", "A flange face view is on the sheet.");
    const sections = model.sections || [];
    if (sections.length < 2) add("warn", "Sections", "On the side view, dimension each section length and label the section.");
    else add("pass", "Sections", `${sections.length} section lengths are labeled.`);
    [["customer", "Customer name"], ["orderNumber", "Order number"], ["quoteNumber", "Quote number"]].forEach(([key, label]) => {
      if (blank(props[key])) add("warn", label, `${label} belongs in the lower-left signoff block.`);
      else add("pass", label, String(props[key]));
    });
    add("pass", "Signature and date", "Signature and date lines are part of the signoff block.");
    if (!(item.signoffFields || item.signoff_fields || []).length) add("warn", "Unit info", "Add the unit-specific lines for this product. Chain conveyor, u-trough, and bucket elevator each differ.");
  }

  function validateTemplate(item) {
    if (!String(item.name || "").trim()) throw new Error("Give the template a name.");
    if (!["part", "weldment", "assembly", "signoff", "standard"].includes(item.drawingType)) throw new Error("Drawing type must be standard, part, weldment, assembly, or signoff.");
    if (!["ipt", "iam", "both"].includes(item.appliesTo)) throw new Error("A template applies to .ipt parts, .iam assemblies, or both.");
    if ((item.views || []).length < 2) throw new Error("A template needs at least two views.");
    const sizes = { A: [11, 8.5], B: [17, 11], C: [22, 17], D: [34, 22], E: [44, 34] };
    const label = String(item.sheetLabel || "").toUpperCase();
    if (sizes[label] && !item.sheetWidthIn) [item.sheetWidthIn, item.sheetHeightIn] = sizes[label];
    const width = Number(item.sheetWidthIn);
    const height = Number(item.sheetHeightIn);
    if (!Number.isFinite(width) || !Number.isFinite(height)) throw new Error("Sheet width and height need to be numbers, in inches.");
    if (width < 8 || height < 6) throw new Error("Sheet size is smaller than an A-size landscape sheet.");
    item.sheetWidthIn = width;
    item.sheetHeightIn = height;
    if (item.table && item.table.kind === "bend") {
      item.table.columns = normalizeColumns(item.table.columns || clone(BEND_COLUMNS));
      item.table.title = item.table.title || "TABLE";
    }
  }

  function line(x1, y1, x2, y2, layer = "OBJECT", dashed = false) {
    return { op: "line", x1, y1, x2, y2, layer, dashed };
  }
  function rect(x, y, w, h, layer = "TABLE") { return { op: "rect", x1: x, y1: y, x2: w, y2: h, layer }; }
  function circle(cx, cy, r, layer = "OBJECT") { return { op: "circle", x1: cx, y1: cy, r, layer }; }
  function poly(pts, layer = "OBJECT", dashed = false) { return { op: "poly", pts, layer, dashed }; }
  function solid(pts, fill = "") { return { op: "solid", pts, fill }; }
  function text(x, y, value, size = 0.1, anchor = "start", bold = false) {
    return { op: "text", x1: x, y1: y, text: String(value ?? ""), size, anchor, bold };
  }

  function wrap(value, widthIn, size) {
    if (!value) return [];
    const maxChars = Math.max(6, Math.floor(widthIn / (size * 0.52)));
    const lines = [];
    String(value).split("\n").forEach((paragraph) => {
      const words = paragraph.split(/\s+/).filter(Boolean);
      if (!words.length) { lines.push(""); return; }
      let cur = "";
      words.forEach((word) => {
        const trial = `${cur} ${word}`.trim();
        if (trial.length <= maxChars) cur = trial;
        else { if (cur) lines.push(cur); cur = word; }
      });
      if (cur) lines.push(cur);
    });
    return lines;
  }

  function fitLine(value, widthIn, size) {
    const text = String(value ?? "").trim().replace(/\s+/g, " ");
    if (!text) return "";
    const maxChars = Math.max(4, Math.floor((widthIn - 0.08) / (size * 0.52)));
    if (text.length <= maxChars) return text;
    return `${text.slice(0, maxChars - 1).trimEnd()}…`;
  }

  const BORDER_INSET = 0.50;

  function zoneCounts(width, height) {
    const innerW = Math.max(width - 2 * BORDER_INSET, 4);
    const innerH = Math.max(height - 2 * BORDER_INSET, 3);
    return [Math.max(4, Math.round(innerW / 2)), Math.max(2, Math.round(innerH / 2.5))];
  }

  function border(width, height) {
    const margin = BORDER_INSET;
    const [cols, rows] = zoneCounts(width, height);
    const innerW = width - 2 * margin;
    const innerH = height - 2 * margin;
    const colW = innerW / cols;
    const rowH = innerH / rows;
    const tick = 0.18;
    const prims = [rect(margin, margin, innerW, innerH, "BORDER")];
    for (let index = 0; index < cols; index += 1) {
      const x = margin + index * colW;
      const number = String(cols - index);
      const center = x + colW / 2;
      prims.push(text(center, height - 0.22, number, 0.11, "middle"));
      prims.push(text(center, 0.12, number, 0.11, "middle"));
      if (index) {
        prims.push(line(x, height - margin, x, height - margin + tick, "THIN"));
        prims.push(line(x, margin, x, margin - tick, "THIN"));
      }
    }
    for (let index = 0; index < rows; index += 1) {
      const y = margin + index * rowH;
      const letter = String.fromCharCode(65 + index);
      const baseline = y + rowH / 2 - 0.04;
      prims.push(text(margin - 0.08, baseline, letter, 0.11, "end"));
      prims.push(text(width - margin + 0.08, baseline, letter, 0.11));
      if (index) {
        prims.push(line(margin - tick, y, margin, y, "THIN"));
        prims.push(line(width - margin, y, width - margin + tick, y, "THIN"));
      }
    }
    return prims;
  }

  const BLOCK_W = 8.20;
  const DESC_SIZE = 0.15;
  const DESC_PITCH = 0.22;
  const DESC_LINES = 2;
  const PART_W = 1.72;
  const THICK_W = 1.55;
  const IDENT_H = 0.50;
  const BODY_H = 1.70;

  function descWidth(blockW) {
    return Math.max(3.2, blockW - PART_W - 0.16);
  }

  function descriptionLines(value, blockW) {
    const lines = wrap(value || "—", descWidth(blockW), DESC_SIZE);
    return lines.length ? lines : ["—"];
  }

  function descBand(lineCount) {
    return 0.30 + Math.max(DESC_LINES, lineCount) * DESC_PITCH;
  }

  function titleBlockHeight(props, blockW) {
    const count = descriptionLines((props && props.description) || "", blockW).length;
    return descBand(count) + IDENT_H + BODY_H;
  }

  function cellLabel(prims, x, y, w, h, label, value, valueSize, bold, limit = 2) {
    prims.push(text(x + 0.06, y + h - 0.13, label, 0.05));
    wrap(value || "—", w - 0.12, valueSize).slice(0, limit).forEach((lineText, i) => {
      prims.push(text(x + 0.06, y + h - 0.30 - i * valueSize * 1.2, lineText, valueSize, "start", bold));
    });
  }

  function titleBlock(x, y, w, h, company, props) {
    const lines = descriptionLines((props && props.description) || "", w);
    const band = descBand(lines.length);
    const yBody = y + BODY_H;
    const yIdent = yBody + IDENT_H;
    const yTop = yIdent + band;
    const xPart = x + w - PART_W;
    const xThick = xPart - THICK_W;
    const prims = [rect(x, y, w, yTop - y)];
    prims.push(line(x, yBody, x + w, yBody, "TABLE"), line(x, yIdent, x + w, yIdent, "TABLE"), line(xPart, yBody, xPart, yTop, "TABLE"), line(xThick, yBody, xThick, yIdent, "TABLE"));
    prims.push(text(x + 0.08, yTop - 0.12, "DESCRIPTION", 0.045));
    lines.forEach((lineText, i) => prims.push(text(x + 0.08, yTop - 0.34 - i * DESC_PITCH, lineText, DESC_SIZE, "start", true)));
    prims.push(text(xPart + 0.08, yTop - 0.12, "PART NO.", 0.045));
    const pnLines = wrap((props && props.partNumber) || "—", PART_W - 0.16, 0.13).slice(0, 2);
    const shownPn = pnLines.length ? pnLines : ["—"];
    const pnBase = yIdent + Math.max(0.12, (band - 0.18 - shownPn.length * 0.16) / 2);
    shownPn.forEach((lineText, i) => prims.push(text(xPart + 0.08, pnBase - i * 0.16, lineText, 0.13, "start", true)));
    prims.push(text(x + 0.08, yIdent - 0.13, "MATERIAL", 0.045));
    prims.push(text(x + 0.08, yBody + 0.12, (props && props.material) || "—", 0.11, "start", true));
    prims.push(text(xThick + 0.08, yIdent - 0.13, "THICKNESS", 0.045));
    prims.push(text(xThick + 0.08, yBody + 0.12, (props && props.thickness) || "—", 0.11, "start", true));
    prims.push(text(xPart + 0.08, yIdent - 0.13, "REV", 0.045));
    prims.push(text(xPart + 0.08, yBody + 0.12, (props && props.rev) || "—", 0.11, "start", true));
    const xProj = x + 3.05;
    const xSign = x + 4.75;
    const xMeta = x + w - 1.42;
    prims.push(line(xProj, y, xProj, yBody, "TABLE"), line(xSign, y, xSign, yBody, "TABLE"), line(xMeta, y, xMeta, yBody, "TABLE"));
    const tolerances = (company && company.tolerances && company.tolerances.length) ? company.tolerances : ["DIMENSIONS ARE IN INCHES", ".X ± .1", ".XX ± .01", ".XXX ± .005", "ANGLES ± 1°"];
    prims.push(text(x + 0.08, yBody - 0.14, "UNLESS OTHERWISE SPECIFIED", 0.042, "start", true));
    tolerances.slice(0, 5).forEach((row, i) => prims.push(text(x + 0.08, yBody - 0.32 - i * 0.18, row, 0.05)));
    prims.push(text(x + 0.08, y + 0.08, "DO NOT SCALE DRAWING", 0.042, "start", true));
    prims.push(text(xProj + 0.08, yBody - 0.16, "THIRD ANGLE", 0.05, "start", true));
    prims.push(text(xProj + 0.08, yBody - 0.32, "PROJECTION", 0.045, "start", true));
    const sx = xProj + 0.16;
    const sy = y + 0.36;
    prims.push(line(sx, sy + 0.16, sx + 0.34, sy + 0.28, "THIN"), line(sx, sy + 0.16, sx + 0.34, sy + 0.04, "THIN"), line(sx + 0.34, sy + 0.28, sx + 0.34, sy + 0.04, "THIN"), line(sx, sy + 0.04, sx, sy + 0.28, "THIN"), circle(sx + 0.52, sy + 0.16, 0.09, "THIN"));
    const drawn = [props && props.drawnBy, props && props.drawnDate].filter(Boolean).join("   ");
    const signatures = [["DRAWN", drawn || "—"], ["CHECKED", (props && props.checker) || "—"], ["ENG APPR", "—"]];
    const signH = BODY_H / signatures.length;
    signatures.forEach(([label, value], i) => {
      const top = yBody - i * signH;
      if (i) prims.push(line(xSign, top, xMeta, top, "TABLE"));
      prims.push(text(xSign + 0.08, top - 0.14, label, 0.045));
      prims.push(text(xSign + 0.08, top - signH + 0.10, value, 0.08, "start", true));
    });
    const notice = String((company && company.proprietary) || "").trim();
    if (notice) wrap(notice, xProj - x - 0.16, 0.042).slice(0, 2).forEach((row, i) => prims.push(text(x + 0.08, y + 0.42 - i * 0.12, row, 0.042)));
    const meta = [["SCALE", (props && props.scale) || "SEE ABOVE"], ["SIZE", (props && props.sheetSize) || "—"], ["MASS", (props && props.mass) || "—"], ["SHEET", `${(props && props.sheetNumber) || "1"} OF ${(props && props.sheetCount) || "1"}`]];
    const cellH = BODY_H / meta.length;
    meta.forEach(([label, value], i) => {
      const top = yBody - i * cellH;
      if (i) prims.push(line(xMeta, top, x + w, top, "TABLE"));
      prims.push(text(xMeta + 0.06, top - 0.13, label, 0.042));
      prims.push(text(xMeta + 0.06, top - cellH + 0.08, value || "—", 0.07, "start", true));
    });
    return prims;
  }

  function dataTable(x, y, w, h, titleText, columns, rows) {
    const prims = [rect(x, y, w, h)];
    const rowH = h / (2 + Math.max(rows.length, 1));
    const titleTop = y + h;
    prims.push(line(x, titleTop - rowH, x + w, titleTop - rowH, "TABLE"));
    prims.push(text(x + w / 2, titleTop - rowH * 0.68, titleText, 0.09, "middle", true));
    const headerBottom = titleTop - 2 * rowH;
    prims.push(line(x, headerBottom, x + w, headerBottom, "TABLE"));
    let cursor = x;
    columns.forEach((col) => {
      const cw = w * num(col.width);
      if (cursor > x + 0.01) prims.push(line(cursor, y, cursor, headerBottom + rowH, "TABLE"));
      prims.push(text(cursor + 0.05, headerBottom + rowH * 0.32, col.heading || "", 0.062, "start", true));
      cursor += cw;
    });
    (rows.length ? rows : [{}]).forEach((row, rIndex) => {
      const rowTop = headerBottom - rIndex * rowH;
      if (rIndex) prims.push(line(x, rowTop, x + w, rowTop, "TABLE"));
      cursor = x;
      columns.forEach((col) => {
        const cw = w * num(col.width);
        const shown = rows.length ? fitLine(row[col.key], cw, 0.07) : "";
        prims.push(text(cursor + 0.05, rowTop - rowH * 0.68, shown, 0.07));
        cursor += cw;
      });
    });
    return prims;
  }

  function signoffBlock(x, y, w, h, props, fields) {
    const prims = [rect(x, y, w, h), text(x + 0.08, y + h - 0.16, "UNIT AND CUSTOMER", 0.08, "start", true), line(x, y + h - 0.26, x + w, y + h - 0.26, "TABLE")];
    const lines = [["CUSTOMER", props.customer || ""], ["ORDER NO.", props.orderNumber || ""], ["QUOTE NO.", props.quoteNumber || ""]];
    const extras = props.extras || {};
    (fields || []).forEach((field) => lines.push([field.label || field.key || "", extras[field.key] || ""]));
    lines.push(["SIGNATURE", props.signature || "________________"], ["DATE", props.signDate || "________________"]);
    const step = Math.min(0.16, (h - 0.36) / Math.max(lines.length, 1));
    const size = step < 0.15 ? 0.062 : 0.07;
    lines.forEach(([label, value], i) => {
      const yy = y + h - 0.42 - i * step;
      if (yy < y + 0.04) return;
      prims.push(text(x + 0.08, yy, `${label}:  ${value || "—"}`, size));
    });
    return prims;
  }

  function fmt(value) {
    const textValue = value.toFixed(3).replace(/0+$/, "").replace(/\.$/, "");
    return textValue.includes(".") ? textValue : value.toFixed(3);
  }

  const VIEW_STYLES = ["hidden-line-removed", "hidden-line", "shaded", "raster"];

  function styleName(value) {
    return VIEW_STYLES.includes(value) ? value : "hidden-line-removed";
  }

  function styleCaption(style) {
    return { "hidden-line": "HIDDEN LINE", shaded: "SHADED", raster: "RASTER" }[style] || "";
  }

  function faceColors(style) {
    if (style === "shaded") return ["#d9d4cc", "#e6e1d8", "#c4bfb6"];
    if (style === "raster") return ["#b7b2a8", "#d2cdc4", "#8f8a82"];
    return [];
  }

  function displayOf(model) {
    const display = (model && model.display) || {};
    const size = Number(display.annotationSize);
    return {
      viewStyle: styleName(display.viewStyle),
      annotationSize: size > 0 && size <= 1 ? size : 0.10,
      annotationStyle: display.annotationStyle === "bold" ? "bold" : "standard",
      balloons: display.balloons !== false,
      partsList: display.partsList !== false,
    };
  }

  function envelope(role, overall, viewStyle, annotationSize) {
    const length = num(overall.length);
    const width = num(overall.width);
    const height = num(overall.height);
    if (length <= 0 || width <= 0) return { empty: true };
    const known = height > 0;
    const visual = known ? height : Math.max(Math.min(length, width) * 0.06, 0.12);
    const style = styleName(viewStyle);
    const colors = faceColors(style);
    if (role === "iso") {
      const isoH = known ? height : visual;
      const project = (x, y, z) => [(x - z) * Math.cos(Math.PI / 6), y + (x + z) * Math.sin(Math.PI / 6)];
      const corners = {};
      [0, 1].forEach((i) => [0, 1].forEach((j) => [0, 1].forEach((k) => { corners[`${i}${j}${k}`] = project(i * length, j * isoH, k * width); })));
      const edges = [[0, 0, 0, 1, 0, 0], [1, 0, 0, 1, 1, 0], [1, 1, 0, 0, 1, 0], [0, 1, 0, 0, 0, 0], [0, 0, 1, 1, 0, 1], [1, 0, 1, 1, 1, 1], [1, 1, 1, 0, 1, 1], [0, 1, 1, 0, 0, 1], [0, 0, 0, 0, 0, 1], [1, 0, 0, 1, 0, 1], [1, 1, 0, 1, 1, 1], [0, 1, 0, 0, 1, 1]];
      const paths = edges.map((e) => {
        const hidden = style === "hidden-line" && e[2] === 1 && e[5] === 1;
        return { pts: [corners[`${e[0]}${e[1]}${e[2]}`], corners[`${e[3]}${e[4]}${e[5]}`]], layer: hidden ? "HIDDEN" : "OBJECT", dashed: hidden };
      });
      const view = { paths, caption: styleCaption(style), annotationSize };
      if (colors.length) {
        const face = (keys) => keys.map((key) => corners[key]);
        view.fills = [
          { pts: face(["000", "100", "110", "010"]), fill: colors[0] },
          { pts: face(["010", "110", "111", "011"]), fill: colors[1] },
          { pts: face(["100", "101", "111", "110"]), fill: colors[2] },
        ];
      }
      return view;
    }
    let w = known ? length : length;
    let h = known ? height : width;
    if (["side", "end", "section"].includes(role)) { w = width; h = known ? height : visual; }
    else if (role === "flat") { w = length; h = width; }
    else if (["top", "bottom"].includes(role)) { w = length; h = known ? width : visual; }
    else if (!["front", "back"].includes(role)) { w = length; h = known ? height : width; }
    const padX = Math.max(w * 0.12, 0.4);
    const padY = Math.max(h * 0.18, 0.45);
    const view = {
      paths: [{ pts: [[0, 0], [w, 0], [w, h], [0, h], [0, 0]], layer: "OBJECT" }],
      dims: [
        { kind: "horizontal", x1: 0, x2: w, y: -padY, ext: 0, text: fmt(w) },
        { kind: "vertical", y1: 0, y2: h, x: -padX, ext: 0, text: fmt(h) },
      ],
      caption: styleCaption(style),
      annotationSize,
    };
    if (colors.length) view.fills = [{ pts: [[0, 0], [w, 0], [w, h], [0, h]], fill: colors[0] }];
    return view;
  }

  function applyStyle(view, display) {
    if (!view || view.empty) return view || { empty: true };
    const style = display.viewStyle;
    const copied = { ...view, annotationSize: display.annotationSize, annotationStyle: display.annotationStyle };
    const colors = faceColors(style);
    if (colors.length && !(copied.fills || []).length) {
      const fills = [];
      (copied.paths || []).forEach((path) => {
        const pts = path.pts || [];
        if (pts.length >= 4 && pts[0][0] === pts[pts.length - 1][0] && pts[0][1] === pts[pts.length - 1][1] && (path.layer || "OBJECT") === "OBJECT") {
          fills.push({ pts: pts.slice(0, -1), fill: colors[0] });
        }
      });
      if (fills.length) copied.fills = fills;
    }
    if (style === "hidden-line") {
      copied.paths = (copied.paths || []).map((path) => {
        if (path.hidden || path.layer === "HIDDEN") return { ...path, dashed: true, layer: "HIDDEN" };
        return path;
      });
    }
    if (!copied.caption) {
      const note = styleCaption(style, false);
      if (note) copied.caption = note;
    }
    return copied;
  }

  function attachBalloons(view, rows) {
    if (!rows.length || !view || view.empty || (view.balloons || []).length) return view;
    const [minx, miny, maxx, maxy] = bbox(view);
    const span = Math.max(maxy - miny, 1);
    const width = Math.max(maxx - minx, 1);
    const count = Math.min(rows.length, 16);
    const balloons = rows.slice(0, count).map((row, index) => ({
      item: row.item === undefined || row.item === "" ? index + 1 : row.item,
      x: minx + width * 0.62,
      y: miny + span * ((index + 1) / (count + 1)),
      nx: maxx + width * 0.28,
      ny: maxy - (index + 0.5) * (span / count),
    }));
    return { ...view, balloons };
  }

  function bbox(view) {
    const xs = [];
    const ys = [];
    const add = (x, y) => { xs.push(x); ys.push(y); };
    (view.paths || []).forEach((path) => (path.pts || []).forEach(([x, y]) => add(num(x), num(y))));
    (view.fills || []).forEach((fill) => (fill.pts || []).forEach(([x, y]) => add(num(x), num(y))));
    (view.circles || []).forEach((c) => {
      add(num(c.cx) - num(c.r), num(c.cy) - num(c.r));
      add(num(c.cx) + num(c.r), num(c.cy) + num(c.r));
    });
    (view.dims || []).forEach((d) => {
      if (d.kind === "horizontal") { add(num(d.x1), num(d.y)); add(num(d.x2), num(d.y)); add(num(d.x1), num(d.ext ?? d.y)); add(num(d.x2), num(d.ext ?? d.y)); }
      else if (d.kind === "vertical") { add(num(d.x), num(d.y1)); add(num(d.x), num(d.y2)); add(num(d.ext ?? d.x), num(d.y1)); }
      else if (d.kind === "leader") { add(num(d.x), num(d.y)); add(num(d.tx), num(d.ty)); }
    });
    (view.notes || []).forEach((note) => add(num(note.x), num(note.y)));
    (view.balloons || []).forEach((b) => { add(num(b.x), num(b.y)); add(num(b.nx), num(b.ny)); });
    (view.welds || []).forEach((w) => { add(num(w.x), num(w.y)); add(num(w.tx ?? w.x), num(w.ty ?? w.y)); });
    if (!xs.length) return [0, 0, 1, 1];
    return [Math.min(...xs), Math.min(...ys), Math.max(...xs), Math.max(...ys)];
  }

  function arrow(x, y, tx, ty) {
    const ang = Math.atan2(ty - y, tx - x) + Math.PI;
    const p1 = [x + 0.09 * Math.cos(ang + 0.38), y + 0.09 * Math.sin(ang + 0.38)];
    const p2 = [x + 0.09 * Math.cos(ang - 0.38), y + 0.09 * Math.sin(ang - 0.38)];
    return solid([[x, y], p1, p2]);
  }

  function renderView(view, role, label, box) {
    const [x, y, w, h] = box;
    const caption = view && view.caption;
    let titleText = label || ROLE_LABELS[role] || role.toUpperCase();
    if (caption) titleText = `${titleText} — ${caption}`;
    const prims = [text(x + w / 2, y + 0.02, titleText, 0.09, "middle", true)];
    if (view && view.scale) prims.push(text(x + w / 2, y + 0.16, String(view.scale), 0.07, "middle"));
    if (!view || view.empty || !(view.paths || view.circles || view.arcs || view.hatch)) {
      prims.push(text(x + w / 2, y + h / 2, "NO PROFILE", 0.1, "middle"));
      return prims;
    }
    const [minx, miny, maxx, maxy] = bbox(view);
    const gw = Math.max(maxx - minx, 0.01);
    const gh = Math.max(maxy - miny, 0.01);
    const innerBottom = y + (view.scale ? 0.32 : 0.2);
    const iw = Math.max(w - 0.12, 0.4);
    const ih = Math.max(h - (innerBottom - y) - 0.06, 0.4);
    const scale = Math.min(iw / gw, ih / gh);
    const ox = x + 0.06 + (iw - gw * scale) / 2 - minx * scale;
    const oy = innerBottom + (ih - gh * scale) / 2 - miny * scale;
    const p = (px, py) => [ox + px * scale, oy + py * scale];
    const ann = num(view.annotationSize, 0.10) > 0 ? num(view.annotationSize, 0.10) : 0.10;
    const bold = view.annotationStyle === "bold";
    (view.fills || []).forEach((fill) => {
      const pts = (fill.pts || []).map(([px, py]) => p(num(px), num(py)));
      if (pts.length >= 3) prims.push(solid(pts, fill.fill || ""));
    });
    (view.paths || []).forEach((path) => {
      const pts = (path.pts || []).map(([px, py]) => p(num(px), num(py)));
      const layer = path.layer || "OBJECT";
      if (pts.length >= 2) prims.push(poly(pts, layer, !!path.dashed || layer === "CENTER" || layer === "HIDDEN"));
    });
    (view.circles || []).forEach((c) => {
      const [cx, cy] = p(num(c.cx), num(c.cy));
      const r = num(c.r) * scale;
      prims.push(circle(cx, cy, r, c.layer || "OBJECT"));
    });
    (view.dims || []).forEach((dim) => {
      if (dim.kind === "horizontal" || dim.kind === "vertical") {
        const a = dim.kind === "horizontal" ? p(num(dim.x1), num(dim.y)) : p(num(dim.x), num(dim.y1));
        const b = dim.kind === "horizontal" ? p(num(dim.x2), num(dim.y)) : p(num(dim.x), num(dim.y2));
        prims.push(line(a[0], a[1], b[0], b[1], "DIM"));
        prims.push(arrow(a[0], a[1], b[0], b[1]), arrow(b[0], b[1], a[0], a[1]));
        prims.push(text((a[0] + b[0]) / 2, (a[1] + b[1]) / 2 + 0.04, dim.text || "", ann, "middle", bold));
      } else if (dim.kind === "leader") {
        const a = p(num(dim.x), num(dim.y));
        const b = p(num(dim.tx), num(dim.ty));
        prims.push(line(b[0], b[1], a[0], a[1], "DIM"), arrow(a[0], a[1], b[0], b[1]));
        prims.push(text(b[0], b[1] + 0.03, dim.text || "", ann, "start", bold));
      }
    });
    (view.notes || []).forEach((note) => {
      const [nx, ny] = p(num(note.x), num(note.y));
      prims.push(text(nx, ny, note.text || "", num(note.size, 0.09), note.anchor || "start", !!note.bold));
    });
    (view.welds || []).forEach((weld) => {
      const [jx, jy] = p(num(weld.x), num(weld.y));
      const [tx, ty] = p(num(weld.tx ?? weld.x), num(weld.ty ?? weld.y));
      prims.push(line(tx, ty, jx, jy, "THIN"), arrow(jx, jy, tx, ty), line(tx, ty, tx + 0.85, ty, "THIN"));
      if (weld.size) prims.push(text(tx + 0.36, ty + 0.04, String(weld.size), 0.08, "middle"));
    });
    (view.balloons || []).forEach((balloon) => {
      const [nx, ny] = p(num(balloon.nx), num(balloon.ny));
      const [bx, by] = p(num(balloon.x), num(balloon.y));
      prims.push(circle(nx, ny, 0.13, "THIN"));
      prims.push(text(nx, ny - 0.035, String(balloon.item ?? ""), 0.09, "middle", true));
      prims.push(line(nx, ny, bx, by, "THIN"));
    });
    return prims;
  }

  function grid(roles, area) {
    const [x, y, w, h] = area;
    const gap = 0.28;
    const cols = roles.length <= 1 ? 1 : roles.length <= 4 ? 2 : 3;
    const rows = Math.ceil(roles.length / cols);
    const cw = (w - gap * (cols - 1)) / cols;
    const rh = (h - gap * (rows - 1)) / rows;
    const boxes = {};
    roles.forEach((role, i) => {
      const c = i % cols;
      const r = Math.floor(i / cols);
      boxes[role] = [x + c * (cw + gap), y + (rows - 1 - r) * (rh + gap), Math.max(cw, 0.4), Math.max(rh, 0.4)];
    });
    return boxes;
  }

  function allocate(roles, area, drawing) {
    const [x, y, w, h] = area;
    if ((drawing === "signoff" || drawing === "weldment" || drawing === "assembly") && roles.includes("side") && (drawing === "signoff" || roles.length >= 3)) {
      const sideH = h * (drawing === "signoff" ? 0.48 : 0.46);
      return { side: [x, y, Math.max(w, 0.4), Math.max(sideH, 0.4)], ...grid(roles.filter((role) => role !== "side"), [x, y + sideH + 0.12, w, h - sideH - 0.12]) };
    }
    if (drawing === "part") {
      const boxes = {};
      let splitY = y + h;
      let left = x + w;
      if (roles.includes("iso")) {
        const isoX = x + w * 0.62;
        const isoH = h * 0.44;
        boxes.iso = [isoX, y + h - isoH, Math.max(x + w - isoX, 0.4), Math.max(isoH, 0.4)];
        splitY = y + h - isoH;
        left = isoX - 0.1;
      }
      const rest = roles.filter((role) => role !== "iso");
      Object.assign(boxes, grid(rest, [x, y, Math.max(left - x, w * 0.5), Math.max(splitY - y, 0.4)]));
      return boxes;
    }
    return grid(roles, area);
  }

  function profileSize(role, length, width, height) {
    const known = height > 0;
    const visual = known ? height : Math.max(Math.min(length, width) * 0.06, 0.12);
    if (role === "front" || role === "back") return known ? [length, height] : [length, width];
    if (["side", "end", "section"].includes(role)) return known ? [width, height] : [width, visual];
    if (role === "top" || role === "bottom") return known ? [length, width] : [length, visual];
    if (role === "flat") return [length, width];
    return known ? [length, height] : [length, width];
  }

  const NICE_SCALES = [10, 5, 4, 2, 1, 0.5, 0.25, 0.2, 0.125, 0.1, 1 / 12, 1 / 16, 0.05, 1 / 24, 1 / 30, 1 / 32, 0.025, 0.02, 1 / 64, 0.01];

  function snapScale(exact) {
    if (!(exact > 0)) return exact;
    const fit = NICE_SCALES.filter((scale) => scale <= exact * 1.001);
    return fit.length ? fit[0] : exact;
  }

  function scaleLabel(scale) {
    if (scale >= 1 && Math.abs(scale - Math.round(scale)) < 1e-6) return `SCALE ${Math.round(scale)} : 1`;
    if (scale > 0) {
      const inverse = 1 / scale;
      if (Math.abs(inverse - Math.round(inverse)) < 0.08) return `SCALE 1 : ${Math.round(inverse)}`;
    }
    return `SCALE ${scale.toFixed(3)}`;
  }

  function ownedDims(roles, height) {
    const owned = {};
    roles.forEach((role) => { owned[role] = { h: false, v: false }; });
    const known = height > 0;
    if (roles.includes("front")) {
      owned.front = { h: true, v: true };
      if (known && roles.includes("top")) owned.top = { h: false, v: true };
      else if (known && roles.includes("side")) owned.side = { h: true, v: false };
      else if (known && roles.includes("end")) owned.end = { h: true, v: false };
    } else if (roles.includes("top")) owned.top = { h: true, v: true };
    else if (roles.includes("side")) owned.side = { h: true, v: true };
    return owned;
  }

  function placeThirdAngle(roles, area, overall, rightReserve = 0) {
    const length = num(overall.length);
    const width = num(overall.width);
    const height = num(overall.height);
    if (!(length > 0 && width > 0)) return null;
    let [x, y, aw, ah] = area;
    let flat = null;
    if (roles.includes("flat")) {
      const flatH = Math.min(ah * 0.28, 2.6);
      flat = [x, y, Math.max(aw - rightReserve, 1), flatH];
      y += flatH + 0.2;
      ah -= flatH + 0.2;
    }
    const columns = [];
    if (roles.includes("back") && roles.includes("front")) columns.push(["back"]);
    const center = [];
    if (roles.includes("bottom")) center.push("bottom");
    if (roles.includes("front")) center.push("front");
    else if (roles.includes("back")) center.push("back");
    if (roles.includes("top")) center.push("top");
    if (center.length) columns.push(center);
    const depth = ["side", "end", "section"].filter((role) => roles.includes(role));
    if (depth.length) columns.push(depth);
    if (!columns.length || aw < 1.5 || ah < 1.5) return null;
    const wh = (role) => profileSize(role, length, width, height);
    const gap = 0.72;
    const modelW = columns.reduce((sum, column) => sum + Math.max(...column.map((role) => wh(role)[0])), 0);
    const modelH = Math.max(...columns.map((column) => column.reduce((sum, role) => sum + wh(role)[1], 0)));
    const gapsX = Math.max(columns.length - 1, 0);
    const gapsY = Math.max(...columns.map((column) => Math.max(column.length - 1, 0)));
    const availW = aw - rightReserve - 1.05;
    const availH = ah - 0.95;
    if (!(modelW > 0 && modelH > 0 && availW > 0.5 && availH > 0.5)) return null;
    const exact = Math.min((availW - gap * gapsX) / modelW, (availH - gap * gapsY) / modelH);
    const candidates = NICE_SCALES.filter((scale) => scale <= exact * 1.001);
    if (!candidates.length) candidates.push(Math.max(exact, 0.01));
    const wantIso = roles.includes("iso");
    const layout = (scale) => {
      let cursorX = x + 0.72;
      const originY = y + 0.82;
      const placed = {};
      columns.forEach((column) => {
        let cursorY = originY;
        const columnW = Math.max(...column.map((role) => wh(role)[0]));
        column.forEach((role) => {
          const [mw, mh] = wh(role);
          placed[role] = { ox: cursorX + ((columnW - mw) * scale) / 2, oy: cursorY, mw, mh };
          cursorY += mh * scale + gap;
        });
        cursorX += columnW * scale + gap;
      });
      const usedRight = Math.max(...Object.values(placed).map((item) => item.ox + item.mw * scale));
      const usedTop = Math.max(...Object.values(placed).map((item) => item.oy + item.mh * scale));
      return { placed, usedRight, usedTop };
    };
    let scale = candidates[candidates.length - 1];
    let { placed, usedRight, usedTop } = layout(scale);
    for (let i = 0; i < candidates.length; i += 1) {
      const candidate = candidates[i];
      const trial = layout(candidate);
      const freeRight = (x + aw - rightReserve) - trial.usedRight;
      if (wantIso && freeRight < 2.5 && candidate !== candidates[candidates.length - 1]) continue;
      scale = candidate;
      placed = trial.placed;
      usedRight = trial.usedRight;
      usedTop = trial.usedTop;
      break;
    }
    let iso = null;
    if (wantIso) {
      const freeRight = (x + aw - rightReserve) - usedRight;
      const freeAbove = (y + ah) - usedTop;
      if (freeRight >= 2.1) iso = [usedRight + 0.28, y + 0.12, freeRight - 0.28, Math.max(ah - 0.22, 1.4)];
      else if (freeAbove >= 1.7) {
        const isoW = Math.min(4.8, Math.max(aw * 0.36, 2.2));
        iso = [x + aw - rightReserve - isoW, usedTop + 0.18, isoW, Math.max(freeAbove - 0.28, 1.4)];
      }
    }
    return { views: placed, scale, base: placed.front ? "front" : Object.keys(placed)[0], iso, flat };
  }

  function balloonStack(rows, box, limitX) {
    const [x, y, w, h] = box;
    const count = Math.min(rows.length, 16);
    if (!count || w <= 0 || h <= 0) return [];
    let pitch = 0.34;
    if (pitch * Math.max(count - 1, 1) > h - 0.2) pitch = Math.max(0.26, (h - 0.2) / Math.max(count - 1, 1));
    const stack = pitch * (count - 1);
    const top = y + (h + stack) / 2;
    const cx = Math.min(x + w + 0.5, limitX - 0.16);
    const prims = [];
    const radius = 0.13;
    rows.slice(0, count).forEach((row, index) => {
      const item = row.item === undefined || row.item === "" ? index + 1 : row.item;
      const by = top - index * pitch;
      const ty = Math.min(Math.max(by, y + 0.1), y + h - 0.1);
      prims.push(circle(cx, by, radius, "THIN"));
      prims.push(text(cx, by - 0.035, String(item), 0.08, "middle", true));
      prims.push(line(cx - radius, by, x + w, ty, "THIN"));
      prims.push(solid([[x + w, ty], [x + w - 0.07, ty + 0.028], [x + w - 0.07, ty - 0.028]]));
    });
    return prims;
  }

  function sheetSpan(x1, y1, x2, y2, value, size, bold, horizontal) {
    const prims = [line(x1, y1, x2, y2, "DIM"), arrow(x1, y1, x2, y2), arrow(x2, y2, x1, y1)];
    if (horizontal) prims.push(text((x1 + x2) / 2, y1 + 0.06, value, size, "middle", bold));
    else prims.push(text(x1 - 0.06, (y1 + y2) / 2, value, size, "end", bold));
    return prims;
  }

  function renderPlaced(view, role, label, place) {
    const { scale } = place;
    const { ox, oy, mw, mh } = place;
    const prims = [];
    const project = (px, py) => [ox + px * scale, oy + py * scale];
    const ann = num(view.annotationSize, 0.1) > 0 ? num(view.annotationSize, 0.1) : 0.1;
    const bold = view.annotationStyle === "bold";
    (view.fills || []).forEach((fill) => {
      const pts = (fill.pts || []).map(([px, py]) => project(num(px), num(py)));
      if (pts.length >= 3) prims.push(solid(pts, fill.fill || ""));
    });
    (view.paths || []).forEach((path) => {
      const pts = (path.pts || []).map(([px, py]) => project(num(px), num(py)));
      const layer = path.layer || "OBJECT";
      if (pts.length >= 2) prims.push(poly(pts, layer, !!path.dashed || layer === "CENTER" || layer === "HIDDEN"));
    });
    const dims = view.dims || [];
    dims.forEach((dim) => {
      if (dim.kind === "horizontal") prims.push(...sheetSpan(ox, oy - 0.36, ox + mw * scale, oy - 0.36, dim.text || "", ann, bold, true));
      else if (dim.kind === "vertical") prims.push(...sheetSpan(ox - 0.42, oy, ox - 0.42, oy + mh * scale, dim.text || "", ann, bold, false));
    });
    const titleText = label || ROLE_LABELS[role] || String(role).toUpperCase();
    const nameY = oy - (dims.some((dim) => dim.kind === "horizontal") ? 0.62 : 0.28);
    prims.push(text(ox + (mw * scale) / 2, nameY, titleText, 0.1, "middle", true));
    if (place.scaleText) prims.push(text(ox + (mw * scale) / 2, nameY - 0.16, place.scaleText, 0.08, "middle"));
    (view.balloons || []).forEach((balloon) => {
      const [nx, ny] = project(num(balloon.nx), num(balloon.ny));
      const [bx, by] = project(num(balloon.x), num(balloon.y));
      prims.push(circle(nx, ny, 0.13, "THIN"));
      prims.push(text(nx, ny - 0.035, String(balloon.item ?? ""), 0.09, "middle", true));
      prims.push(line(nx, ny, bx, by, "THIN"));
    });
    return prims;
  }

  function compose(item, fmt, job) {
    const width = num(item.sheetWidthIn);
    const height = num(item.sheetHeightIn);
    const props = { ...(job.properties || {}), sheetSize: item.sheetLabel || "" };
    const model = job.model || {};
    const roles = job.selectedViews || [];
    const labels = {};
    (item.views || []).forEach((view) => { labels[view.role] = view.label || ROLE_LABELS[view.role] || view.role.toUpperCase(); });
    const inset = BORDER_INSET;
    const tbW = Math.min(BLOCK_W, width - 2 * inset - 0.4);
    const tbH = titleBlockHeight(props, tbW);
    const tb = [width - inset - tbW, inset, tbW, tbH];
    const kind = (item.table || {}).kind;
    let spec = null;
    let rows = [];
    if (kind === "bend") { spec = [item.table.title || "TABLE", item.table.columns || []]; rows = model.bends || []; }
    else if (kind === "parts" && fmt) { spec = [fmt.title || "Parts List", fmt.columns || []]; rows = job.bomRows || []; }
    const display = displayOf(model);
    const partSheet = job.sourceKind === "ipt" || item.drawingType === "part";
    if ((partSheet || !display.partsList) && kind === "parts") spec = null;
    if (partSheet && kind === "bend" && !rows.length) spec = null;
    let tableBox = null;
    if (spec && spec[1].length) {
      const count = Math.max(rows.length, 1);
      if (item.drawingType === "part") {
        const tw = Math.min(7.6, width * 0.48);
        const th = 0.3 * (2 + count);
        tableBox = [inset + 0.08, height - inset - th - 0.08, tw, th];
      } else {
        const tw = Math.min(7.5, Math.max(tb[0] - inset - 0.28, 4.2));
        let th = 0.22 * (2 + count);
        const limit = height - inset - 0.35;
        if (inset + th > limit) th = Math.max(limit - inset, 1.2);
        tableBox = [inset + 0.08, inset, tw, th];
      }
    }
    let infoBox = null;
    if (kind === "signoff" || item.drawingType === "signoff") infoBox = [inset + 0.08, inset, Math.min(6.6, tb[0] - inset - 0.25), tbH];
    let bottom = inset + tbH + 0.28;
    if (tableBox && item.drawingType !== "part") bottom = Math.max(bottom, tableBox[1] + tableBox[3] + 0.2);
    const top = height - inset - 0.16;
    const area = [inset + 0.12, bottom, width - 2 * inset - 0.24, Math.max(top - bottom, 1)];
    const authored = roles.some((role) => geometry((model.views || {})[role]));
    const balloonRole = ["iso", "front", "side"].find((role) => roles.includes(role));
    let useBalloons = job.sourceKind === "iam" && display.balloons && display.partsList && rows.length > 1 && balloonRole;
    const placement = !authored && item.drawingType !== "signoff" ? placeThirdAngle(roles, area, model.overall || {}, useBalloons ? 1.15 : 0) : null;
    const boxes = placement ? {} : allocate(roles, area, item.drawingType || "part");
    const prims = border(width, height);
    const owned = placement ? ownedDims(roles, num((model.overall || {}).height)) : {};
    roles.forEach((role) => {
      const authoredView = (model.views || {})[role];
      let view = geometry(authoredView) ? applyStyle(authoredView, display) : envelope(role, model.overall || {}, display.viewStyle, display.annotationSize);
      if (view && !view.empty) view = { ...view, annotationStyle: display.annotationStyle, annotationSize: display.annotationSize };
      if (placement && placement.views[role]) {
        const keep = owned[role] || { h: false, v: false };
        view = {
          ...view,
          caption: "",
          dims: (view.dims || []).filter((dim) => (dim.kind === "horizontal" && keep.h) || (dim.kind === "vertical" && keep.v)),
        };
        prims.push(...renderPlaced(view, role, labels[role] || "", {
          ...placement.views[role],
          scale: placement.scale,
          scaleText: role === placement.base ? scaleLabel(placement.scale) : "",
        }));
        return;
      }
      let box = boxes[role];
      if (placement && role === "iso" && placement.iso) box = placement.iso;
      else if (placement && role === "flat" && placement.flat) box = placement.flat;
      if (!box) return;
      prims.push(...renderView(view, role, labels[role] || "", box));
      if (useBalloons && role === balloonRole) {
        prims.push(...balloonStack(rows, box, width - inset - 0.02));
        useBalloons = false;
      }
    });
    if (useBalloons && placement) {
      let target = placement.iso;
      const placed = placement.views[balloonRole];
      if (!target && placed) target = [placed.ox, placed.oy, placed.mw * placement.scale, placed.mh * placement.scale];
      if (target) prims.push(...balloonStack(rows, target, width - inset - 0.02));
    }
    if (tableBox && spec) prims.push(...dataTable(...tableBox, spec[0], spec[1], rows));
    prims.push(...titleBlock(...tb, item.company || {}, props));
    if (infoBox) prims.push(...signoffBlock(...infoBox, props, item.signoffFields || []));
    return { prims, width, height, title: props.partNumber || job.sourceName || "Drawing" };
  }

  function xml(value) {
    return String(value ?? "").replace(/[&<>"']/g, (ch) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[ch]));
  }

  function toSvg(prims, width, height) {
    const parts = [
      `<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 ${width.toFixed(4)} ${height.toFixed(4)}" width="100%" height="100%" role="img">`,
      "<rect width='100%' height='100%' fill='#fbfaf6'/>",
      `<g transform="translate(0 ${height.toFixed(4)}) scale(1 -1)" fill="none" stroke="#1b1916" stroke-linecap="round" stroke-linejoin="round">`,
    ];
    prims.forEach((prim) => {
      const sw = `${LAYER_PX[prim.layer] || 1}px`;
      if (prim.op === "line") {
        const dash = prim.dashed || prim.layer === "CENTER" ? ' stroke-dasharray="4 3"' : "";
        parts.push(`<line x1="${prim.x1.toFixed(4)}" y1="${prim.y1.toFixed(4)}" x2="${prim.x2.toFixed(4)}" y2="${prim.y2.toFixed(4)}" stroke-width="${sw}" vector-effect="non-scaling-stroke"${dash}/>`);
      } else if (prim.op === "rect") {
        parts.push(`<rect x="${prim.x1.toFixed(4)}" y="${prim.y1.toFixed(4)}" width="${prim.x2.toFixed(4)}" height="${prim.y2.toFixed(4)}" stroke-width="${sw}" vector-effect="non-scaling-stroke"/>`);
      } else if (prim.op === "circle") {
        parts.push(`<circle cx="${prim.x1.toFixed(4)}" cy="${prim.y1.toFixed(4)}" r="${prim.r.toFixed(4)}" stroke-width="${sw}" vector-effect="non-scaling-stroke"/>`);
      } else if (prim.op === "poly") {
        const d = prim.pts.map(([px, py]) => `${px.toFixed(4)},${py.toFixed(4)}`).join(" ");
        const dash = prim.dashed || prim.layer === "CENTER" || prim.layer === "HIDDEN" ? ' stroke-dasharray="5 3"' : "";
        parts.push(`<polyline points="${d}" stroke-width="${sw}" vector-effect="non-scaling-stroke"${dash}/>`);
      } else if (prim.op === "solid") {
        const d = prim.pts.map((pt) => `${pt[0].toFixed(4)},${pt[1].toFixed(4)}`).join(" ");
        const fill = /^#[0-9A-Fa-f]{6}$/.test(prim.fill || "") ? prim.fill : "#1b1916";
        parts.push(`<polygon points="${d}" fill="${fill}" stroke="none"/>`);
      } else if (prim.op === "text" && prim.text) {
        const weight = prim.bold ? "700" : "500";
        const anchor = { start: "start", middle: "middle", end: "end" }[prim.anchor] || "start";
        String(prim.text).split("\n").forEach((lineText, i) => {
          const yy = prim.y1 - i * prim.size * 1.25;
          parts.push(`<g transform="translate(${prim.x1.toFixed(4)} ${yy.toFixed(4)}) scale(1 -1)"><text x="0" y="0" fill="#1b1916" stroke="none" font-family="Inter, Noto Sans, sans-serif" font-weight="${weight}" font-size="${prim.size.toFixed(4)}" text-anchor="${anchor}">${xml(lineText)}</text></g>`);
        });
      }
    });
    parts.push("</g></svg>");
    return parts.join("");
  }

  function pdfEscape(value) {
    return String(value).replace(/\\/g, "\\\\").replace(/\(/g, "\\(").replace(/\)/g, "\\)");
  }

  function toPdf(prims, width, height, title) {
    const cmds = ["0.106 0.098 0.086 RG", "0.106 0.098 0.086 rg"];
    prims.forEach((prim) => {
      const X = (v) => (v * 72).toFixed(2);
      if (prim.op === "line") cmds.push(`${X(prim.x1)} ${X(prim.y1)} m ${X(prim.x2)} ${X(prim.y2)} l S`);
      else if (prim.op === "rect") cmds.push(`${X(prim.x1)} ${X(prim.y1)} ${X(prim.x2)} ${X(prim.y2)} re S`);
      else if (prim.op === "circle") {
        const pts = [];
        for (let i = 0; i <= 24; i += 1) {
          const a = (Math.PI * 2 * i) / 24;
          pts.push(`${X(prim.x1 + prim.r * Math.cos(a))} ${X(prim.y1 + prim.r * Math.sin(a))}`);
        }
        cmds.push(`${pts[0]} m ${pts.slice(1).map((pt) => `${pt} l`).join(" ")} S`);
      } else if (prim.op === "poly" || prim.op === "solid") {
        const pts = prim.pts.map((pt) => `${X(pt[0])} ${X(pt[1])}`);
        if (pts.length >= 2) cmds.push(`${pts[0]} m ${pts.slice(1).map((pt) => `${pt} l`).join(" ")} ${prim.op === "solid" ? "f" : "S"}`);
      } else if (prim.op === "text" && prim.text) {
        const size = Math.max(4, prim.size * 72);
        let x = prim.x1 * 72;
        const shift = prim.anchor === "middle" ? 0.5 : prim.anchor === "end" ? 1 : 0;
        if (shift) x -= prim.text.length * size * 0.45 * shift;
        cmds.push(`BT /F1 ${size.toFixed(2)} Tf ${x.toFixed(2)} ${(prim.y1 * 72).toFixed(2)} Td (${pdfEscape(prim.text)}) Tj ET`);
      }
    });
    const stream = cmds.join("\n");
    const objects = [];
    const add = (body) => { objects.push(body); return objects.length; };
    add("<< /Type /Catalog /Pages 2 0 R >>");
    add("<< /Type /Pages /Kids [3 0 R] /Count 1 >>");
    add(`<< /Type /Page /Parent 2 0 R /MediaBox [0 0 ${(width * 72).toFixed(2)} ${(height * 72).toFixed(2)}] /Contents 4 0 R /Resources << /Font << /F1 5 0 R >> >> >>`);
    add(`<< /Length ${stream.length} >>\nstream\n${stream}\nendstream`);
    add("<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica >>");
    let pdf = `%PDF-1.4\n% ${title}\n`;
    const offsets = [0];
    objects.forEach((body, index) => {
      offsets.push(pdf.length);
      pdf += `${index + 1} 0 obj\n${body}\nendobj\n`;
    });
    const xref = pdf.length;
    pdf += `xref\n0 ${objects.length + 1}\n0000000000 65535 f \n`;
    offsets.slice(1).forEach((offset) => { pdf += `${String(offset).padStart(10, "0")} 00000 n \n`; });
    pdf += `trailer << /Size ${objects.length + 1} /Root 1 0 R >>\nstartxref\n${xref}\n%%EOF`;
    return new TextEncoder().encode(pdf);
  }

  function toDxf(prims) {
    const lines = ["0", "SECTION", "2", "ENTITIES"];
    const push = (pairs) => pairs.forEach((pair) => lines.push(String(pair[0]), String(pair[1])));
    prims.forEach((prim) => {
      const layer = prim.layer || "OBJECT";
      if (prim.op === "line") push([[0, "LINE"], [8, layer], [10, prim.x1], [20, prim.y1], [11, prim.x2], [21, prim.y2]]);
      else if (prim.op === "rect") {
        const pts = [[prim.x1, prim.y1], [prim.x1 + prim.x2, prim.y1], [prim.x1 + prim.x2, prim.y1 + prim.y2], [prim.x1, prim.y1 + prim.y2], [prim.x1, prim.y1]];
        for (let i = 0; i < 4; i += 1) push([[0, "LINE"], [8, layer], [10, pts[i][0]], [20, pts[i][1]], [11, pts[i + 1][0]], [21, pts[i + 1][1]]]);
      } else if (prim.op === "circle") push([[0, "CIRCLE"], [8, layer], [10, prim.x1], [20, prim.y1], [40, prim.r]]);
      else if (prim.op === "poly") {
        for (let i = 0; i < prim.pts.length - 1; i += 1) push([[0, "LINE"], [8, layer], [10, prim.pts[i][0]], [20, prim.pts[i][1]], [11, prim.pts[i + 1][0]], [21, prim.pts[i + 1][1]]]);
      } else if (prim.op === "text" && prim.text) push([[0, "TEXT"], [8, "TEXT"], [10, prim.x1], [20, prim.y1], [40, prim.size], [1, prim.text]]);
    });
    lines.push("0", "ENDSEC", "0", "EOF");
    return lines.join("\n");
  }

  function rendered(jobId) {
    const job = jobById(jobId);
    if (!job.snapshot) throw new Error("Generate the sheet before downloading it.");
    const item = job.snapshot.template;
    const fmt = job.snapshot.bomFormat;
    return compose(item, fmt, job);
  }

  function buildFile(jobId, name) {
    const drawing = rendered(jobId);
    const title = (drawing.title || "Drawing").replace(/\s+/g, "_");
    if (name.endsWith(".svg")) return { body: toSvg(drawing.prims, drawing.width, drawing.height), type: "image/svg+xml", download: `${title}.svg` };
    if (name.endsWith(".pdf")) return { body: toPdf(drawing.prims, drawing.width, drawing.height, drawing.title), type: "application/pdf", download: `${title}.pdf` };
    if (name.endsWith(".dxf")) return { body: toDxf(drawing.prims), type: "application/dxf", download: `${title}.dxf` };
    const job = jobById(jobId);
    const columns = (job.snapshot.bomFormat && job.snapshot.bomFormat.columns) || [];
    const csv = (value) => {
      const text = String(value ?? "");
      return /[",\n]/.test(text) ? `"${text.replace(/"/g, '""')}"` : text;
    };
    const header = columns.map((col) => csv(col.heading || col.key || "")).join(",");
    const rows = (job.sourceKind === "ipt" ? [] : (job.bomRows || [])).map((row) => columns.map((col) => csv(row[col.key])).join(","));
    return { body: `${[header, ...rows].join("\n")}\n`, type: "text/csv", download: `${title}-bom.csv` };
  }

  const blobs = new Map();
  function sheetLink(jobId, name) {
    const file = buildFile(jobId, name);
    const blob = new Blob([file.body], { type: file.type });
    const url = URL.createObjectURL(blob);
    const key = `${jobId}:${name}`;
    if (blobs.has(key)) URL.revokeObjectURL(blobs.get(key));
    blobs.set(key, url);
    return { url, download: file.download };
  }

  async function jsonBody(options) {
    if (!options || options.body == null) return {};
    if (typeof options.body === "string") return JSON.parse(options.body);
    return options.body;
  }

  async function handle(path, options) {
    const method = ((options && options.method) || "GET").toUpperCase();
    const clean = String(path || "").replace(/^\//, "").split("?")[0];
    const bits = clean.split("/");
    if (clean === "api/template-source") return { path: SHOP, reachable: false, drawings: [], otherCount: 0, pages: true };
    if (clean === "api/templates/import" || clean === "api/template-source/sync") throw new Error(LOCKED);
    if (clean === "api/templates" && method === "GET") return templates();
    if (bits[0] === "api" && bits[1] === "templates" && bits[2] && method === "PUT") {
      const current = templateById(bits[2]);
      const body = await jsonBody(options);
      const merged = { ...current, ...body, id: current.id, updatedAt: stamp() };
      validateTemplate(merged);
      const state = read();
      state.templates = state.templates.map((item) => (item.id === merged.id ? merged : item));
      write(state);
      return merged;
    }
    if (bits[1] === "templates" && bits[3] === "duplicate") throw new Error(LOCKED);
    if (bits[1] === "templates" && method === "DELETE") throw new Error(LOCKED);
    if (clean === "api/bom-formats" && method === "GET") return formats();
    if (bits[1] === "bom-formats" && bits[2] && method === "PUT") {
      const current = formatById(bits[2]);
      if (!current || current.id !== bits[2]) throw new Error("That BOM format is no longer in the library.");
      const body = await jsonBody(options);
      const merged = { ...current, ...body, columns: normalizeColumns(body.columns || current.columns), updatedAt: stamp() };
      if (!merged.columns.length) throw new Error("A BOM format needs at least one column.");
      const state = read();
      if (merged.isDefault) state.formats.forEach((item) => { item.isDefault = item.id === merged.id; });
      state.formats = state.formats.map((item) => (item.id === merged.id ? merged : item));
      write(state);
      return formatById(merged.id);
    }
    if (bits[1] === "bom-formats" && bits[3] === "duplicate" && method === "POST") {
      const current = clone(formatById(bits[2]));
      if (!current || current.id !== bits[2]) throw new Error("That BOM format is no longer in the library.");
      current.id = newId();
      current.name = `${current.name} copy`;
      current.isDefault = false;
      current.updatedAt = stamp();
      const state = read();
      state.formats.push(current);
      write(state);
      return current;
    }
    if (bits[1] === "bom-formats" && method === "DELETE") {
      const state = read();
      if (state.formats.length <= 1) throw new Error("Keep at least one BOM format.");
      const current = state.formats.find((item) => item.id === bits[2]);
      state.formats = state.formats.filter((item) => item.id !== bits[2]);
      if (current && current.isDefault && state.formats[0]) state.formats[0].isDefault = true;
      write(state);
      return { ok: true };
    }
    if (clean === "api/examples") return [];
    if (clean === "api/jobs" && method === "GET") {
      return read().jobs.map((job) => present(job)).map((job) => ({
        id: job.id, updatedAt: job.updatedAt, sourceName: job.sourceName, sourceKind: job.sourceKind,
        partNumber: (job.properties || {}).partNumber || "", description: (job.properties || {}).description || "",
        status: job.status, viewCount: job.viewCount, hasSheet: job.hasSheet, sample: job.sample,
      }));
    }
    if (clean === "api/jobs" && method === "POST") {
      let parsed;
      const upload = options && options.body;
      if (typeof FormData !== "undefined" && upload instanceof FormData) {
        const file = options.body.get("file");
        if (!file) throw new Error("Drop an .ipt, .iam, .json, or .zip file.");
        parsed = await parseUpload(file);
      } else {
        const body = await jsonBody(options);
        if (body.exampleId) throw new Error("Drop an Inventor part or assembly.");
        parsed = fromDrawgen(body, body.fileName || "model.json");
      }
      return insertJob(parsed);
    }
    if (bits[1] === "jobs" && bits[2] && bits.length === 3 && method === "GET") return present(jobById(bits[2]));
    if (bits[1] === "jobs" && bits[2] && bits.length === 3 && method === "PUT") {
      const job = jobById(bits[2]);
      const body = await jsonBody(options);
      const item = templateById(body.templateId || job.templateId);
      const fmt = formatById(body.bomFormatId || job.bomFormatId);
      const views = viewsFor(item, { selectedViews: body.selectedViews || job.selectedViews, viewCount: body.viewCount ?? (body.selectedViews || job.selectedViews).length, fileKind: job.sourceKind, model: body.model || job.model });
      job.templateId = item.id;
      job.bomFormatId = fmt ? fmt.id : null;
      job.selectedViews = views;
      job.viewCount = views.length;
      job.properties = sanitize(body.properties || job.properties, job.sourceName || "");
      job.properties.extras = job.properties.extras || {};
      job.model = body.model || job.model || {};
      job.bomRows = job.sourceKind === "ipt" ? [] : (body.bomRows || job.bomRows || []);
      job.status = "draft";
      job.sop = null;
      job.updatedAt = stamp();
      replaceJob(job);
      return present(job);
    }
    if (bits[1] === "jobs" && bits[3] === "generate" && method === "POST") {
      const job = jobById(bits[2]);
      if ((job.selectedViews || []).length < 2) throw new Error("Ask for at least 2 views before generating the sheet.");
      applyDescribedSize(job);
      if (!drawable(job)) throw new Error("This file has no profiles and no overall size.");
      const item = effective(templateById(job.templateId), job);
      const fmt = formatById(job.bomFormatId);
      const sop = review(effectiveSnake(item), forRules(job));
      job.sop = sop;
      job.status = sop.every((check) => check.status === "pass") ? "ready" : "review";
      job.snapshot = { template: item, bomFormat: fmt, generatedAt: stamp() };
      job.updatedAt = job.snapshot.generatedAt;
      replaceJob(job);
      const shown = present(job);
      shown.sop = sop;
      return shown;
    }
    throw new Error("That page is not on the live site.");
  }

  function effectiveSnake(item) {
    return { ...item, signoff_fields: item.signoffFields || [] };
  }

  const api = { active: false, handle, sheetLink, buildFile };
  const root = typeof globalThis !== "undefined" ? globalThis : window;
  root.drawgenBrowser = api;
})();
