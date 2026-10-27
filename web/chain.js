/* SiteWhy why-chain module (Todo 9): verdict <- decisive rule <- verified quote <- source. */
(() => {
  "use strict";

  var VERDICT_WORD = {
    "no-go": "No-go",
    go: "Go",
    conditional: "Conditional",
    needs_confirmation: "Needs one more check",
  };
  var LAYER_NAME = {
    federal: "Federal",
    iso_rto: "Grid/ISO",
    state: "State",
    county: "County",
    city: "City",
  };
  var GRADE_WORD = {
    fatal: "Stop",
    major: "Needs a fix",
    minor: "Noted",
    clear: "Clear",
    unknown: "Not checked",
    not_modelled: "Out of scope",
  };

  function esc(v) {
    return String(v ?? "").replace(/[&<>"']/g, (c) => ({
      "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;",
    }[c]));
  }
  function clip(s, n) {
    var t = String(s || "").trim().replace(/\s+/g, " ");
    return t.length > n ? t.slice(0, n - 1) + "…" : t;
  }
  function hostname(url) {
    try {
      return new URL(String(url)).hostname;
    } catch (e) {
      return "";
    }
  }
  function verdictClass(v) {
    return v === "no-go" || v === "conditional" || v === "go" ? v : "needs_confirmation";
  }
  function demoRunning() {
    return document.body.classList.contains("demo-running");
  }
  function reduced() {
    return window.matchMedia("(prefers-reduced-motion: reduce)").matches;
  }

  function pickEvidence(report, d) {
    var findings = report.findings || [];
    var f = null;
    for (var i = 0; i < findings.length; i++) {
      if (findings[i] && findings[i].rule_id === d.rule_id) { f = findings[i]; break; }
    }
    var pool = (f && f.evidence) || [];
    for (var j = 0; j < pool.length; j++) {
      if (pool[j] && pool[j].verification === "verified") return pool[j];
    }
    if (pool.length) return pool[0];
    if (d.fact && d.fact.quote) return d.fact;
    return null;
  }

  function verdictCard(report) {
    if (!report.verdict) {
      return '<div class="chain-card" tabindex="0" data-chain="verdict">'
        + '<p class="chain-label">Verdict</p><p class="chain-missing">—</p>'
        + '<p class="chain-why">No verdict in this report.</p></div>';
    }
    var word = VERDICT_WORD[report.verdict] || String(report.verdict);
    return '<div class="chain-card" tabindex="0" data-chain="verdict">'
      + '<p class="chain-label">Verdict</p>'
      + '<p class="chain-verdict"><span class="dot ' + esc(verdictClass(report.verdict))
      + '" aria-hidden="true"></span><span>' + esc(word) + "</span></p></div>";
  }

  function ruleCard(d) {
    if (!d) {
      return '<div class="chain-card" tabindex="0" data-chain="rule">'
        + '<p class="chain-label">Decisive rule</p><p class="chain-missing">—</p>'
        + '<p class="chain-why">No decisive rule in this report.</p></div>';
    }
    var layer = LAYER_NAME[d.layer] || String(d.layer || "Rule");
    var grade = GRADE_WORD[d.grade] || String(d.grade || "");
    var meta = layer + (grade ? " · " + grade : "");
    return '<div class="chain-card" tabindex="0" data-chain="rule">'
      + '<p class="chain-label">Decisive rule</p>'
      + '<p class="chain-title">' + esc(d.title || "Untitled rule") + "</p>"
      + '<p class="chain-meta">' + esc(meta) + "</p></div>";
  }

  function quoteCard(ev) {
    if (!ev || !ev.quote) {
      return '<div class="chain-card" tabindex="0" data-chain="quote">'
        + '<p class="chain-label">Source says</p><p class="chain-missing">—</p>'
        + '<p class="chain-why">No quote for this rule.</p></div>';
    }
    var meta = ev.verification ? String(ev.verification) : "";
    var label = ev.verification === "verified" ? "Verified quote" : "Source says (unverified)";
    return '<div class="chain-card" tabindex="0" data-chain="quote">'
      + '<p class="chain-label">' + label + '</p>'
      + '<p class="chain-quote">“' + esc(clip(ev.quote, 160)) + "”</p>"
      + (meta ? '<p class="chain-meta">' + esc(meta) + "</p>" : "") + "</div>";
  }

  function sourceCard(ev) {
    if (!ev || !/^https?:\/\//i.test(String(ev.url || ""))) {
      return '<div class="chain-card" tabindex="0" data-chain="source">'
        + '<p class="chain-label">Source</p><p class="chain-missing">—</p>'
        + '<p class="chain-why">No source link for this quote.</p></div>';
    }
    var host = hostname(ev.url) || clip(ev.url, 40);
    var prov = ev.provenance ? String(ev.provenance) : "";
    if (prov === "primary" || prov === "county_source") prov = "county source";
    return '<div class="chain-card" tabindex="0" data-chain="source">'
      + '<p class="chain-label">Source</p>'
      + '<p class="chain-src"><a href="' + esc(ev.url) + '" target="_blank" rel="noopener">'
      + esc(host) + "</a></p>"
      + (prov ? '<p class="chain-meta">' + esc(prov) + "</p>" : "") + "</div>";
  }

  function targetFor(kind, info) {
    if (kind === "verdict") return document.getElementById("banner");
    if (kind === "rule") return document.querySelector("#decisive-first .decisive");
    if (kind === "quote") {
      var want = String(info.layer || "").toLowerCase();
      if (want === "iso_rto") want = "grid/iso";
      var lamps = document.querySelectorAll("#lamps .lamp");
      for (var i = 0; i < lamps.length; i++) {
        var nm = lamps[i].querySelector(".name");
        if (nm && nm.textContent.trim().toLowerCase() === want) return lamps[i];
      }
      return null;
    }
    if (kind === "source") {
      var links = document.querySelectorAll("#decisive-first .decisive a[href]");
      if (info.url) {
        for (var j = 0; j < links.length; j++) {
          if (links[j].getAttribute("href") === info.url) return links[j];
        }
        var all = document.querySelectorAll("#report-view a[href]");
        for (var k = 0; k < all.length; k++) {
          if (all[k].getAttribute("href") === info.url) return all[k];
        }
      }
      return links[0] || null;
    }
    return null;
  }

  function clearHot() {
    var hots = document.querySelectorAll(".chain-hot");
    for (var i = 0; i < hots.length; i++) hots[i].classList.remove("chain-hot");
  }

  function bindCards(sec, info) {
    var cards = sec.querySelectorAll(".chain-card");
    for (var i = 0; i < cards.length; i++) {
      (function (card) {
        var kind = card.getAttribute("data-chain");
        card.addEventListener("mouseenter", () => {
          var t = targetFor(kind, info);
          clearHot();
          if (t) t.classList.add("chain-hot");
        });
        card.addEventListener("mouseleave", clearHot);
        card.addEventListener("focus", () => {
          var t = targetFor(kind, info);
          clearHot();
          if (t) t.classList.add("chain-hot");
        });
        card.addEventListener("blur", clearHot);
      })(cards[i]);
    }
    var more = sec.querySelector(".chain-more");
    if (more) {
      more.addEventListener("click", () => {
        if (demoRunning()) return;
        var box = document.getElementById("disclosure-why");
        if (!box) return;
        box.open = true;
        box.scrollIntoView({ block: "nearest", behavior: reduced() ? "auto" : "smooth" });
      });
    }
  }

  function render(report) {
    var old = document.getElementById("why-chain");
    if (old) old.remove();
    clearHot();
    var anchor = document.querySelector(".answer-first");
    if (!anchor || !report) return;
    var decisive = (report.explanation || {}).decisive || [];
    var d0 = decisive[0] || null;
    var ev = d0 ? pickEvidence(report, d0) : null;
    var info = { layer: d0 && d0.layer, url: ev && ev.url };
    var extra = decisive.length - 1;
    var html = '<div class="chain-row">'
      + verdictCard(report)
      + '<span class="chain-arrow" aria-hidden="true"></span>'
      + ruleCard(d0)
      + '<span class="chain-arrow" aria-hidden="true"></span>'
      + quoteCard(ev)
      + '<span class="chain-arrow" aria-hidden="true"></span>'
      + sourceCard(ev)
      + "</div>";
    if (extra > 0) {
      html += '<button type="button" class="chain-more">+' + extra
        + " more rule" + (extra === 1 ? "" : "s") + "</button>";
    }
    var sec = document.createElement("section");
    sec.id = "why-chain";
    sec.setAttribute("data-demo", "chain");
    sec.setAttribute("aria-label", "Why this verdict");
    sec.innerHTML = html;
    anchor.after(sec);
    bindCards(sec, info);
  }

  function observeErrorState() {
    var anchor = document.querySelector("#decisive-first");
    if (!anchor || typeof MutationObserver === "undefined") return;
    var mo = new MutationObserver(() => {
      try {
        var cur = window.SiteWhy && window.SiteWhy.current();
        if (cur == null) {
          var old = document.getElementById("why-chain");
          if (old) old.remove();
          clearHot();
        }
      } catch (e) { /* private mode or early boot */ }
    });
    mo.observe(anchor, { childList: true });
  }

  document.addEventListener("sitewhy:report", (e) => {
    render(e && e.detail ? e.detail.report : null);
  });

  function init() {
    try {
      var cur = window.SiteWhy && window.SiteWhy.current();
      if (cur) render(cur);
    } catch (e) { /* keep page usable when storage is blocked */ }
    observeErrorState();
  }
  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", init);
  } else {
    init();
  }
})();
