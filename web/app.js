const $ = (id) => document.getElementById(id);
const esc = (v) => String(v ?? "").replace(/[&<>"']/g, (c) => ({
  "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;",
}[c]));
const VERDICT_TEXT = {
  "no-go": "No-go", go: "Go", conditional: "Conditional",
  needs_confirmation: "Needs confirmation",
};
const LAMPS = [
  ["federal", "Federal"], ["iso_rto", "Grid/ISO"], ["state", "State"],
  ["county", "County"], ["city", "City"],
];
const LAMP_WORD = {
  fatal: "Fatal", major: "Major", minor: "Minor", clear: "Clear",
  unknown: "Unknown", not_modelled: "Not modelled",
};

async function api(path, opts) {
  const res = await fetch(path, opts);
  if (!res.ok) {
    const detail = await res.text();
    throw new Error(`Request failed (${res.status}): ${detail.slice(0, 200)}`);
  }
  return res.json();
}

function applyTheme() {
  const root = document.documentElement;
  const light = root.dataset.theme === "light" ||
    (!root.dataset.theme && matchMedia("(prefers-color-scheme: light)").matches);
  const btn = $("theme-toggle");
  btn.setAttribute("aria-pressed", String(!light));
  btn.textContent = light ? "Use dark theme" : "Use light theme";
}
$("theme-toggle").addEventListener("click", () => {
  const root = document.documentElement;
  const light = root.dataset.theme === "light" ||
    (!root.dataset.theme && matchMedia("(prefers-color-scheme: light)").matches);
  root.dataset.theme = light ? "dark" : "light";
  applyTheme();
});
applyTheme();

const state = { rows: [], reports: {}, contexts: {}, selected: null, dots: {}, map: null, layers: null };

function shortAddress(address) {
  return String(address || "").split(",")[0].trim();
}

function renderPortfolio() {
  const ul = $("portfolio");
  ul.innerHTML = state.rows.map((r) => {
    const rep = state.reports[r.name];
    const county = r.county || rep?.jurisdiction?.county_name || "";
    const current = state.selected === r.name ? "true" : "false";
    return `<li><button type="button" class="site-row" data-name="${esc(r.name)}" aria-current="${current}">`
      + `<span class="dot ${esc(r.verdict)}" aria-hidden="true"></span>`
      + `<span><span class="addr">${esc(shortAddress(r.address))}</span>`
      + `<span class="meta">${esc(r.mw)} MW${county ? ` · ${esc(county)}` : ""} · ${esc(VERDICT_TEXT[r.verdict] || r.verdict)}</span></span>`
      + `</button></li>`;
  }).join("");
  ul.querySelectorAll("button").forEach((b) =>
    b.addEventListener("click", () => selectSite(b.dataset.name, true)));
}

async function boot() {
  if (matchMedia("(max-width: 1179px)").matches) $("portfolio-details").removeAttribute("open");
  let rows;
  try {
    rows = await api("/samples");
  } catch (err) {
    $("portfolio").innerHTML = `<li class="note">Could not load samples. Check the server and reload.</li>`;
    renderLampsFallback();
    renderTelemetryFallback();
    return;
  }
  state.rows = rows;
  renderPortfolio();
  await Promise.allSettled(rows.map(async (r) => {
    try {
      const rep = await api(`/samples/${encodeURIComponent(r.name)}`);
      state.reports[r.name] = rep;
      if (rep.jurisdiction?.county_name && !r.county) r.county = rep.jurisdiction.county_name;
      if (rep.jurisdiction && (r.lat === undefined || r.lon === undefined)) {
        r.lat = rep.jurisdiction.lat;
        r.lon = rep.jurisdiction.lon;
      }
      if (!r.headline && rep.explanation?.headline) r.headline = rep.explanation.headline;
    } catch { /* row keeps skeleton data; selection retries */ }
  }));
  renderPortfolio();
  if (rows.length) await selectSite(rows[0].name, false);
}

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
  const bases = document.createElement("fieldset");
  bases.className = "basemaps";
  bases.innerHTML = `<legend>Basemap</legend>`;
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
      state.layers.county = L_.geoJSON(ctx.county, {
        style: { color: "#b7d8c7", weight: 2, fillColor: "#b7d8c7", fillOpacity: 0.08 },
      }).addTo(state.map);
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
  for (const r of state.rows) {
    if (r.name === state.selected || r.lat === undefined) continue;
    const dot = L_.marker([r.lat, r.lon], {
      icon: L_.divIcon({ className: "", html: `<div class="site-dot ${verdictClass(r.verdict)}" aria-hidden="true"><span></span></div>`, iconSize: [44, 44], iconAnchor: [22, 22] }),
      title: r.address, alt: r.address,
    });
    dot.on("click", () => selectSite(r.name, true));
    dot.addTo(state.map);
    state.dots[r.name] = dot;
  }
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
    return `<li class="lamp" tabindex="0" aria-label="${esc(name)}: ${esc(LAMP_WORD[lamp])}. ${esc(summary)}">`
      + `<span class="dot ${esc(lamp)}" aria-hidden="true"></span>`
      + `<span><span class="name">${esc(name)}</span><span class="state">${esc(LAMP_WORD[lamp])}</span>`
      + `<span class="summary">${esc(summary)}</span></span></li>`;
  }).join("");
}

