/* SiteWhy command palette (Todo 7): Ctrl+K search across sites, rules and actions. */
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
  var SECTIONS = [
    ["Verdict", "#banner", false],
    ["The rule", "#decisive-first", false],
    ["Why chain", "#why-chain", false],
    ["Map", ".map-wrap", false],
    ["Layers", ".layers", false],
    ["Agents", "#agent-lanes", false],
    ["Why", "#disclosure-why", true],
    ["How it was checked", "#disclosure-checked", true],
  ];
  var GROUP_ORDER = ["Sites", "Sections", "Rules", "Evidence", "Terms", "Actions"];
  var MAX_RESULTS = 40;

  function esc(v) {
    return String(v ?? "").replace(/[&<>"']/g, (c) => ({
      "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;",
    }[c]));
  }
  function clip(s, n) {
    var t = String(s || "").trim().replace(/\s+/g, " ");
    return t.length > n ? t.slice(0, n - 1) + "…" : t;
  }
  function shortAddr(address) {
    return String(address || "").split(",")[0].trim();
  }
  function verdictWord(v) {
    return VERDICT_WORD[v] || String(v || "");
  }
  function demoRunning() {
    return document.body.classList.contains("demo-running");
  }
  function reduced() {
    return window.matchMedia("(prefers-reduced-motion: reduce)").matches;
  }
  function scrollToEl(el) {
    if (!el) return;
    el.scrollIntoView({ block: "start", behavior: reduced() ? "auto" : "smooth" });
  }
  function openDisclosure(sel) {
    var box = typeof sel === "string" ? document.querySelector(sel) : sel;
    if (box && box.tagName === "DETAILS") box.open = true;
    return box;
  }

  function fuzzy(target, q) {
    var t = String(target).toLowerCase();
    var idx = [];
    var p = 0;
    for (var i = 0; i < q.length; i++) {
      var at = t.indexOf(q[i], p);
      if (at === -1) return null;
      idx.push(at);
      p = at + 1;
    }
    var score = 1000 - (idx[idx.length - 1] - idx[0]) * 2 - idx[0] * 2;
    if (idx[0] === 0) score += 200;
    for (var j = 0; j < idx.length; j++) {
      var prev = idx[j] === 0 ? " " : t[idx[j] - 1];
      if (/[^a-z0-9]/.test(prev)) score += 40;
    }
    return { score: score, idx: idx };
  }

  function highlight(text, idx) {
    var s = String(text);
    var marks = {};
    for (var i = 0; i < idx.length; i++) marks[idx[i]] = true;
    var out = "";
    for (var j = 0; j < s.length; j++) {
      out += marks[j] ? "<mark>" + esc(s[j]) + "</mark>" : esc(s[j]);
    }
    return out;
  }

  var scrim = null;
  var input = null;
  var list = null;
  var opener = null;
  var flat = [];

  function ensureDom() {
    if (scrim) return;
    scrim = document.createElement("div");
    scrim.className = "palette-scrim";
    scrim.hidden = true;
    scrim.innerHTML = '<div class="palette-modal" role="dialog" aria-modal="true" aria-label="Search">'
      + '<input class="palette-input" type="text" role="combobox" aria-expanded="true"'
      + ' aria-controls="palette-list" aria-autocomplete="list" autocomplete="off" spellcheck="false"'
      + ' placeholder="Search sites, rules, actions…" aria-label="Search sites, rules and actions">'
      + '<div class="palette-list" role="listbox" id="palette-list" aria-label="Results"></div>'
      + "</div>";
    document.body.appendChild(scrim);
    input = scrim.querySelector(".palette-input");
    list = scrim.querySelector(".palette-list");
    scrim.addEventListener("mousedown", (e) => {
      if (e.target === scrim) close();
    });
    input.addEventListener("input", () => render(input.value));
    input.addEventListener("keydown", (e) => {
      if (e.key === "ArrowDown" || e.key === "ArrowUp" || e.key === "Home"
        || e.key === "End" || e.key === "Enter" || e.key === "Escape" || e.key === "Tab") {
        e.stopPropagation();
      }
      if (e.key === "ArrowDown") { e.preventDefault(); move(1); }
      else if (e.key === "ArrowUp") { e.preventDefault(); move(-1); }
      else if (e.key === "Home") { e.preventDefault(); setActive(0); }
      else if (e.key === "End") { e.preventDefault(); setActive(flat.length - 1); }
      else if (e.key === "Enter") { e.preventDefault(); activate(); }
      else if (e.key === "Escape") { e.preventDefault(); close(); }
      else if (e.key === "Tab") { e.preventDefault(); input.focus(); }
    });
  }

  function ensureRailButton() {
    if (document.querySelector(".palette-open")) return;
    var t = document.querySelector(".rail-tools");
    if (!t) {
      t = document.createElement("div");
      t.className = "rail-tools";
      (document.querySelector(".rail .brand") || document.querySelector(".rail")).after(t);
    }
    var b = document.createElement("button");
    b.type = "button";
    b.className = "palette-open";
    b.innerHTML = 'Search <kbd>Ctrl K</kbd>';
    b.setAttribute("aria-label", "Search (Control K)");
    b.addEventListener("click", () => open());
    t.appendChild(b);
  }

  function siteLabel(r) {
    return shortAddr(r.address) || String(r.id || r.name || "Site");
  }
  function siteSub(r) {
    var bits = [];
    if (r.mw) bits.push(r.mw + " MW");
    if (r.county) bits.push(String(r.county));
    if (r.verdict) bits.push(verdictWord(r.verdict));
    return bits.join(" · ");
  }

  function buildItems(query) {
    var q = String(query || "").trim().toLowerCase();
    var groups = { Sites: [], Sections: [], Rules: [], Evidence: [], Terms: [], Actions: [] };
    var W = window.SiteWhy || {};
    var report = null;
    try { report = W.current ? W.current() : null; } catch (e) { report = null; }
    var viewHidden = true;
    var rv = document.getElementById("report-view");
    if (rv) viewHidden = rv.hidden;

    var rows = [];
    try { rows = W.sites ? W.sites() : []; } catch (e) { rows = []; }
    rows.forEach((r) => {
      if (!r || (r.kind && r.kind !== "showcase")) return;
      var id = r.id || r.name;
      if (!id) return;
      var label = siteLabel(r);
      var sub = siteSub(r);
      groups.Sites.push({
        group: "Sites", label: label, text: label + " " + sub + " " + id, labelHtml: null,
        sub: sub, run: () => { W.selectSite(id); },
      });
    });

    var clickAction = (id) => () => {
      var el = document.getElementById(id);
      if (el) el.click();
    };
    var actionDefs = [
      ["Start tour", "open the guided tour", "demo-roll", clickAction("demo-roll")],
      ["Print brief", "print this report", "print-brief", clickAction("print-brief")],
      ["Copy link", "copy a link to this report", "copy-link", clickAction("copy-link")],
      ["Download JSON", "download the report data", "download-json", clickAction("download-json")],
      ["Open agent trace", "show the model trace", null, () => { W.openChecked("trace"); }],
    ];
    actionDefs.forEach((a) => {
      if (a[2] && !document.getElementById(a[2])) return;
      groups.Actions.push({ group: "Actions", label: a[0], text: a[0] + " " + a[1], labelHtml: null, sub: a[1], run: a[3] });
    });

    if (!viewHidden) {
      SECTIONS.forEach((s) => {
        var el = document.querySelector(s[1]);
        if (!el) return;
        (function (title, sel, isDetails) {
          groups.Sections.push({
            group: "Sections", label: title, text: title, labelHtml: null, sub: "Go to section",
            run: () => {
              var target = document.querySelector(sel);
              if (!target) return;
              if (isDetails) openDisclosure(target);
              scrollToEl(target);
            },
          });
        })(s[0], s[1], s[2]);
      });
    }

    if (report) {
      (report.findings || []).forEach((f) => {
        if (!f) return;
        var layer = LAYER_NAME[f.layer] || String(f.layer || "");
        (function (finding, layerName) {
          groups.Rules.push({
            group: "Rules", label: finding.title,
            text: finding.title + " " + (finding.rule_id || "") + " " + layerName,
            labelHtml: null, sub: [finding.rule_id, layerName].filter(Boolean).join(" · "),
            run: () => scrollToRule(finding.title),
          });
          (finding.evidence || []).forEach((ev) => {
            if (!ev || !ev.quote) return;
            (function (quote, title) {
              groups.Evidence.push({
                group: "Evidence", label: clip(quote, 90), text: quote, labelHtml: null,
                sub: "In: " + title, run: () => scrollToRule(title),
              });
            })(ev.quote, finding.title);
          });
        })(f, layer);
      });
    }

    var legendItems = document.querySelectorAll("#legend li");
    for (var i = 0; i < legendItems.length; i++) {
      var txt = String(legendItems[i].textContent || "").trim().replace(/\s+/g, " ");
      if (!txt) continue;
      (function (term) {
        groups.Terms.push({
          group: "Terms", label: term, text: term, labelHtml: null, sub: "Status key",
          run: () => {
            var box = openDisclosure("#legend-details");
            scrollToEl(box || document.getElementById("legend"));
          },
        });
      })(txt);
    }

    var out = [];
    if (!q) {
      ["Actions", "Sites"].forEach((g) => {
        groups[g].forEach((it) => {
          it.labelHtml = esc(it.label);
          out.push(it);
        });
      });
      return out;
    }
    var scored = [];
    GROUP_ORDER.forEach((g) => {
      groups[g].forEach((it) => {
        var m = fuzzy(it.text, q);
        if (m) scored.push({ it: it, score: m.score });
      });
    });
    scored.sort((a, b) => b.score - a.score);
    var picked = {};
    scored.slice(0, MAX_RESULTS).forEach((s) => {
      var it = s.it;
      var ml = fuzzy(it.label, q);
      it.labelHtml = ml ? highlight(it.label, ml.idx) : esc(it.label);
      it._score = s.score;
      (picked[it.group] = picked[it.group] || []).push(it);
    });
    GROUP_ORDER.forEach((g) => {
      (picked[g] || []).forEach((it) => out.push(it));
    });
    return out;
  }

  function scrollToRule(title) {
    var box = openDisclosure("#disclosure-checked");
    if (!box) {
      scrollToEl(document.getElementById("checked-rules"));
      return;
    }
    var rows = box.querySelectorAll(".rule-row");
    for (var i = 0; i < rows.length; i++) {
      var head = rows[i].querySelector(".rule-title");
      if (head && head.textContent.trim() === String(title).trim()) {
        scrollToEl(rows[i]);
        return;
      }
    }
    scrollToEl(document.getElementById("checked-rules") || box);
  }

  function render(query) {
    ensureDom();
    var items = buildItems(query);
    flat = items;
    list.innerHTML = "";
    if (!items.length) {
      var empty = document.createElement("p");
      empty.className = "palette-empty";
      empty.textContent = "No matches";
      list.appendChild(empty);
      input.removeAttribute("aria-activedescendant");
      return;
    }
    var lastGroup = null;
    items.forEach((it, n) => {
      if (it.group !== lastGroup) {
        lastGroup = it.group;
        var head = document.createElement("p");
        head.className = "palette-head";
        head.setAttribute("role", "presentation");
        head.textContent = it.group;
        list.appendChild(head);
      }
      var d = document.createElement("div");
      d.className = "palette-item";
      d.setAttribute("role", "option");
      d.id = "palette-opt-" + n;
      d.setAttribute("aria-selected", "false");
      d.innerHTML = '<span class="palette-label">' + (it.labelHtml || esc(it.label)) + "</span>"
        + (it.sub ? '<span class="palette-sub">' + esc(it.sub) + "</span>" : "");
      (function (item) {
        d.addEventListener("mousedown", (e) => {
          e.preventDefault();
          runItem(item);
        });
      })(it);
      list.appendChild(d);
    });
    var best = 0;
    for (var b = 1; b < items.length; b++) {
      if ((items[b]._score || 0) > (items[best]._score || 0)) best = b;
    }
    setActive(best);
  }

  function setActive(n) {
    if (!flat.length) return;
    if (n < 0) n = 0;
    if (n > flat.length - 1) n = flat.length - 1;
    var opts = list.querySelectorAll(".palette-item");
    for (var i = 0; i < opts.length; i++) opts[i].setAttribute("aria-selected", "false");
    var el = list.querySelector("#palette-opt-" + n);
    if (!el) return;
    el.setAttribute("aria-selected", "true");
    el.scrollIntoView({ block: "nearest" });
    input.setAttribute("aria-activedescendant", el.id);
    list.dataset.active = String(n);
  }
  function move(d) {
    var cur = parseInt(list.dataset.active || "0", 10) || 0;
    setActive(cur + d);
  }
  function activate() {
    var cur = parseInt(list.dataset.active || "0", 10) || 0;
    var it = flat[cur];
    if (it) runItem(it);
  }
  function runItem(it) {
    close();
    try { it.run(); } catch (e) { /* keep page usable */ }
  }

  function open() {
    if (demoRunning()) return;
    ensureDom();
    ensureRailButton();
    if (!scrim.hidden) return;
    opener = document.activeElement;
    input.value = "";
    render("");
    scrim.hidden = false;
    input.focus();
  }
  function close() {
    if (!scrim || scrim.hidden) return;
    scrim.hidden = true;
    list.innerHTML = "";
    flat = [];
    if (opener && opener.isConnected) {
      try { opener.focus({ preventScroll: true }); } catch (e) { /* opener gone */ }
    }
    opener = null;
  }

  document.addEventListener("keydown", (e) => {
    var hot = (e.key === "k" || e.key === "K") && (e.ctrlKey || e.metaKey);
    if (!hot) return;
    e.preventDefault();
    if (demoRunning()) return;
    ensureDom();
    if (!scrim.hidden) close();
    else open();
  });

  function init() {
    ensureDom();
    ensureRailButton();
    // A tour can start from the #/demo hash while the palette is open; close it then.
    if (typeof MutationObserver !== "undefined") {
      new MutationObserver(() => { if (demoRunning()) close(); })
        .observe(document.body, { attributes: true, attributeFilter: ["class"] });
    }
  }
  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", init);
  } else {
    init();
  }
})();
