const $ = (id) => document.getElementById(id);
const esc = (v) => String(v ?? "").replace(/[&<>"']/g, (c) => ({
  "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;",
}[c]));
const VERDICT_TEXT = {
  "no-go": "No-go", go: "Go", conditional: "Conditional",
  needs_confirmation: "Needs one more check",
};
const LAMPS = [
  ["federal", "Federal"], ["iso_rto", "Grid/ISO"], ["state", "State"],
  ["county", "County"], ["city", "City"],
];
const LAMP_WORD = {
  fatal: "Stop", major: "Needs a fix", minor: "Noted", clear: "Clear",
  unknown: "Not checked", not_modelled: "Out of scope",
};

async function api(path, opts) {
  const res = await fetch(path, opts);
  if (!res.ok) {
    const detail = await res.text();
    throw new Error(`Request failed (${res.status}): ${detail.slice(0, 200)}`);
  }
  return res.json();
}

const state = { rows: [], reports: {}, contexts: {}, selected: null, dots: {}, map: null, layers: null, sampleMode: false, popupAt: 0, currentCtx: null };

function dismissGuide() {
  try { localStorage.setItem("sitewhy-guide-dismissed", "1"); } catch { /* private mode */ }
}
function guideDismissed() {
  try { return localStorage.getItem("sitewhy-guide-dismissed") === "1"; }
  catch { return false; }
}

function shortAddress(address) {
  return String(address || "").split(",")[0].trim();
}

function isSelected(r) {
  return !!state.selected && state.selected.kind === (r.kind || "showcase") && state.selected.id === (r.id || r.name);
}

function renderPortfolio() {
  const paint = (ul, rows) => {
    ul.innerHTML = rows.map((r) => {
      const id = r.id || r.name;
      const kind = r.kind || "showcase";
      const current = isSelected(r) ? "true" : "false";
      return `<li><button type="button" class="site-row" data-kind="${esc(kind)}" data-id="${esc(id)}" aria-current="${current}">`
        + `<span class="dot ${esc(r.verdict)}" aria-hidden="true"></span>`
        + `<span><span class="addr">${esc(shortAddress(r.address))}</span>`
        + `<span class="meta">${esc(r.mw)} MW${r.county ? ` · ${esc(r.county)}` : ""} · ${esc(VERDICT_TEXT[r.verdict] || r.verdict)}</span></span>`
        + `</button></li>`;
    }).join("");
    ul.querySelectorAll("button").forEach((b) =>
      b.addEventListener("click", () => selectRow(b.dataset.kind, b.dataset.id, true)));
  };
  paint($("portfolio"), state.rows.filter((r) => (r.kind || "showcase") === "showcase"));
  const live = state.rows.filter((r) => r.kind === "live");
  $("live-details").hidden = live.length === 0 && !$("running-row");
  paint($("portfolio-live"), live);
}

function selectRow(kind, id, fly) {
  if (kind === "live") selectLive(id, fly);
  else selectSite(id, fly);
}

async function bootPortfolio() {
  let rows;
  try {
    rows = await api("/portfolio");
  } catch (err) {
    $("portfolio").innerHTML = `<li class="note">Could not load the portfolio. Check the server and reload.</li>`;
    renderLampsFallback();
    renderTelemetryFallback();
    return;
  }
  state.rows = rows;
  renderPortfolio();
  renderDots();
  if (location.hash === "#/demo") return;
  const hash = parseHash();
  if (hash) {
    await restoreHash(hash);
  } else if (guideDismissed()) {
    const first = rows.find((r) => (r.kind || "showcase") === "showcase") || rows[0];
    if (first) await selectRow(first.kind || "showcase", first.id || first.name, false);
    else showGuide(false);
  } else {
    showGuide(false);
  }
}

