const app = document.querySelector("#app");
const state = {
  templates: [],
  formats: [],
  examples: [],
  templateSource: null,
  jobs: [],
  job: null,
  showAllTemplates: false,
  zoom: 1,
  error: "",
};

function esc(value) {
  return String(value ?? "").replace(/[&<>"']/g, (ch) => ({
    "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;",
  }[ch]));
}

function formatWhen(iso) {
  if (!iso) return "";
  const stamp = new Date(iso).toLocaleString("en-US", {
    timeZone: "America/Chicago",
    month: "short",
    day: "numeric",
    year: "numeric",
    hour: "numeric",
    minute: "2-digit",
  });
  return `${stamp} CT`;
}

let serverMode = null;

async function usesServer() {
  if (serverMode !== null) return serverMode;
  try {
    const response = await fetch("api/template-source", { headers: { Accept: "application/json" } });
    const type = response.headers.get("content-type") || "";
    serverMode = response.ok && type.includes("json");
  } catch (error) {
    serverMode = false;
  }
  if (!serverMode && window.drawgenBrowser) window.drawgenBrowser.active = true;
  return serverMode;
}

function sheetLink(jobId, name) {
  if (window.drawgenBrowser && window.drawgenBrowser.active) return window.drawgenBrowser.sheetLink(jobId, name);
  return { url: `api/jobs/${jobId}/${name}`, download: "" };
}

