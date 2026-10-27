/* SiteWhy agent-lanes module: who ran each step and on which model.
 * Own files: web/lanes.js + web/lanes.css. Never touches app.js/app.css/index.html.
 * Renders from the sitewhy:report event; on load uses window.SiteWhy.current(). */
(function () {
  "use strict";

  function esc(v) {
    return String(v ?? "").replace(/[&<>"']/g, function (c) {
      return { "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c];
    });
  }

  function shortModel(m) {
    return String(m || "").replace(/^nvidia\//, "") || "unknown model";
  }

  function isNemotron(m) {
    return /nemotron/i.test(String(m || ""));
  }

  function fmtInt(n) {
    return Number(n || 0).toLocaleString("en-US");
  }

  function flexGrow(t) {
    var ms = Math.round(Number(t.latency_ms));
    return Number.isFinite(ms) && ms > 0 ? ms : 0;
  }

  function summaryHtml(trace) {
    var nemo = 0, toks = 0, rcpt = 0;
    for (var i = 0; i < trace.length; i++) {
      if (isNemotron(trace[i].model)) nemo++;
      toks += Number(trace[i].total_tokens) || 0;
      if (trace[i].receipt_id) rcpt++;
    }
    return '<p class="lanes-summary"><strong>' + trace.length + "</strong> model calls · <strong>"
      + nemo + "</strong> on NVIDIA Nemotron · <strong>" + fmtInt(toks) + "</strong> total tokens · <strong>"
      + rcpt + "</strong> Nightshift receipts</p>";
  }

  function blockTitle(t) {
    return [t.provider || "unknown provider",
      fmtInt(t.total_tokens) + " tokens",
      (t.latency_ms ?? "—") + " ms",
      t.receipt_id ? "receipt " + t.receipt_id : "no receipt"].join(" · ");
  }

  function blockHtml(t) {
    var badges = "";
    if (t.cached) badges += ' <span class="lane-badge">cached</span>';
    if (t.escalated_from) badges += ' <span class="lane-badge">escalated</span>';
    return '<span class="lane-block" style="flex:' + flexGrow(t) + ' 0 120px" title="' + esc(blockTitle(t)) + '">'
      + '<span class="lane-step">' + esc(t.step || "step") + "</span>"
      + '<span class="lane-model">' + esc(shortModel(t.model)) + "</span>" + badges + "</span>";
  }

  function catchesByActor(report) {
    var map = {};
    var list = (report.explanation || {}).catches || [];
    for (var i = 0; i < list.length; i++) {
      var actor = list[i].actor || "unknown";
      if (!map[actor]) map[actor] = [];
      map[actor].push(list[i]);
    }
    return map;
  }

  function flagHtml(catches) {
    if (!catches || !catches.length) return "";
    var kinds = catches.map(function (c) { return c.kind || "catch"; }).join(", ");
    return ' <span class="lane-flag" title="' + esc(catches.length + " reviewer catch(es): " + kinds) + '">⚑</span>';
  }

  function rowsHtml(trace, report) {
    var order = [];
    var seen = {};
    var i;
    for (i = 0; i < trace.length; i++) {
      var role = trace[i].role || "unknown";
      if (!seen[role]) { seen[role] = []; order.push(role); }
      seen[role].push(trace[i]);
    }
    if (!order.length) return '<p class="note">No model calls.</p>';
    var byActor = catchesByActor(report);
    return order.map(function (role) {
      return '<div class="lane-row"><span class="lane-role">' + esc(role) + flagHtml(byActor[role]) + "</span>"
        + '<span class="lane-blocks">' + seen[role].map(blockHtml).join("") + "</span></div>";
    }).join("");
  }

  function dataHtml(report) {
    var rows = report.data_trace || [];
    var cells = rows.length ? rows.map(function (q) {
      return '<span class="lane-block lane-data-cell">' + esc(q.backend || "unknown")
        + " · " + esc(q.status || "—") + " · " + esc(q.rows ?? q.error ?? "—") + "</span>";
    }).join("") : '<span class="note">No queries.</span>';
    return '<div class="lane-row lane-data"><span class="lane-role">Data</span>'
      + '<span class="lane-blocks">' + cells + "</span></div>";
  }

  function render(report) {
    document.getElementById("agent-lanes")?.remove();
    if (!report) return;
    var layers = document.querySelector("section.layers");
    if (!layers) return;
    var trace = Array.isArray(report.model_trace) ? report.model_trace : [];
    var sec = document.createElement("section");
    sec.id = "agent-lanes";
    sec.setAttribute("data-demo", "lanes");
    sec.setAttribute("aria-labelledby", "agent-lanes-h");
    sec.innerHTML = '<h2 id="agent-lanes-h">Who did the work</h2>'
      + summaryHtml(trace)
      + '<div class="lanes-scroll">' + rowsHtml(trace, report) + dataHtml(report) + "</div>";
    layers.after(sec);
  }

  document.addEventListener("sitewhy:report", function (e) {
    render(e.detail && e.detail.report);
  });

  if (window.SiteWhy && typeof window.SiteWhy.current === "function") {
    try {
      var cur = window.SiteWhy.current();
      if (cur) render(cur);
    } catch (err) { /* report arrives via event */ }
  }
})();