function parseHash() {
  const m = location.hash.match(/^#\/(site|run)\/([^/]+)$/);
  return m ? { kind: m[1], id: decodeURIComponent(m[2]) } : null;
}

async function restoreHash({ kind, id }) {
  const row = state.rows.find((r) => (r.kind || "showcase") === (kind === "run" ? "live" : "showcase") && (r.id || r.name) === id);
  if (row) await selectRow(row.kind || "showcase", row.id || row.name, false);
  else if (kind === "site") await selectSite(id, false);
  else await selectLive(id, false);
}

function setHash(kind, id) {
  const h = kind === "live" ? `#/run/${encodeURIComponent(id)}` : `#/site/${encodeURIComponent(id)}`;
  if (location.hash !== h) location.hash = h;
}

addEventListener("hashchange", () => {
  const hash = parseHash();
  if (!hash) { showGuide(!!state.currentReport); return; }
  const key = `${hash.kind}:${hash.id}`;
  const cur = state.selected ? `${state.selected.kind === "live" ? "run" : "site"}:${state.selected.id}` : "";
  if (key !== cur) restoreHash(hash);
});

function tileUrl(kind) {
  if (new URLSearchParams(location.search).get("tiles") === "invalid") return "https://invalid.local/tiles/{z}/{x}/{y}.png";
  return kind;
}

function ensureMap(lat, lon) {
  if (state.map) return;
  if (!window.L) { showMapFallback(lat, lon, null); return; }
  const reduced = matchMedia("(prefers-reduced-motion: reduce)").matches;
  const esri = L.tileLayer(tileUrl("https://server.arcgisonline.com/ArcGIS/rest/services/World_Imagery/MapServer/tile/{z}/{y}/{x}"), {
    maxZoom: 19, attribution: "Esri, Maxar, Earthstar Geographics",
  });
  const streets = L.tileLayer(tileUrl("https://tile.openstreetmap.org/{z}/{x}/{y}.png"), {
    maxZoom: 19, attribution: "© OpenStreetMap contributors",
  });
  const dark = L.tileLayer(tileUrl("https://{s}.basemaps.cartocdn.com/dark_all/{z}/{x}/{y}.png"), {
    maxZoom: 20, subdomains: "abcd", attribution: "© OpenStreetMap contributors © CARTO",
  });
  state.map = L.map("map", {
    center: [lat, lon], zoom: 12, layers: [esri], zoomControl: false,
    fadeAnimation: !reduced, zoomAnimation: !reduced, inertia: !reduced,
  });
  state.baseLayers = { sat: esri, street: streets, dark };
  state.map.on("click", onMapClick);
  let watchdog = null, okTiles = false;
  const armWatchdog = () => {
    clearTimeout(watchdog);
    watchdog = setTimeout(() => {
      if (!okTiles) showMapFallback(lat, lon, state.contexts[state.selected]?.google_maps_url || null);
    }, 12000);
  };
  state.map.on("loading", () => { okTiles = false; armWatchdog(); });
  state.map.on("load", () => {
    clearTimeout(watchdog);
    if (okTiles) $("map-fallback").hidden = true;
  });
  for (const layer of [esri, streets, dark]) {
    layer.on("tileload", () => { okTiles = true; });
    layer.on("tileerror", () => {
      state.tileErrors = (state.tileErrors || 0) + 1;
      if (state.tileErrors >= 4) showMapFallback(lat, lon, state.contexts[state.selected]?.google_maps_url || null);
    });
  }
  addMapControls();
  state.layers = { county: null, place: null, transmission: null, pin: null };
}

function showMapFallback(lat, lon, mapsUrl) {
  const fb = $("map-fallback");
  $("fallback-coords").textContent = `${lat}, ${lon}`;
  fb.querySelector("a.gmaps-fallback")?.remove();
  if (mapsUrl) {
    const a = document.createElement("a");
    a.className = "gmaps-fallback";
    a.href = mapsUrl;
    a.target = "_blank";
    a.rel = "noopener";
    a.textContent = "Open in Google Maps";
    fb.appendChild(a);
  }
  fb.hidden = false;
}

function addMapControls() {
  const wrap = document.querySelector(".map-wrap");
  if (wrap.querySelector(".zoom-controls")) return;
  const zoom = document.createElement("div");
  zoom.className = "zoom-controls";
  zoom.setAttribute("role", "group");
  zoom.setAttribute("aria-label", "Map zoom");
  const mk = (label, name) => {
    const b = document.createElement("button");
    b.type = "button";
    b.className = "zoom-btn";
    b.textContent = label;
    b.setAttribute("aria-label", name);
    b.addEventListener("click", () => (label === "+" ? state.map.zoomIn() : state.map.zoomOut()));
    return b;
  };
  zoom.append(mk("+", "Zoom in"), mk("−", "Zoom out"));
  wrap.appendChild(zoom);
  const bases = document.createElement("div");
  bases.className = "basemaps";
  bases.setAttribute("role", "radiogroup");
  bases.setAttribute("aria-label", "Basemap");
  bases.innerHTML = `<p class="label" aria-hidden="true">Basemap</p>`;
  [["sat", "Satellite"], ["street", "Streets"], ["dark", "Dark"]].forEach(([value, label], i) => {
    const l = document.createElement("label");
    const r = document.createElement("input");
    r.type = "radio";
    r.name = "basemap";
    r.value = value;
    if (i === 0) r.checked = true;
    r.addEventListener("change", () => setBasemap(value));
    l.append(r, document.createTextNode(` ${label}`));
    bases.appendChild(l);
  });
  wrap.appendChild(bases);
}

function setBasemap(which) {
  if (!state.map || !state.baseLayers) return;
  for (const [name, layer] of Object.entries(state.baseLayers)) {
    if (state.map.hasLayer(layer) && name !== which) state.map.removeLayer(layer);
  }
  const next = state.baseLayers[which];
  if (next && !state.map.hasLayer(next)) next.addTo(state.map);
}

function verdictClass(v) {
  return ["no-go", "conditional", "go"].includes(v) ? v : "needs_confirmation";
}

function renderOverlays(report, ctx) {
  const j = report.jurisdiction || {};
  const lat = j.lat, lon = j.lon;
  ensureMap(lat, lon);
  const note = $("map-note");
  if (!state.map) return;
  const L_ = window.L;
  for (const key of ["county", "place", "transmission", "pin"]) state.layers[key]?.remove();
  Object.values(state.dots).forEach((d) => d.remove());
  state.dots = {};
  if (!ctx) {
    note.textContent = "Boundary data unavailable.";
    note.hidden = false;
  } else {
    note.hidden = true;
    if (ctx.county?.features?.length) {
      const halo = L_.geoJSON(ctx.county, {
        style: { color: "#0d1417", weight: 5.5, opacity: 0.9, fill: false },
      });
      const line = L_.geoJSON(ctx.county, {
        style: { color: "#b7d8c7", weight: 2.5, fillColor: "#b7d8c7", fillOpacity: 0.08 },
      });
      state.layers.county = L_.layerGroup([halo, line]).addTo(state.map);
    }
    if (ctx.place) {
      state.layers.place = L_.geoJSON(ctx.place, {
        style: { color: "#c64d2e", weight: 2, dashArray: "6 4", fill: false },
      }).addTo(state.map);
      const name = ctx.place.properties?.NAME;
      if (name) state.layers.place.bindTooltip(esc(name), { direction: "top", className: "city-label" });
    }
    if (ctx.transmission?.features?.length) {
      state.layers.transmission = L_.geoJSON(ctx.transmission, {
        style: { color: "#e0a83c", weight: 1, opacity: 0.85 },
        onEachFeature: (f, layer) => {
          const p = f.properties || {};
          if (p.VOLTAGE) layer.bindTooltip(`${esc(String(p.VOLTAGE))} kV · ${esc(p.OWNER || "unknown owner")}`);
        },
      }).addTo(state.map);
    }
  }
  const v = verdictClass(report.verdict);
  state.layers.pin = L_.marker([lat, lon], {
    icon: L_.divIcon({ className: "", html: `<div class="site-pin ${v}" aria-hidden="true"><span></span></div>`, iconSize: [44, 44], iconAnchor: [22, 22] }),
    title: report.project?.address || "",
    alt: `Selected site: ${report.project?.address || ""}`,
  }).addTo(state.map);
  renderDots();
  const link = document.querySelector(".gmaps");
  if (link) link.remove();
  if (ctx?.google_maps_url) {
    const a = document.createElement("a");
    a.className = "gmaps";
    a.href = ctx.google_maps_url;
    a.target = "_blank";
    a.rel = "noopener";
    a.textContent = "Open in Google Maps";
    document.querySelector(".map-wrap").appendChild(a);
  }
  state.map.flyTo([lat, lon], Math.max(state.map.getZoom(), 11), { duration: reduced() ? 0 : 0.8 });
}

function renderDots() {
  if (!state.map || !window.L) return;
  Object.values(state.dots).forEach((d) => d.remove());
  state.dots = {};
  for (const r of state.rows) {
    const id = r.id || r.name;
    const kind = r.kind || "showcase";
    if (r.lat === undefined || r.lon === undefined) continue;
    if (state.selected && state.selected.kind === kind && state.selected.id === id) continue;
    const dot = window.L.marker([r.lat, r.lon], {
      icon: window.L.divIcon({ className: "", html: `<div class="site-dot ${verdictClass(r.verdict)}" aria-hidden="true"><span></span></div>`, iconSize: [44, 44], iconAnchor: [22, 22] }),
      title: r.address, alt: r.address,
    });
    dot.on("click", () => { state.popupAt = Date.now(); selectRow(kind, id, true); });
    dot.addTo(state.map);
    state.dots[`${kind}:${id}`] = dot;
  }
}

function onMapClick(e) {
  if (!state.map || Date.now() - state.popupAt < 500) return;
  if (state.sampleMode) return;
  const lat = Math.round(e.latlng.lat * 10000) / 10000;
  const lon = Math.round(e.latlng.lng * 10000) / 10000;
  const div = document.createElement("div");
  div.className = "map-popup";
  {
    div.innerHTML = `<p><strong>Screen this location</strong><br>${esc(lat)}, ${esc(lon)}</p>`
      + `<form><div class="field"><label class="label" for="popup-mw">IT load (MW)</label>`
      + `<input id="popup-mw" name="mw" type="number" min="1" max="10000" step="1" value="300" required></div>`
      + `<p class="status" data-role="error"></p>`
      + `<button type="submit">Screen ${esc(lat)}, ${esc(lon)}</button></form>`;
    div.querySelector("form").addEventListener("submit", async (ev) => {
      ev.preventDefault();
      const mw = Number(div.querySelector("#popup-mw").value);
      state.map.closePopup();
      await submitRun({ lat, lon, mw }, `${lat}, ${lon}`);
    });
  }
  window.L.popup().setLatLng(e.latlng).setContent(div).openOn(state.map);
}

function reduced() {
  return matchMedia("(prefers-reduced-motion: reduce)").matches;
}

function chipText(report) {
  const j = report.jurisdiction || {};
  const county = j.county_name || "County";
  const short = county.replace(/ County$/, "");
  const countyFinding = (report.findings || []).find((f) => f.layer === "county");
  if (countyFinding) {
    const scope = countyFinding.parameters?.scope;
    if (countyFinding.applies === "no" && scope === "unincorporated" && j.place) {
      return `Inside ${j.place} — ${short} pause covers unincorporated areas only`;
    }
    if (countyFinding.applies === "yes" && !j.place) return `${county} pause covers this unincorporated site`;
    if (countyFinding.applies === "yes") return `${county} pause applies here`;
    return `${short} pause does not reach this site`;
  }
  if (report.explanation?.headline) return report.explanation.headline;
  return `Verdict: ${VERDICT_TEXT[report.verdict] || report.verdict}`;
}

function lampFor(layer, report) {
  const entry = report.explanation?.layer_status?.[layer];
  if (entry && LAMP_WORD[entry.lamp]) return { lamp: entry.lamp, summary: entry.summary || "" };
  return { lamp: "unknown", summary: "Explanation arrives with the next backend step." };
}

function renderLamps(report) {
  $("lamps").innerHTML = LAMPS.map(([key, name]) => {
    const { lamp, summary } = lampFor(key, report);
    return `<li class="lamp" tabindex="0" aria-label="${esc(name)}: ${esc(LAMP_WORD[lamp])}. ${esc(summary)}" title="${esc(summary)}">`
      + `<span class="dot ${esc(lamp)}" aria-hidden="true"></span>`
      + `<span class="name">${esc(name)}</span><span class="state">${esc(LAMP_WORD[lamp])}</span></li>`;
  }).join("");
}

function renderLampsFallback() {
  $("lamps").innerHTML = LAMPS.map(([, name]) =>
    `<li class="lamp"><span class="dot unknown" aria-hidden="true"></span>`
    + `<span class="name">${esc(name)}</span><span class="state">Not checked</span></li>`).join("");
}

function splitModels(calls) {
  let light = 0, ultra = 0, other = 0;
  for (const c of calls) {
    const m = String(c.routed_model || c.model || "").toLowerCase();
    if (m.includes("light")) light += c.calls ?? 1;
    else if (m.includes("ultra")) ultra += c.calls ?? 1;
    else other += c.calls ?? 1;
  }
  return { light, ultra, other, total: light + ultra + other };
}

function statsFor(report) {
  const stats = report.explanation?.stats;
  let light = 0, ultra = 0, other = 0;
  if (stats?.models && typeof stats.models === "object") {
    for (const [name, n] of Object.entries(stats.models)) {
      const m = name.toLowerCase(), c = Number(n) || 0;
      if (m.includes("light")) light += c;
      else if (m.includes("ultra")) ultra += c;
      else other += c;
    }
  } else {
    const split = splitModels((report.model_trace || []).map((t) => ({ routed_model: t.routed_model || t.model, calls: 1 })));
    ({ light, ultra, other } = split);
  }
  const total = light + ultra + other;
  const receipts = Array.isArray(stats?.receipts)
    ? stats.receipts.length
    : new Set((report.model_trace || []).map((t) => t.receipt_id).filter(Boolean)).size;
  const dq = stats?.data_queries;
  const dataList = Array.isArray(dq) ? dq : report.data_trace || [];
  const zetaris = (dq && !Array.isArray(dq) ? dq.zetaris : undefined)
    ?? dataList.filter((q) => (q.backend || "").toLowerCase() === "zetaris").length;
  const dataTotal = (dq && !Array.isArray(dq) ? Object.values(dq).reduce((a, b) => a + (Number(b) || 0), 0) : undefined)
    ?? dataList.length;
  const verified = stats?.quotes_verified !== undefined
    ? `${stats.quotes_verified}/${stats.quotes_checked ?? "?"}`
    : `${(report.findings || []).flatMap((f) => f.evidence || []).filter((e) => e.verification === "verified").length} verified`;
  let duration = stats?.run_duration_s ?? stats?.duration_s;
  if (duration === undefined && report.events?.length) {
    const times = report.events.map((e) => Date.parse(e.at)).filter((t) => !Number.isNaN(t));
    if (times.length >= 2) duration = Math.max(0, (Math.max(...times) - Math.min(...times)) / 1000);
  }
  return [
    { label: "Nemotron calls", value: String(total || "—"),
      sub: total ? `${light} light · ${ultra} ultra` : "" },
    { label: "Nightshift receipts", value: String(receipts || "—"), sub: "" },
    { label: "Zetaris queries", value: String(dataTotal ? zetaris : "—"),
      sub: dataTotal ? `${dataTotal} data queries` : "" },
    { label: "Quotes verified", value: verified, sub: "" },
    { label: "Run time", value: duration === undefined ? "—" : `${Math.round(duration)} s`, sub: "" },
  ];
}

function renderTelemetry(report) {
  $("telemetry").innerHTML = statsFor(report).map((t) =>
    `<div class="tile"><dt>${esc(t.label)}</dt><dd>${esc(t.value)}${t.sub ? `<small>${esc(t.sub)}</small>` : ""}</dd></div>`).join("");
}

function renderTelemetryFallback() {
  $("telemetry").innerHTML = ["Nemotron calls", "Nightshift receipts", "Zetaris queries", "Quotes verified", "Run time"]
    .map((label) => `<div class="tile"><dt>${esc(label)}</dt><dd>—</dd></div>`).join("");
}

const GLOSSARY = {
  stop: "A decisive rule applies: the site cannot proceed as proposed.",
  "needs a fix": "Applies, but a condition, waiver or design change may resolve it.",
  noted: "Applies with limited impact; noted for the record.",
  clear: "No blocking rule at this layer.",
  "not checked": "Not yet evaluated.",
  "out of scope": "This layer does not model this site.",
  info: "Background information; it does not affect the verdict.",
  "grid/iso": "The power market operator for the site, for example PJM or ERCOT.",
  moratorium: "A temporary pause on accepting or approving data center projects.",
  "title v": "Clean Air Act permit for major sources of air pollution (100+ tons a year).",
  "sb 6": "Texas 2025 law adding large-load disclosure and curtailment rules for ERCOT.",
  estimate: "A projection from the remaining rules, not a new finding.",
};
const FIELD_LABELS = {
  effective: "Effective date", effective_date: "Effective date",
  duration: "Duration", duration_days: "Duration", scope: "Scope",
  exempt_if_permits_submitted: "Permits exemption",
};

function fieldLabel(field) {
  const key = String(field || "");
  if (FIELD_LABELS[key]) return FIELD_LABELS[key];
  return key.split("_").map((w) => w ? w.charAt(0).toUpperCase() + w.slice(1) : w).join(" ");
}
const LAYER_NAMES = {
  federal: "Federal", iso_rto: "Grid/ISO", state: "State", county: "County", city: "City",
};

function glossAttrs(term) {
  const key = String(term).toLowerCase();
  const def = GLOSSARY[key];
  if (!def) return "";
  return ` tabindex="0" data-def="${esc(def)}" aria-label="${esc(term)}: ${esc(def)}"`;
}

function gradeChip(grade) {
  const g = LAMP_WORD[grade] ? grade : "info";
  const word = LAMP_WORD[g] || "Info";
  return `<span class="tag"${glossAttrs(word)}>${esc(word)}</span>`;
}

function sourceLink(url, provenance) {
  const label = `${provenance || "source"}`;
  if (url && String(url).startsWith("http")) {
    return `<a href="${esc(url)}" target="_blank" rel="noopener">${esc(label)} source</a>`;
  }
  return esc(url || label);
}

function evItem(ev) {
  const field = ev.field === "other" ? "" : fieldLabel(ev.field);
  return `<div class="ev-item">“${esc(ev.quote)}”`
    + `<span class="meta"><span class="tag ${esc(ev.verification)}">${esc(ev.verification)}</span>`
    + `${field ? ` ${esc(field)} · ` : " "}${sourceLink(ev.url, ev.provenance)}</span></div>`;
}

function evidenceBlock(list) {
  const shown = (list || []).filter((e) => e.field !== "other");
  if (!shown.length) return `<p class="note">No cited evidence.</p>`;
  const first = shown.slice(0, 3).map(evItem).join("");
  if (shown.length <= 3) return first;
  return first + `<details><summary>Show ${shown.length - 3} more</summary>${shown.slice(3).map(evItem).join("")}</details>`;
}

function synthModel(report) {
  const s = (report.model_trace || []).find((t) => t.step === "synthesize");
  return s ? String(s.model || "").replace(/^nvidia\//, "") : "";
}

async function selectSite(name, fly) {
  state.selected = { kind: "showcase", id: name };
  setHash("showcase", name);
  dismissGuide();
  renderPortfolio();
  renderDots();
  let report = state.reports[name];
  if (!report) {
    try {
      report = await api(`/samples/${encodeURIComponent(name)}`);
      state.reports[name] = report;
    } catch {
      $("map-note").textContent = "Report unavailable. Check the server and retry.";
      $("map-note").hidden = false;
      return;
    }
  }
  let ctx = state.contexts[name];
  if (!ctx) {
    try {
      ctx = await api(`/samples/${encodeURIComponent(name)}/context`);
      state.contexts[name] = ctx;
    } catch { ctx = null; }
  }
  showReport(report, ctx, fly);
}

async function fetchLiveContext(id, report) {
  try {
    return await api(`/runs/${encodeURIComponent(id)}/context`);
  } catch { /* fall through to coordinate lookup */ }
  const j = report?.jurisdiction || {};
  if (j.lat !== undefined && j.lon !== undefined && j.county_fips) {
    try {
      return await api(`/context?lat=${j.lat}&lon=${j.lon}&county_fips=${encodeURIComponent(j.county_fips)}`);
    } catch { /* pin only */ }
  }
  return null;
}

async function selectLive(id, fly) {
  state.selected = { kind: "live", id };
  setHash("live", id);
  dismissGuide();
  renderPortfolio();
  renderDots();
  let report = state.reports[`live:${id}`];
  if (!report) {
    try {
      const s = await api(`/runs/${encodeURIComponent(id)}`);
      report = s.report;
      if (!report) throw new Error("run has no report yet");
      state.reports[`live:${id}`] = report;
    } catch {
      $("map-note").textContent = "Report unavailable. Check the server and retry.";
      $("map-note").hidden = false;
      return;
    }
  }
  let ctx = state.contexts[`live:${id}`];
  if (!ctx) {
    ctx = await fetchLiveContext(id, report);
    state.contexts[`live:${id}`] = ctx;
  }
  showReport(report, ctx, fly);
}

function projectLine(report) {
  const j = report.jurisdiction || {};
  const p = report.project || {};
  const asOf = report.explanation?.site?.as_of || "";
  const bits = [`${p.mw} MW`, `at ${p.address || j.matched_address || ""}`];
  if (j.county_name) bits.push(`${j.county_name}${j.state ? `, ${j.state}` : ""}`);
  if (j.iso) bits.push(j.iso);
  if (asOf) bits.push(`as of ${asOf}`);
  return bits.filter(Boolean).join(" · ");
}

function decisiveCard(d, report, demo) {
  const f = (report.findings || []).find((x) => x.rule_id === d.rule_id);
  return `<div class="decisive"${demo ? ` data-demo="decisive"` : ""}><h3>${esc(d.title)} ${gradeChip(d.grade)}</h3>`
    + `<p class="step"><span class="step-label">Source says</span></p>`
    + (d.fact?.quote ? evItem(d.fact) : `<p class="note">No verified quote.</p>`)
    + (d.more_sources ? `<p class="note">Plus ${esc(d.more_sources)} more source${d.more_sources === 1 ? "" : "s"}.</p>` : "")
    + `<p class="rule-line"><span class="step-label">Rule</span> ${esc(f?.reason || `${LAYER_NAMES[d.layer] || d.layer} rule`)}</p>`
    + `<p class="check-line"><span class="step-label">Check</span> ${esc(d.computation || "")}</p>`
    + `<p class="result-line"><span class="step-label">Result</span> ${esc(d.result || "")}</p></div>`;
}

function openQuestionsHtml(report) {
  const needs = report.needs_confirmation || [];
  const model = synthModel(report);
  const why = `<p class="adjudicator">Adjudicator${model ? ` (${esc(model)})` : ""}: ${esc(report.why || "")}</p>`;
  const open = needs.length
    ? `<h3>Open questions</h3><ul class="openq">${needs.map((o) =>
      `<li><strong>${esc(o.rule_id)}</strong> <span class="tag">${esc((o.type || "").replace(/_/g, " "))}</span><br>${esc(o.text)}${o.question ? `<div class="q">To resolve: ${esc(o.question)}</div>` : ""}</li>`).join("")}</ul>`
    : "";
  return why + open;
}

function flipsTable(rows) {
  return `<table class="flips-table"><thead><tr><th>Change</th><th>Effect</th><th>Estimated verdict</th></tr></thead><tbody>`
    + rows.map((f) => `<tr><td>${esc(f.change)}</td><td>${esc(f.effect)}</td>`
      + `<td><span class="tag estimate"${glossAttrs("estimate")}>estimate</span> ${esc(f.estimated_verdict)}</td></tr>`).join("")
    + `</tbody></table>`;
}

function renderFlipsTop(report) {
  const flips = (report.explanation || {}).flips || [];
  if (!flips.length) return `<div data-demo="flips"><h3>What would change it</h3><p class="note">No single change flips the answer.</p></div>`;
  return `<div data-demo="flips"><h3>What would change it</h3>${flipsTable(flips.slice(0, 2))}</div>`;
}

function renderFlipsRest(report) {
  const flips = (report.explanation || {}).flips || [];
  if (flips.length <= 2) return "";
  return `<h3>More changes that flip it</h3>${flipsTable(flips.slice(2))}`;
}

function renderCaught(report) {
  const exp = report.explanation || {};
  const list = exp.catches || [];
  const catches = list.map((c) =>
    `<div class="catch"><span class="actor">${esc(c.actor)} · ${esc((c.kind || "").replace(/_/g, " "))}</span>`
    + `<span class="note">round ${esc(c.round)}</span><p>${esc(c.text)}</p>`
    + (c.outcome ? `<p class="outcome">Outcome: ${esc(c.outcome)}</p>` : "") + `</div>`).join("");
  const sens = (exp.sensitivity || []).map((s) => {
    const rs = (s.readings || []).map((r) => {
      let host = "";
      try { host = r.url ? new URL(r.url).hostname : ""; } catch { /* keep empty */ }
      return `${r.value}${host ? ` (${host})` : ""}`;
    }).join(" vs ");
    return `<div class="sens-row">Sources disagree on ${esc(fieldLabel(s.field).toLowerCase())}: ${esc(rs)} — `
      + (s.holds ? "verdict holds under both readings" : "still open for your team") + `</div>`;
  }).join("");
  const head = `<h3>Double-checks (${list.length})</h3>`;
  if (!catches && !sens) return `${head}<p class="note">No double-checks and no source disagreements.</p>`;
  return head + catches
    + (sens ? `<h3>Source disagreements</h3>${sens}` : "");
}

function renderRules(report) {
  const order = ["federal", "iso_rto", "state", "county", "city"];
  const groups = new Map();
  for (const f of report.findings || []) {
    if (!groups.has(f.layer)) groups.set(f.layer, []);
    groups.get(f.layer).push(f);
  }
  const layers = [...groups.keys()].sort((a, b) => {
    const ai = order.indexOf(a), bi = order.indexOf(b);
    return (ai === -1 ? 99 : ai) - (bi === -1 ? 99 : bi);
  });
  const rows = layers.map((layer) => {
    const fs = groups.get(layer).map((f) =>
      `<div class="rule-row"><div class="rule-head">${gradeChip(f.grade)}`
      + `<span class="rule-title">${esc(f.title)}</span>`
      + `<span class="note">applies: ${esc(f.applies)}</span></div>`
      + `<p class="reason">${esc(f.reason || "")}</p>${evidenceBlock(f.evidence)}</div>`).join("");
    return `<h3>${esc(LAYER_NAMES[layer] || layer)}</h3>${fs}`;
  }).join("");
  const watch = (report.state_watch || []).map((w) =>
    `<div class="watch-row"><strong>${esc(w.title || w.policy_action_id || "State action")}</strong>`
    + `<span class="tag">dataset, not verified</span><br>${esc(w.key_provisions || w.status || "")}`
    + (w.primary_source_url ? ` · <a href="${esc(w.primary_source_url)}" target="_blank" rel="noopener">source</a>` : "")
    + `</div>`).join("");
  return (rows || `<p class="note">No rules in scope.</p>`)
    + (watch ? `<h3>State watch list</h3>${watch}` : "");
}

function humanizeEvent(e) {
  const d = e.detail;
  if (d === null || d === undefined) return `${e.role} ${e.action}`;
  switch (e.action) {
    case "resolved":
      return `Site resolved: ${d.county || ""}${d.county && d.state ? ", " : ""}${d.state || ""} · ${d.iso || ""}${d.place ? ` · ${d.place}` : " · unincorporated"}`;
    case "seeded":
      return `${(d.local || []).length} local rule(s), ${(d.curated || []).length} curated rule(s)`;
    case "tasks": case "targeted_tasks":
      return Array.isArray(d) ? d.map((t) => `${t.rule_id}: ${(t.questions || []).length} question(s)`).join("; ") : "no local rules";
    case "markovian_run":
      return `${d.rule} attempt ${d.attempt}: ${d.chunks} chunk(s), ${d.facts} fact(s), ${d.status}`;
    case "verified":
      return `${d.rule} attempt ${d.attempt}: ${d.checked - d.failed}/${d.checked} quotes verbatim`;
    case "retry_requested":
      return String(d).slice(0, 160);
    case "conflict":
      return `${d.rule} ${d.field}: ${d.value} vs ${d.other_primary ?? d.other_dataset}`;
    case "computed":
      return Array.isArray(d) ? d.map((f) => `${f.rule_id}: ${f.applies}`).join(", ") : String(d).slice(0, 160);
    case "draft":
      return `verdict ${d.verdict}`;
    case "objections":
      return d.length ? d.map((o) => `${o.type} on ${o.rule_id}`).join("; ") : "no objections";
    case "escalated":
      return `${d.length} objection(s) need confirmation`;
    default:
      return typeof d === "string" ? d : `${e.role} ${e.action}`;
  }
}

function feedHtml(events, started) {
  const items = (events || []).slice(-30);
  return `<ul class="feed">${items.map((e) => {
    let t = "";
    if (started && e.at) {
      const s = Math.round((Date.parse(e.at) - started) / 1000);
      if (!Number.isNaN(s) && s >= 0) t = `<span class="t">${s}s</span>`;
    }
    return `<li>${t}${esc(humanizeEvent(e))}</li>`;
  }).join("")}</ul>`;
}

function renderTrace(report) {
  const models = (report.model_trace || []).map((t) =>
    `<tr><td>${esc(t.role)}</td><td>${esc(String(t.model || "").replace(/^nvidia\//, ""))}${t.escalated_from ? " ↑" : ""}</td>`
    + `<td>${esc(t.receipt_id || "")}</td><td>${esc(t.latency_ms ?? "")}</td></tr>`).join("");
  const data = (report.data_trace || []).map((t) =>
    `<tr><td>${esc(t.backend)}</td><td>${esc(t.status)}</td><td>${esc(t.rows ?? t.error ?? "")}</td></tr>`).join("");
  const stats = report.explanation?.stats || {};
  const markovian = (report.markovian_runs || []).map((r) =>
    `<li>Run ${esc(String(r.id || "").slice(0, 8))}: ${esc(r.status || "done")}`
    + `${r.duration_ms !== undefined ? `, ${Math.round(r.duration_ms)} ms` : ""}`
    + `${r.total_tokens_saved ? `, ${esc(String(r.total_tokens_saved))} tokens saved` : ""}</li>`).join("");
  const claims = (report.findings || []).reduce((a, f) => a + (f.evidence || []).length, 0);
  return `<h3>How this was built</h3>`
    + `<h4>Model trace</h4>`
    + (models ? `<table class="flips-table"><thead><tr><th>Role</th><th>Model</th><th>Receipt</th><th>ms</th></tr></thead><tbody>${models}</tbody></table>` : `<p class="note">No model calls.</p>`)
    + `<h4>Data trace</h4>`
    + (data ? `<table class="flips-table"><thead><tr><th>Backend</th><th>Status</th><th>Rows</th></tr></thead><tbody>${data}</tbody></table>` : `<p class="note">No queries.</p>`)
    + `<h4>Markovian runs</h4>`
    + (markovian ? `<ul class="openq">${markovian}</ul><p class="note">${esc(String(stats.markovian_chunks ?? 0))} chunks, ${esc(String(stats.markovian_tokens_saved ?? 0))} tokens saved.</p>` : `<p class="note">No Markovian runs.</p>`)
    + `<h4>World Model</h4><p class="note">${claims} evidence claims across ${(report.findings || []).length} findings, ${(report.conflicts || []).length} conflict(s), ${(report.needs_confirmation || []).length} open objection(s).</p>`
    + `<p class="note">${esc(report.disclaimer || "")}</p>`;
}

function renderTimeline(report) {
  return `<h3>Agent timeline</h3>${feedHtml(report.events, null)}`;
}

function openChecked(section) {
  const box = $("disclosure-checked");
  if (box) box.open = true;
  const el = document.querySelector(`[data-demo="${section === "trace" ? "trace" : "catches"}"]`);
  el?.scrollIntoView({ block: "nearest", behavior: reduced() ? "auto" : "smooth" });
}

window.SiteWhy = {
  selectSite: (name) => selectSite(name),
  openChecked,
  current: () => state.currentReport,
  sites: () => state.rows.slice(),
};

function showErrorCard(title, message) {
  state.currentReport = null;
  state.currentCtx = null;
  hideGuide();
  $("report-empty").hidden = true;
  $("report-view").hidden = false;
  $("banner-dot").className = "dot unknown";
  $("banner-verdict").textContent = title;
  $("banner-headline").textContent = "";
  $("banner-project").textContent = "";
  $("print-site").textContent = "";
  $("print-disc").textContent = "";
  $("decisive-first").innerHTML = `<div class="decisive"><h3>${esc(title)}</h3>`
    + `<p class="result-line">${esc(message)}</p>`
    + `<p class="note">Try a different address, or pick a site from the portfolio.</p></div>`;
  $("flips-top").innerHTML = "";
  $("why-rest").innerHTML = "";
  $("checked-catches").innerHTML = "";
  $("checked-rules").innerHTML = "";
  $("checked-trace").innerHTML = "";
  renderTelemetryFallback();
  $("checked-timeline").innerHTML = "";
}

function showReport(report, ctx, fly) {
  state.currentReport = report;
  state.currentCtx = ctx || null;
  hideGuide();
  $("report-empty").hidden = true;
  $("report-view").hidden = false;
  $("banner-dot").className = `dot ${verdictClass(report.verdict)}`;
  $("banner-verdict").textContent = VERDICT_TEXT[report.verdict] || report.verdict;
  $("banner-headline").textContent = report.explanation?.headline || "";
  $("banner-project").textContent = projectLine(report);
  $("print-site").textContent = projectLine(report);
  $("print-disc").textContent = report.disclaimer || "";
  const decisive = (report.explanation || {}).decisive || [];
  $("decisive-first").innerHTML = decisive.length
    ? decisiveCard(decisive[0], report, true)
    : `<div class="decisive" data-demo="decisive"><p class="note">No decisive rules.</p></div>`;
  $("flips-top").innerHTML = renderFlipsTop(report);
  const rest = decisive.slice(1).map((d) => decisiveCard(d, report, false)).join("");
  $("why-rest").innerHTML = rest + renderFlipsRest(report) + openQuestionsHtml(report);
  $("checked-catches").innerHTML = renderCaught(report);
  $("checked-rules").innerHTML = `<h3>All rules</h3>` + renderRules(report);
  $("checked-trace").innerHTML = renderTrace(report);
  renderTelemetry(report);
  $("checked-timeline").innerHTML = renderTimeline(report);
  const chip = $("map-chip");
  chip.textContent = chipText(report);
  chip.hidden = false;
  renderOverlays(report, ctx);
  if (ctx?.google_maps_url) showMapFallbackCoords(report, ctx);
  renderLamps(report);
  if (!fly) state.map?.setView([report.jurisdiction.lat, report.jurisdiction.lon], 12, { animate: false });
  // Add-on modules (nav, palette, chain, lanes, settings) re-render from this event.
  document.dispatchEvent(new CustomEvent("sitewhy:report", { detail: { report, ctx: ctx || null } }));
}

function showMapFallbackCoords(report, ctx) {
  if (!$("map-fallback").hidden) showMapFallback(report.jurisdiction.lat, report.jurisdiction.lon, ctx.google_maps_url);
}

function showGuide(withBack) {
  $("guide").hidden = false;
  $("report-view").hidden = true;
  $("report-empty").hidden = true;
  $("guide-back").hidden = !(withBack && state.currentReport);
}

function hideGuide() {
  $("guide").hidden = true;
}

function runningRow(addressLabel, mw) {
  $("running-row")?.remove();
  $("live-details").hidden = false;
  const li = document.createElement("li");
  li.id = "running-row";
  li.innerHTML = `<div class="site-row running" aria-busy="true"><span class="dot major" aria-hidden="true"></span>`
    + `<span><span class="addr">Screening…</span><span class="meta">${esc(addressLabel)} · ${esc(mw)} MW</span></span></div>`;
  $("portfolio-live").prepend(li);
}

async function pollRun(runId, request) {
  const started = Date.now();
  let seen = 0, flown = false;
  for (;;) {
    const s = await api(`/runs/${runId}`);
    const events = s.events || [];
    if (events.length > seen) {
      seen = events.length;
      const resolved = events.find((e) => e.action === "resolved");
      if (resolved && !flown) {
        flown = true;
        const d = resolved.detail || {};
        if (d.lat !== undefined && d.lon !== undefined && state.map) {
          state.map.flyTo([d.lat, d.lon], 12, { duration: reduced() ? 0 : 1.2 });
        }
      }
      const ago = Math.round((Date.now() - started) / 1000);
      $("run-status").innerHTML = `Screening… ${ago} s · about 3–4 minutes${feedHtml(events, started)}`;
    }
    if (s.status === "done") return s.report;
    if (s.status === "error") throw new Error(s.error || "run failed");
    await new Promise((res) => setTimeout(res, 1500));
  }
}

async function submitRun(body, addressLabel) {
  $("run-btn").disabled = true;
  $("form-status").textContent = "Screening…";
  runningRow(addressLabel, body.mw);
  try {
    const res = await fetch("/runs", {
      method: "POST", headers: { "content-type": "application/json" }, body: JSON.stringify(body),
    });
    const data = await res.json();
    if (!res.ok) throw new Error(data.detail || res.statusText);
    const report = await pollRun(data.run_id, body);
    $("running-row")?.remove();
    $("form-status").textContent = "";
    $("run-status").innerHTML = "";
    state.reports[`live:${data.run_id}`] = report;
    const ctx = await fetchLiveContext(data.run_id, report);
    state.contexts[`live:${data.run_id}`] = ctx;
    state.selected = { kind: "live", id: data.run_id };
    setHash("live", data.run_id);
    dismissGuide();
    try {
      state.rows = await api("/portfolio");
    } catch { /* keep current rows; the report below is authoritative */ }
    renderPortfolio();
    showReport(report, ctx, true);
  } catch (err) {
    $("running-row")?.remove();
    const msg = err.message.includes("503") || err.message.includes("SAMPLE_MODE")
      ? "Live runs are off in sample mode — pick a site from the portfolio."
      : `Could not screen: ${err.message}`;
    $("form-status").textContent = msg;
    showErrorCard("Screening failed", msg);
  } finally { $("run-btn").disabled = false; $("run-status").textContent = ""; }
}

$("run-form").addEventListener("submit", (ev) => {
  ev.preventDefault();
  const permits = $("permits").value;
  submitRun({
    address: $("address").value, mw: Number($("mw").value),
    permits_submitted: permits === "" ? null : permits === "yes",
  }, $("address").value);
});

$("copy-link")?.addEventListener("click", async () => {
  const done = () => { $("copy-status").textContent = "Link copied."; };
  try {
    await navigator.clipboard.writeText(location.href);
    done();
  } catch {
    const ta = document.createElement("textarea");
    ta.value = location.href;
    document.body.appendChild(ta);
    ta.select();
    try { document.execCommand("copy"); done(); }
    catch { $("copy-status").textContent = "Copy this URL: " + location.href; }
    ta.remove();
  }
});

$("guide-glossary").innerHTML = Object.entries(GLOSSARY).map(([term, def]) =>
  `<dt>${esc(term)}</dt><dd>${esc(def)}</dd>`).join("");

$("guide-open")?.addEventListener("click", () => showGuide(true));
$("guide-back")?.addEventListener("click", () => {
  if (state.currentReport) { hideGuide(); $("report-view").hidden = false; }
});
$("guide-try")?.addEventListener("click", () => {
  dismissGuide();
  selectRow("showcase", "md-washington-county-unincorporated", true);
});

$("download-json")?.addEventListener("click", () => {
  if (!state.currentReport) return;
  const id = state.selected ? state.selected.id : "report";
  const blob = new Blob([JSON.stringify(state.currentReport, null, 1)], { type: "application/json" });
  const a = document.createElement("a");
  a.href = URL.createObjectURL(blob);
  a.download = `sitewhy-${id}.json`;
  document.body.appendChild(a);
  a.click();
  setTimeout(() => { URL.revokeObjectURL(a.href); a.remove(); }, 1000);
});

$("print-brief")?.addEventListener("click", () => window.print());

async function boot() {
  if (matchMedia("(max-width: 1179px)").matches) $("portfolio-details").removeAttribute("open");
  try {
    const status = await api("/status");
    state.sampleMode = !!status.sample_mode;
    if (status.sample_mode) {
      $("run-btn").disabled = true;
      $("screen-details").removeAttribute("open");
      $("form-status").textContent = "Live runs are off in sample mode — pick a site from the portfolio.";
    }
  } catch { /* status optional; submit surfaces errors */ }
  await bootPortfolio();
}

boot();