function renderLampsFallback() {
  $("lamps").innerHTML = LAMPS.map(([, name]) =>
    `<li class="lamp"><span class="dot unknown" aria-hidden="true"></span>`
    + `<span><span class="name">${esc(name)}</span><span class="state">Unknown</span></span></li>`).join("");
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

function updateScrollCue() {
  const board = document.querySelector(".statusboard");
  const cue = $("scroll-cue");
  if (!board || !cue) return;
  const scrollable = board.scrollHeight > board.clientHeight + 8;
  const atBottom = board.scrollTop + board.clientHeight >= board.scrollHeight - 8;
  cue.hidden = !(scrollable && !atBottom);
}

function renderTelemetry(report) {
  $("telemetry").innerHTML = statsFor(report).map((t) =>
    `<div class="tile"><dt>${esc(t.label)}</dt><dd>${esc(t.value)}${t.sub ? `<small>${esc(t.sub)}</small>` : ""}</dd></div>`).join("");
}

function renderTelemetryFallback() {
  $("telemetry").innerHTML = ["Nemotron calls", "Nightshift receipts", "Zetaris queries", "Quotes verified", "Run time"]
    .map((label) => `<div class="tile"><dt>${esc(label)}</dt><dd>—</dd></div>`).join("");
}

async function selectSite(name, fly) {
  const row = state.rows.find((r) => r.name === name);
  if (!row) return;
  state.selected = name;
  renderPortfolio();
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
  const chip = $("map-chip");
  chip.textContent = chipText(report);
  chip.hidden = false;
  renderOverlays(report, ctx);
  if (ctx?.google_maps_url) showMapFallbackCoords(report, ctx);
  renderLamps(report);
  renderTelemetry(report);
  updateScrollCue();
  if (!fly) state.map?.setView([report.jurisdiction.lat, report.jurisdiction.lon], 12, { animate: false });
}

function showMapFallbackCoords(report, ctx) {
  if (!$("map-fallback").hidden) showMapFallback(report.jurisdiction.lat, report.jurisdiction.lon, ctx.google_maps_url);
}

async function pollRun(runId) {
  const started = Date.now();
  for (;;) {
    const s = await api(`/runs/${runId}`);
    if (s.status === "done") return s.report;
    if (s.status === "error") throw new Error(s.error || "run failed");
    $("run-status").textContent = `Screening… ${Math.round((Date.now() - started) / 1000)} s`;
    await new Promise((res) => setTimeout(res, 1500));
  }
}

$("run-form").addEventListener("submit", async (ev) => {
  ev.preventDefault();
  const permits = $("permits").value;
  const body = {
    address: $("address").value, mw: Number($("mw").value),
    permits_submitted: permits === "" ? null : permits === "yes",
  };
  $("run-btn").disabled = true;
  $("form-status").textContent = "Screening…";
  try {
    const res = await fetch("/runs", {
      method: "POST", headers: { "content-type": "application/json" }, body: JSON.stringify(body),
    });
    const data = await res.json();
    if (!res.ok) throw new Error(data.detail || res.statusText);
    const report = await pollRun(data.run_id);
    $("form-status").textContent = "";
    $("run-status").textContent = `Done: ${VERDICT_TEXT[report.verdict] || report.verdict} — the full report lands here in the next step.`;
    state.reports[`live:${data.run_id}`] = report;
    let ctx = null;
    try { ctx = await api(`/runs/${data.run_id}/context`); } catch { /* pin only */ }
    const chip = $("map-chip");
    chip.textContent = chipText(report);
    chip.hidden = false;
    renderOverlays(report, ctx);
    renderLamps(report);
    renderTelemetry(report);
    updateScrollCue();
  } catch (err) {
    $("form-status").textContent = err.message.includes("503") || err.message.includes("SAMPLE_MODE")
      ? "Live runs are off in sample mode — pick a site from the portfolio."
      : `Could not screen: ${err.message}`;
  } finally { $("run-btn").disabled = false; $("run-status").textContent = ""; }
});

document.querySelector(".statusboard")?.addEventListener("scroll", updateScrollCue, { passive: true });
addEventListener("resize", updateScrollCue);

boot();