async function api(path, options) {
  if (!(await usesServer())) return window.drawgenBrowser.handle(path, options);
  const response = await fetch(String(path).replace(/^\//, ""), options);
  const type = response.headers.get("content-type") || "";
  if (!response.ok) {
    let detail = response.statusText;
    if (type.includes("json")) {
      const body = await response.json();
      detail = body.detail || detail;
    }
    throw new Error(detail);
  }
  if (type.includes("json")) return response.json();
  return response;
}

function route() {
  const hash = location.hash.replace(/^#\/?/, "");
  const [head, id] = hash.split("/");
  return { name: head || "new", id: id || "" };
}

function setNav() {
  const name = route().name;
  document.querySelectorAll("nav a").forEach((link) => {
    const key = link.dataset.nav;
    const on = key === name || (key === "new" && name === "job") || (key === "library" && name === "sheet");
    link.classList.toggle("active", on);
  });
}

let stickyError = "";

function flash(error) {
  stickyError = error.message || String(error);
  boot();
}

async function boot() {
  setNav();
  state.error = stickyError;
  stickyError = "";
  const { name, id } = route();
  try {
    if (name === "new") {
      state.templateSource = await api("/api/template-source");
      renderNew();
    } else if (name === "job" && id) {
      [state.job, state.templates, state.formats, state.templateSource] = await Promise.all([
        api(`/api/jobs/${id}`), api("/api/templates"), api("/api/bom-formats"), api("/api/template-source"),
      ]);
      if (!state.job.hasSheet && (hasOverall(state.job) || describedSize(state.job))) {
        await api(`/api/jobs/${id}/generate`, { method: "POST" });
        location.hash = `#/sheet/${id}`;
        return;
      }
      renderJob();
    } else if (name === "sheet" && id) {
      [state.job, state.templates] = await Promise.all([
        api(`/api/jobs/${id}`), api("/api/templates"),
      ]);
      renderSheet();
    } else if (name === "library") {
      state.jobs = await api("/api/jobs");
      renderLibrary();
    } else if (name === "templates") {
      [state.templates, state.templateSource] = await Promise.all([
        api("/api/templates"), api("/api/template-source"),
      ]);
      renderTemplates(id || (state.templates[0] && state.templates[0].id));
    } else if (name === "formats") {
      state.formats = await api("/api/bom-formats");
      renderFormats(id || (state.formats[0] && state.formats[0].id));
    } else {
      location.hash = "#/new";
    }
  } catch (error) {
    app.innerHTML = `<div class="error">${esc(error.message)}</div>`;
  }
}

function errorBlock() {
  return state.error ? `<div class="error">${esc(state.error)}</div>` : "";
}

function renderNew() {
  document.querySelector("main").classList.remove("wide");
  app.innerHTML = `
    ${errorBlock()}
    <h1>New drawing</h1>
    <p class="lede">Drop a part (.ipt) or an assembly (.iam). The sheet is made from the file. Part number, description, material, thickness, and overall size are read automatically.</p>
    ${templateSourceNote()}
    <div class="drop" id="drop">
      <strong>Drop an .ipt or an .iam</strong>
      <span>Run CreateDrawing.vb in Inventor for a Standard.idw sheet with real views. Drop the .drawgen.json it writes.</span>
      <label class="file-btn">Browse<input id="file" type="file" accept=".ipt,.iam,.json,.zip" hidden></label>
    </div>`;
  const drop = document.getElementById("drop");
  drop.addEventListener("dragover", (event) => { event.preventDefault(); drop.classList.add("hot"); });
  drop.addEventListener("dragleave", () => drop.classList.remove("hot"));
  drop.addEventListener("drop", (event) => {
    event.preventDefault();
    const file = event.dataTransfer.files[0];
    if (file) upload(file);
  });
  document.getElementById("file").addEventListener("change", (event) => {
    if (event.target.files[0]) upload(event.target.files[0]);
  });
}

async function upload(file) {
  const body = new FormData();
  body.append("file", file);
  try {
    const job = await api("/api/jobs", { method: "POST", body });
    const overall = (job.model && job.model.overall) || {};
    const sized = ["length", "width", "height"].every((key) => Number(overall[key]) > 0);
    if (sized) {
      await api(`/api/jobs/${job.id}/generate`, { method: "POST" });
      location.hash = `#/sheet/${job.id}`;
      return;
    }
    location.hash = `#/job/${job.id}`;
  } catch (error) {
    flash(error);
  }
}

function hasOverall(job) {
  const overall = (job.model && job.model.overall) || {};
  return Number(overall.length) > 0 && Number(overall.width) > 0;
}

function describedSize(job) {
  const props = (job && job.properties) || {};
  const reader = window.drawgenInventor;
  if (!reader || !reader.sizeFromText) return null;
  const text = [props.description, props.title, props.subject, props.comments].filter(Boolean).join(" ");
  return reader.sizeFromText(text);
}

function currentTemplate() {
  return state.templates.find((item) => item.id === state.job.templateId) || state.templates[0];
}

function renderJob() {
  document.querySelector("main").classList.remove("wide");
  const job = state.job;
  const template = currentTemplate();
  const visible = state.templates.filter((item) => state.showAllTemplates || item.appliesTo === job.sourceKind || item.appliesTo === "both");
  const choices = (visible.length ? visible : state.templates).map((item) => `
    <label class="choice ${item.id === job.templateId ? "on" : ""}">
      <input type="radio" name="template" value="${esc(item.id)}" ${item.id === job.templateId ? "checked" : ""}>
      <span><strong>${esc(item.name)}</strong><br><span class="muted">${esc(templateMeta(item))}</span></span>
      <span class="tag">${esc(appliesLabel(item.appliesTo))}</span>
    </label>`).join("");
  const order = (template.views || []);
  const selected = new Set(job.selectedViews || []);
  const chips = order.map((view) => `
    <button type="button" class="chip ${selected.has(view.role) ? "on" : ""}" data-role="${esc(view.role)}">${esc(view.label || view.role)}</button>`).join("");
  const props = job.properties || {};
  const overall = (job.model && job.model.overall) || {};
  const sheetKind = sheetKindFor(template, job);
  const showSignoff = sheetKind === "signoff";
  const warnings = (job.warnings || []).map((line) => `<p>${esc(line)}</p>`).join("");
  app.innerHTML = `
    ${errorBlock()}
    <h1>${esc(props.partNumber || job.sourceName || "Drawing")}</h1>
    <p class="lede">${esc(props.description || "")} <span class="tag">${esc(job.sourceKind || "")}</span> ${job.sample ? '<span class="tag">Sample</span>' : ""}</p>
    ${warnings ? `<div class="banner warn">${warnings}</div>` : ""}
    <form id="jobForm" class="layout">
      <div class="stack">
        <section class="panel">
          <h2>Drawing template</h2>
          ${templateSourceNote()}
          <div class="choices">${choices}</div>
          <label class="field" style="margin-top:10px"><span></span>
            <span><input type="checkbox" id="showAll" ${state.showAllTemplates ? "checked" : ""}> Show every template</span>
          </label>
          <p class="notes">${esc(template.sopNotes || "")}</p>
        </section>
        ${displayPanel(job)}
        <section class="panel">
          <h2>How many views are needed?</h2>
          <p class="notes">Minimum 2. The count turns on the first views in this template. Click a view to change the set.</p>
          <div class="views">
            <div class="stepper">
              <button type="button" class="btn small" id="fewer">−</button>
              <input id="viewCount" type="number" min="2" max="${order.length}" value="${selected.size || 2}">
              <button type="button" class="btn small" id="more">+</button>
            </div>
            ${chips}
          </div>
        </section>
        ${fileFacts(props, overall)}
        ${showSignoff ? signoffPanel(template, props) : ""}
        ${bendPanel(job)}
      </div>
      <div class="stack">
        ${bomPanel(job)}
        <div class="sticky-actions">
          <span class="muted">${showSignoff ? "Customer, order, and quote are not stored in the part file." : "Part number, material, thickness, and overall size come from the file."}</span>
          <button class="btn primary" type="submit">Generate sheet</button>
        </div>
      </div>
    </form>`;
  bindJob();
}

const STYLE_OPTIONS = [
  ["hidden-line-removed", "Hidden line removed"],
  ["hidden-line", "Hidden line"],
  ["shaded", "Shaded"],
  ["raster", "Raster"],
];
const SIZE_OPTIONS = ["0.10", "0.12", "0.18", "0.24"];

function savedDisplay(job) {
  const display = (job.model && job.model.display) || {};
  const size = String(display.annotationSize ?? "");
  return {
    viewStyle: STYLE_OPTIONS.some(([id]) => id === display.viewStyle) ? display.viewStyle : "hidden-line-removed",
    annotationSize: SIZE_OPTIONS.includes(size) ? size : "0.10",
    annotationStyle: display.annotationStyle === "bold" ? "bold" : "standard",
    balloons: display.balloons !== false,
    partsList: display.partsList !== false,
  };
}

function displayPanel(job) {
  const display = savedDisplay(job);
  const assembly = job.sourceKind === "iam";
  const styles = STYLE_OPTIONS.map(([id, label]) => `<option value="${id}" ${display.viewStyle === id ? "selected" : ""}>${label}</option>`).join("");
  const sizes = SIZE_OPTIONS.map((size) => `<option value="${size}" ${display.annotationSize === size ? "selected" : ""}>${size} in</option>`).join("");
  const lists = assembly
    ? `<label class="field"><span>Parts list</span><span><input type="checkbox" id="partsList" ${display.partsList ? "checked" : ""}> Show the parts list</span></label>
       <label class="field"><span>Balloons</span><span><input type="checkbox" id="balloons" ${display.balloons ? "checked" : ""}> Item balloons when the assembly has more than one part</span></label>`
    : `<p class="notes">A part has no parts list and no balloons. Those stay on assemblies.</p>`;
  return `<section class="panel">
    <h2>Style and annotations</h2>
    <div class="grid-2">
      <label class="field">View style<select id="viewStyle">${styles}</select></label>
      <label class="field">Annotation size<select id="annotationSize">${sizes}</select></label>
      <label class="field">Annotation style<select id="annotationStyle">
        <option value="standard" ${display.annotationStyle === "standard" ? "selected" : ""}>Standard</option>
        <option value="bold" ${display.annotationStyle === "bold" ? "selected" : ""}>Bold</option>
      </select></label>
    </div>
    ${lists}
    <p class="notes">Hidden line removed, hidden line, shaded, and raster are the Inventor view styles. The title block stays on the template border.</p>
  </section>`;
}

function field(label, key, value) {
  return `<label class="field">${esc(label)}<input data-prop="${esc(key)}" value="${esc(value ?? "")}"></label>`;
}

function fileFacts(props, overall) {
  const sized = ["length", "width", "height"].every((key) => Number(overall[key]) > 0);
  const size = sized ? `${trimNum(overall.length)} × ${trimNum(overall.width)} × ${trimNum(overall.height)} in` : "";
  const rows = [
    ["Part number", props.partNumber],
    ["Description", props.description],
    ["Material", props.material],
    ["Thickness", props.thickness],
    ["Mass", props.mass],
    ["Rev", props.rev],
    ["Designer", props.designer],
    ["Overall size", size],
  ].filter((row) => row[1]);
  if (!rows.length) return "";
  return `<section class="panel"><h2>From the file</h2><dl class="facts">${rows.map(([label, value]) => `<dt>${esc(label)}</dt><dd>${esc(value)}</dd>`).join("")}</dl></section>`;
}

function trimNum(value) {
  const number = Number(value);
  if (!Number.isFinite(number)) return "";
  return String(Math.round(number * 10000) / 10000);
}

function signoffPanel(template, props) {
  const extras = props.extras || {};
  const lines = (template.signoffFields || []).map((item) => `
    <label class="field">${esc(item.label)}<input data-extra="${esc(item.key)}" value="${esc(extras[item.key] ?? "")}"></label>`).join("");
  return `<section class="panel">
    <h2>Signoff block</h2>
    <div class="grid-2">
      ${field("Customer", "customer", props.customer)}
      ${field("Order number", "orderNumber", props.orderNumber)}
      ${field("Quote number", "quoteNumber", props.quoteNumber)}
      ${field("Signature", "signature", props.signature)}
      ${field("Date", "signDate", props.signDate)}
      ${lines}
    </div>
  </section>`;
}

function bendPanel(job) {
  const bends = (job.model && job.model.bends) || [];
  if (!bends.length) return "";
  const rows = bends.map((bend) => `<tr>
    <td>${esc(bend.id ?? "")}</td>
    <td>${esc(bend.direction ?? "")}</td>
    <td>${esc(bend.angle ?? "")}</td>
    <td>${esc(bend.radius ?? "")}</td>
  </tr>`).join("");
  return `<section class="panel">
    <h2>Bend table</h2>
    <table class="data">
      <thead><tr><th>ID</th><th>Direction</th><th>Angle</th><th>Radius</th></tr></thead>
      <tbody>${rows}</tbody>
    </table>
  </section>`;
}

function bomPanel(job) {
  if (job.sourceKind === "ipt") return "";
  const rowsIn = job.bomRows || [];
  if (!rowsIn.length) return "";
  const format = state.formats.find((item) => item.id === job.bomFormatId) || state.formats[0];
  const columns = (format && format.columns) || [];
  const options = state.formats.map((item) => `<option value="${esc(item.id)}" ${item.id === job.bomFormatId ? "selected" : ""}>${esc(item.name)}</option>`).join("");
  const head = columns.map((col) => `<th>${esc(col.heading)}</th>`).join("");
  const rows = rowsIn.map((row) => `<tr>
    ${columns.map((col) => `<td>${esc(row[col.key] ?? "")}</td>`).join("")}
  </tr>`).join("");
  return `<section class="panel">
    <h2>${esc((format && format.title) || "Parts List")}</h2>
    <label class="field">Format<select name="bomFormat">${options}</select></label>
    <table class="data" style="margin-top:10px">
      <thead><tr>${head}</tr></thead>
      <tbody>${rows}</tbody>
    </table>
  </section>`;
}

function collectRows(root, name) {
  const table = root.querySelector(`[data-rows="${name}"]`);
  if (!table) return null;
  return [...table.querySelectorAll("tbody tr")].map((tr) => {
    const row = {};
    tr.querySelectorAll("input[data-key]").forEach((input) => { row[input.dataset.key] = input.value; });
    return row;
  });
}

function collectJob(root) {
  root = root || document.getElementById("jobForm");
  const job = state.job;
  const props = { ...(job.properties || {}) };
  root.querySelectorAll("[data-prop]").forEach((input) => { props[input.dataset.prop] = input.value; });
  const extras = { ...(props.extras || {}) };
  root.querySelectorAll("[data-extra]").forEach((input) => { extras[input.dataset.extra] = input.value; });
  props.extras = extras;
  const model = { ...(job.model || {}), overall: { ...((job.model || {}).overall || {}) }, views: (job.model || {}).views || {} };
  root.querySelectorAll("[data-overall]").forEach((input) => { model.overall[input.dataset.overall] = input.value; });
  const bends = collectRows(root, "bend");
  if (bends) model.bends = bends;
  const style = root.querySelector("#viewStyle");
  if (style) {
    const size = Number((root.querySelector("#annotationSize") || {}).value || 0.10);
    const assembly = job.sourceKind === "iam";
    model.display = {
      viewStyle: style.value,
      annotationSize: Number.isFinite(size) && size > 0 ? size : 0.10,
      annotationStyle: (root.querySelector("#annotationStyle") || {}).value === "bold" ? "bold" : "standard",
      balloons: assembly ? !!(root.querySelector("#balloons") && root.querySelector("#balloons").checked) : false,
      partsList: assembly ? !!(root.querySelector("#partsList") && root.querySelector("#partsList").checked) : false,
    };
  } else if (job.model && job.model.display) {
    model.display = job.model.display;
  }
  const selectedViews = [...root.querySelectorAll(".chip.on")].map((chip) => chip.dataset.role);
  const templateId = (root.querySelector("input[name=template]:checked") || {}).value || job.templateId;
  const formatSelect = root.querySelector("select[name=bomFormat]");
  const bomFromTable = collectRows(root, "bom");
  return {
    templateId,
    bomFormatId: formatFrom(formatSelect, job),
    viewCount: Math.max(selectedViews.length, 2),
    selectedViews: selectedViews.length ? selectedViews : job.selectedViews,
    properties: props,
    model,
    bomRows: bomFromTable || job.bomRows || [],
  };
}

function formatFrom(select, job) {
  return select ? select.value : job.bomFormatId;
}

function bindJob() {
  const form = document.getElementById("jobForm");
  form.addEventListener("submit", async (event) => {
    event.preventDefault();
    await saveAndGenerate();
  });
  form.querySelectorAll("input[name=template]").forEach((input) => {
    input.addEventListener("change", async () => {
      const body = collectJob();
      const template = state.templates.find((item) => item.id === body.templateId);
      const defaults = (template && template.defaultViews) || [];
      body.selectedViews = defaults.slice(0, Math.max(2, defaults.length));
      body.viewCount = body.selectedViews.length;
      await persist(body, true);
    });
  });
  document.getElementById("showAll").addEventListener("change", (event) => {
    const body = collectJob();
    Object.assign(state.job, body);
    state.showAllTemplates = event.target.checked;
    renderJob();
  });
  document.getElementById("fewer").addEventListener("click", () => setViewCount(Number(document.getElementById("viewCount").value) - 1));
  document.getElementById("more").addEventListener("click", () => setViewCount(Number(document.getElementById("viewCount").value) + 1));
  document.getElementById("viewCount").addEventListener("change", (event) => setViewCount(Number(event.target.value)));
  form.querySelectorAll(".chip").forEach((chip) => chip.addEventListener("click", () => toggleChip(chip)));
  form.querySelectorAll("[data-remove]").forEach((button) => {
    button.addEventListener("click", () => {
      button.closest("tr").remove();
    });
  });
  const formatSelect = form.querySelector("select[name=bomFormat]");
  if (formatSelect) {
    formatSelect.addEventListener("change", async () => {
      await persist(collectJob(), true);
    });
  }
}

function setViewCount(count) {
  const template = currentTemplate();
  const order = (template.views || []).map((view) => view.role);
  const next = Math.max(2, Math.min(order.length, count || 2));
  document.getElementById("viewCount").value = String(next);
  document.querySelectorAll(".chip").forEach((chip) => {
    const index = order.indexOf(chip.dataset.role);
    chip.classList.toggle("on", index >= 0 && index < next);
  });
}

function toggleChip(chip) {
  const on = [...document.querySelectorAll(".chip.on")];
  if (chip.classList.contains("on") && on.length <= 2) return;
  chip.classList.toggle("on");
  const count = document.getElementById("viewCount");
  if (count) count.value = String(document.querySelectorAll(".chip.on").length);
}

async function persist(body, rerender) {
  state.job = await api(`/api/jobs/${state.job.id}`, {
    method: "PUT",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(body),
  });
  if (rerender) renderJob();
}

async function saveAndGenerate() {
  try {
    const body = collectJob();
    if ((body.selectedViews || []).length < 2) {
      state.error = "At least 2 views are required.";
      renderJob();
      return;
    }
    await persist(body, false);
    await api(`/api/jobs/${state.job.id}/generate`, { method: "POST" });
    location.hash = `#/sheet/${state.job.id}`;
  } catch (error) {
    flash(error);
  }
}

function renderSheet() {
  document.querySelector("main").classList.add("wide");
  const job = state.job;
  const props = job.properties || {};
  const template = currentTemplate() || { views: [] };
  const selected = new Set(job.selectedViews || []);
  const chips = (template.views || []).map((view) => `
    <button type="button" class="chip ${selected.has(view.role) ? "on" : ""}" data-role="${esc(view.role)}">${esc(view.label || view.role)}</button>`).join("");
  const checks = (job.sop || []).map((item) => `
    <div class="check ${esc(item.status)}"><strong>${esc(item.rule)}</strong><span>${esc(item.detail)}</span></div>`).join("");
  const behind = job.status === "draft" && job.hasSheet
    ? `<div class="banner warn"><p>This is the last generated sheet. Generate again after edits.</p></div>` : "";
  const pdf = job.hasSheet ? sheetLink(job.id, "sheet.pdf") : { url: "#", download: "" };
  const dxf = job.hasSheet ? sheetLink(job.id, "sheet.dxf") : { url: "#", download: "" };
  const svg = job.hasSheet ? sheetLink(job.id, "sheet.svg") : { url: "#", download: "" };
  const csv = job.hasSheet && job.bomReady ? sheetLink(job.id, "bom.csv") : null;
  const download = (link) => (link && link.download ? `download="${esc(link.download)}"` : "");
  app.innerHTML = `
    ${errorBlock()}
    ${behind}
    <div class="actions" style="margin-bottom:12px">
      <a class="btn" href="#/job/${esc(job.id)}">Edit setup</a>
      <a class="btn primary" href="${esc(pdf.url)}" ${download(pdf)}>PDF</a>
      <a class="btn" href="${esc(dxf.url)}" ${download(dxf)}>DXF</a>
      <a class="btn" href="${esc(svg.url)}" ${download(svg)}>SVG</a>
      ${csv ? `<a class="btn" href="${esc(csv.url)}" ${download(csv)}>BOM CSV</a>` : ""}
      <button class="btn" type="button" id="zoomOut">−</button>
      <button class="btn" type="button" id="zoomIn">+</button>
      <span class="muted">${esc(props.partNumber || "")} · ${esc(job.status)} · ${esc(formatWhen(job.updatedAt))}</span>
    </div>
    <div class="sheet-page">
      <div class="sheet-scroll" id="sheetScroll">${job.hasSheet ? `<img id="sheetImg" alt="Production drawing for ${esc(props.partNumber || "this part")}" src="${esc(svg.download ? svg.url : `${svg.url}?v=${Date.now()}`)}">` : ""}</div>
      <aside>
        <form id="sheetForm" class="stack">
          <section class="panel">
            <h2>Views</h2>
            <p class="notes">Every view on this template. At least two stay on.</p>
            <div class="views">${chips}</div>
          </section>
          ${displayPanel(job)}
          <button class="btn primary" type="submit">Update drawing</button>
        </form>
        <h2>SOP check</h2>
        <div class="checks">${checks || "<p class='muted'>Generate the sheet to run the checklist.</p>"}</div>
      </aside>
    </div>`;
  const sheetForm = document.getElementById("sheetForm");
  sheetForm.querySelectorAll(".chip").forEach((chip) => chip.addEventListener("click", () => toggleChip(chip)));
  sheetForm.addEventListener("submit", (event) => {
    event.preventDefault();
    updateDrawing();
  });
  if (!job.hasSheet) {
    document.getElementById("sheetScroll").innerHTML = `<div class="banner warn"><p>Generate the sheet from the setup page.</p></div>`;
    return;
  }
  const img = document.getElementById("sheetImg");
  const fit = () => {
    const scroll = document.getElementById("sheetScroll");
    img.style.width = `${Math.max(640, scroll.clientWidth - 40) * state.zoom}px`;
  };
  img.addEventListener("load", fit);
  document.getElementById("zoomIn").addEventListener("click", () => { state.zoom = Math.min(2.6, state.zoom + 0.25); fit(); });
  document.getElementById("zoomOut").addEventListener("click", () => { state.zoom = Math.max(0.6, state.zoom - 0.25); fit(); });
}

async function updateDrawing() {
  try {
    const body = collectJob(document.getElementById("sheetForm"));
    if ((body.selectedViews || []).length < 2) {
      state.error = "At least 2 views are required.";
      renderSheet();
      return;
    }
    await persist(body, false);
    await api(`/api/jobs/${state.job.id}/generate`, { method: "POST" });
    await boot();
  } catch (error) {
    flash(error);
  }
}

function renderLibrary() {
  document.querySelector("main").classList.remove("wide");
  const rows = state.jobs.map((job) => `
    <a class="lib" href="${job.hasSheet ? `#/sheet/${esc(job.id)}` : `#/job/${esc(job.id)}`}">
      <b class="mono">${esc(job.partNumber || "—")}</b>
      <span>${esc(job.description || job.sourceName || "Untitled")}<br><span class="muted">${esc(formatWhen(job.updatedAt))} · ${job.viewCount || 0} views</span></span>
      <span class="tag">${esc(job.sourceKind || "")}</span>
      <span class="status ${esc(job.status)}">${esc(statusLabel(job.status))}</span>
    </a>`).join("");
  app.innerHTML = `
    <h1>Issued drawings</h1>
    <p class="lede">Sheets stay on the template and BOM format they were generated with. Editing a template later does not rewrite a sheet that is already issued.</p>
    <div class="library">${rows || `<div class="panel"><p>No sheets yet. Drop an Inventor part or assembly.</p><a class="btn primary" href="#/new">New drawing</a></div>`}</div>`;
}

function statusLabel(status) {
  if (status === "ready") return "Ready to issue";
  if (status === "review") return "Needs a look";
  return "Setup";
}

function sheetKindFor(template, job) {
  if (!template || template.drawingType !== "standard") return (template && template.drawingType) || "part";
  const modelKind = job && job.model && job.model.kind;
  if (modelKind === "weldment") return "weldment";
  if ((job && job.sourceKind === "iam") || modelKind === "assembly") return "assembly";
  return "part";
}

function templateSourceNote() {
  const source = state.templateSource;
  if (!source) return "";
  const pages = source.pages ? `<span>Opened from GitHub Pages. Sheets stay in this browser.</span>` : "";
  return `<div class="source-banner"><strong>Three drawing templates</strong><span>Standard.idw, Standard.dwg, and Sign off.</span>${pages}<span class="path">${esc(source.path)}</span></div>`;
}

function templateMeta(item) {
  const file = item.source && item.source.relativePath ? `${item.source.relativePath} · ` : "";
  return `${file}${item.drawingType} · sheet ${item.sheetLabel} · ${item.sheetWidthIn} × ${item.sheetHeightIn} in`;
}

function appliesLabel(value) {
  if (value === "both") return "ipt · iam";
  return value;
}

function renderTemplates(id) {
  document.querySelector("main").classList.remove("wide");
  const template = state.templates.find((item) => item.id === id) || state.templates[0];
  const list = state.templates.map((item) => `
    <button class="list-row ${item.id === template.id ? "on" : ""}" data-id="${esc(item.id)}">
      <strong>${esc(item.name)}</strong>
      <span class="muted">${esc(templateMeta(item))}</span>
    </button>`).join("");
  app.innerHTML = `
    ${errorBlock()}
    <h1>Drawing templates</h1>
    <p class="lede">Two standard drawings and one sign off. Title block, views, and sheet size stay editable. The next sheet uses the saved copy.</p>
    ${templateSourceNote()}
    <div class="split">
      <div>
        ${list}
      </div>
      <form class="editor" id="templateForm" data-template-id="${esc(template.id)}">${templateEditor(template)}</form>
    </div>`;
  app.querySelectorAll(".list-row").forEach((button) => {
    button.addEventListener("click", () => { location.hash = `#/templates/${button.dataset.id}`; });
  });
  document.getElementById("templateForm").addEventListener("submit", (event) => saveTemplate(event, template));
  document.getElementById("addView").addEventListener("click", () => addEditorRow("views", viewRow({ role: "front", label: "FRONT" })));
  const addColumn = document.getElementById("addColumn");
  if (addColumn) addColumn.addEventListener("click", () => addEditorRow("columns", columnRow({ key: "note", heading: "NOTE", width: 20 })));
  const addField = document.getElementById("addField");
  if (addField) addField.addEventListener("click", () => addEditorRow("fields", fieldRow({ key: "note", label: "NOTE" })));
  document.getElementById("sheetLabel").addEventListener("change", (event) => applySheetSize(event.target.value));
  bindRemove();
}

function templateEditor(template) {
  const company = template.company || {};
  const tolerances = (company.tolerances || []).join("\n");
  const views = (template.views || []).map(viewRow).join("");
  const bend = template.table && template.table.kind === "bend";
  const columns = bend ? (template.table.columns || []).map((col) => columnRow({ ...col, width: Math.round((col.width || 0) * 100) })).join("") : "";
  const fields = (template.signoffFields || []).map(fieldRow).join("");
  const sheetLabels = ["A", "B", "C", "D", "E"];
  if (template.sheetLabel && !sheetLabels.includes(template.sheetLabel)) sheetLabels.push(template.sheetLabel);
  const source = template.source && template.source.fileName
    ? `<p class="notes">File ${esc(template.source.folder)}\\${esc(template.source.relativePath || template.source.fileName)}${template.source.titleBlock ? ` · title block ${esc(template.source.titleBlock)}` : ""}${template.source.sheetSizeRead ? "" : " · sheet size not read from Inventor"}</p>`
    : "";
  return `
    ${source}
    <div class="grid-2">
      <label class="field">Name<input name="name" value="${esc(template.name)}"></label>
      <label class="field">Drawing type
        <select name="drawingType">${["standard", "part", "weldment", "assembly", "signoff"].map((item) => `<option ${item === template.drawingType ? "selected" : ""}>${item}</option>`).join("")}</select>
      </label>
      <label class="field">Applies to
        <select name="appliesTo">
          <option value="ipt" ${template.appliesTo === "ipt" ? "selected" : ""}>.ipt part</option>
          <option value="iam" ${template.appliesTo === "iam" ? "selected" : ""}>.iam assembly</option>
          <option value="both" ${template.appliesTo === "both" ? "selected" : ""}>.ipt and .iam</option>
        </select>
      </label>
      <label class="field">Sheet<select name="sheetLabel" id="sheetLabel">${sheetLabels.map((item) => `<option ${item === template.sheetLabel ? "selected" : ""}>${item}</option>`).join("")}</select></label>
      <label class="field">Width, in<input name="sheetWidthIn" id="sheetWidth" value="${esc(template.sheetWidthIn)}"></label>
      <label class="field">Height, in<input name="sheetHeightIn" id="sheetHeight" value="${esc(template.sheetHeightIn)}"></label>
      <label class="field">Company<input name="companyName" value="${esc(company.name || "")}"></label>
      <label class="field">Sub line<input name="companySub" value="${esc(company.sub || "")}"></label>
      <label class="field">Mark
        <select name="mark"><option value="star" ${company.mark === "star" ? "selected" : ""}>Star</option><option value="diamond" ${company.mark === "diamond" ? "selected" : ""}>Diamond</option><option value="none" ${company.mark === "none" ? "selected" : ""}>None</option></select>
      </label>
      <label class="field">Product series<input name="productSeries" value="${esc(company.productSeries || "")}"></label>
    </div>
    <label class="field" style="margin-top:10px">Tolerances, one per line<textarea name="tolerances">${esc(tolerances)}</textarea></label>
    <label class="field">Standard note<textarea name="standard">${esc(company.standard || "")}</textarea></label>
    <label class="field">Proprietary notice<textarea name="proprietary">${esc(company.proprietary || "")}</textarea></label>
    <label class="field">SOP notes for this template<textarea name="sopNotes">${esc(template.sopNotes || "")}</textarea></label>
    <h2 style="margin-top:16px">Views, in the order the count uses</h2>
    <div id="views">${views}</div>
    <button class="btn small" type="button" id="addView">Add view</button>
    <label class="field" style="margin-top:14px">Table
      <select name="tableKind">
        ${["auto", "none", "bend", "parts", "signoff"].map((item) => `<option value="${item}" ${(template.table || {}).kind === item ? "selected" : ""}>${item}</option>`).join("")}
      </select>
    </label>
    ${bend ? `<h2>Bend table columns</h2><div id="columns">${columns}</div><button class="btn small" type="button" id="addColumn">Add column</button>` : `<div id="columns"></div>`}
    <h2 style="margin-top:16px">Signoff lines</h2>
    <div id="fields">${fields}</div>
    <button class="btn small" type="button" id="addField">Add line</button>
    <div class="actions" style="margin-top:16px">
      <button class="btn primary" type="submit">Save template</button>
    </div>`;
}

function viewRow(view) {
  const roles = ["flat", "front", "side", "top", "bottom", "back", "end", "iso", "section", "inlet", "discharge", "detail"];
  return `<div class="view-row">
    <select data-view-role>${roles.map((role) => `<option ${role === view.role ? "selected" : ""}>${role}</option>`).join("")}</select>
    <input data-view-label value="${esc(view.label || "")}">
    <button type="button" class="btn small" data-up>Up</button>
    <button type="button" class="btn small" data-down>Down</button>
    <button type="button" class="btn small" data-remove-row>Remove</button>
  </div>`;
}

function columnRow(col) {
  return `<div class="row">
    <input data-col-heading placeholder="Heading" value="${esc(col.heading || "")}">
    <input data-col-key placeholder="key" value="${esc(col.key || "")}">
    <input data-col-width placeholder="%" value="${esc(col.width ?? "")}">
    <button type="button" class="btn small" data-up>Up</button>
    <button type="button" class="btn small" data-remove-row>Remove</button>
  </div>`;
}

function fieldRow(field) {
  return `<div class="row">
    <input data-field-label placeholder="Label" value="${esc(field.label || "")}">
    <input data-field-key placeholder="key" value="${esc(field.key || "")}">
    <span></span>
    <button type="button" class="btn small" data-up>Up</button>
    <button type="button" class="btn small" data-remove-row>Remove</button>
  </div>`;
}

function addEditorRow(id, html) {
  document.getElementById(id).insertAdjacentHTML("beforeend", html);
  bindRemove();
}

function bindRemove() {
  document.querySelectorAll("[data-remove-row]").forEach((button) => {
    button.onclick = () => button.parentElement.remove();
  });
  document.querySelectorAll("[data-up]").forEach((button) => {
    button.onclick = () => {
      const row = button.parentElement;
      const prev = row.previousElementSibling;
      if (prev) row.parentElement.insertBefore(row, prev);
    };
  });
  document.querySelectorAll("[data-down]").forEach((button) => {
    button.onclick = () => {
      const row = button.parentElement;
      const next = row.nextElementSibling;
      if (next) row.parentElement.insertBefore(next, row);
    };
  });
  const del = document.getElementById("deleteTemplate");
  if (del) {
    del.onclick = async () => {
      const id = document.getElementById("templateForm").dataset.templateId;
      if (!confirm("Delete this template?")) return;
      try {
        await api(`/api/templates/${id}`, { method: "DELETE" });
        location.hash = "#/templates";
        boot();
      } catch (error) {
        flash(error);
      }
    };
  }
}

function applySheetSize(label) {
  const sizes = { A: [11, 8.5], B: [17, 11], C: [22, 17], D: [34, 22], E: [44, 34] };
  const size = sizes[label];
  if (!size) return;
  document.getElementById("sheetWidth").value = size[0];
  document.getElementById("sheetHeight").value = size[1];
}

async function saveTemplate(event, template) {
  event.preventDefault();
  const form = event.target;
  const data = new FormData(form);
  const views = [...form.querySelectorAll(".view-row")].map((row) => ({
    role: row.querySelector("[data-view-role]").value,
    label: row.querySelector("[data-view-label]").value,
  }));
  const kind = data.get("tableKind");
  const table = { kind };
  if (kind === "bend") {
    table.title = "TABLE";
    table.columns = [...form.querySelectorAll("#columns .row")].map((row) => ({
      heading: row.querySelector("[data-col-heading]").value,
      key: row.querySelector("[data-col-key]").value,
      width: Number(row.querySelector("[data-col-width]").value || 0),
    }));
  }
  const signoffFields = [...form.querySelectorAll("#fields .row")].map((row) => ({
    label: row.querySelector("[data-field-label]").value,
    key: row.querySelector("[data-field-key]").value,
  })).filter((item) => item.key && item.label);
  const body = {
    name: data.get("name"),
    drawingType: data.get("drawingType"),
    appliesTo: data.get("appliesTo"),
    sheetLabel: data.get("sheetLabel"),
    sheetWidthIn: Number(data.get("sheetWidthIn")),
    sheetHeightIn: Number(data.get("sheetHeightIn")),
    company: {
      ...(template.company || {}),
      name: data.get("companyName"),
      sub: data.get("companySub"),
      mark: data.get("mark"),
      productSeries: data.get("productSeries"),
      standard: data.get("standard"),
      proprietary: data.get("proprietary"),
      tolerances: String(data.get("tolerances") || "").split("\n").map((line) => line.trim()).filter(Boolean),
    },
    views,
    defaultViews: views.map((view) => view.role),
    table,
    signoffFields,
    sopNotes: data.get("sopNotes"),
  };
  try {
    await api(`/api/templates/${template.id}`, {
      method: "PUT",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(body),
    });
    state.templates = await api("/api/templates");
    state.error = "";
    renderTemplates(template.id);
  } catch (error) {
    flash(error);
  }
}

function renderFormats(id) {
  document.querySelector("main").classList.remove("wide");
  const format = state.formats.find((item) => item.id === id) || state.formats[0];
  const list = state.formats.map((item) => `
    <button class="list-row ${item.id === format.id ? "on" : ""}" data-id="${esc(item.id)}">
      <strong>${esc(item.name)}</strong>
      <span class="muted">${item.isDefault ? "Default · " : ""}${esc(item.title)}</span>
    </button>`).join("");
  const columns = (format.columns || []).map((col) => columnRow({ ...col, width: Math.round(col.width * 100) })).join("");
  app.innerHTML = `
    ${errorBlock()}
    <h1>BOM format</h1>
    <p class="lede">The parts list is built in this format as soon as an assembly is dropped. Column headings, order, and the table title can be changed here.</p>
    <div class="split">
      <div>
        ${list}
        <button class="btn" id="duplicateFormat" type="button">Duplicate</button>
      </div>
      <form class="editor" id="formatForm">
        <div class="grid-2">
          <label class="field">Name<input name="name" value="${esc(format.name)}"></label>
          <label class="field">Table title<input name="title" value="${esc(format.title)}"></label>
        </div>
        <label class="field" style="margin:10px 0"><span><input type="checkbox" name="isDefault" ${format.isDefault ? "checked" : ""}> Use this format for new assemblies</span></label>
        <label class="field"><span><input type="checkbox" name="showBalloons" ${format.showBalloons ? "checked" : ""}> Numbered balloons on the views</span></label>
        <h2 style="margin-top:16px">Columns</h2>
        <div id="columns">${columns}</div>
        <button class="btn small" type="button" id="addColumn">Add column</button>
        <div class="actions" style="margin-top:16px">
          <button class="btn primary" type="submit">Save format</button>
          <button class="btn" type="button" id="deleteFormat">Delete</button>
        </div>
      </form>
    </div>`;
  app.querySelectorAll(".list-row").forEach((button) => {
    button.addEventListener("click", () => { location.hash = `#/formats/${button.dataset.id}`; });
  });
  document.getElementById("duplicateFormat").addEventListener("click", async () => {
    const copy = await api(`/api/bom-formats/${format.id}/duplicate`, { method: "POST" });
    location.hash = `#/formats/${copy.id}`;
  });
  document.getElementById("addColumn").addEventListener("click", () => addEditorRow("columns", columnRow({ key: "material", heading: "MATERIAL", width: 20 })));
  bindRemove();
  document.getElementById("formatForm").addEventListener("submit", (event) => saveFormat(event, format));
  document.getElementById("deleteFormat").onclick = async () => {
    if (!confirm("Delete this BOM format?")) return;
    try {
      await api(`/api/bom-formats/${format.id}`, { method: "DELETE" });
      location.hash = "#/formats";
      boot();
    } catch (error) {
      flash(error);
    }
  };
}

async function saveFormat(event, format) {
  event.preventDefault();
  const form = event.target;
  const data = new FormData(form);
  const columns = [...form.querySelectorAll("#columns .row")].map((row) => ({
    heading: row.querySelector("[data-col-heading]").value,
    key: row.querySelector("[data-col-key]").value,
    width: Number(row.querySelector("[data-col-width]").value || 0),
  }));
  try {
    await api(`/api/bom-formats/${format.id}`, {
      method: "PUT",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        name: data.get("name"),
        title: data.get("title"),
        isDefault: form.querySelector("[name=isDefault]").checked,
        showBalloons: form.querySelector("[name=showBalloons]").checked,
        columns,
      }),
    });
    state.formats = await api("/api/bom-formats");
    state.error = "";
    renderFormats(format.id);
  } catch (error) {
    flash(error);
  }
}

window.addEventListener("hashchange", boot);
boot();
