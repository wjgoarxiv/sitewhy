/* SiteWhy settings module: reading density, motion and term hints.
 * Own files: web/settings.js + web/settings.css. Never touches app.js/app.css/index.html.
 * Listens to sitewhy:report; reads window.SiteWhy.current() on load. */
(function () {
  "use strict";

  var STORE_KEY = "sitewhy-settings";

  /* Generic glossary definitions only: no report facts, numbers or place names. */
  var TERMS = [
    ["Needs one more check", "A verdict meaning an open question must be resolved before the answer is final."],
    ["decisive rule", "The single rule that decides the verdict; everything else is context."],
    ["verified quote", "A source passage checked word for word against its origin."],
    ["Conditional", "A verdict meaning the site can proceed only if a condition or waiver resolves the blocking rule."],
    ["Nightshift", "The service SiteWhy uses to call the models; it returns a receipt per call."],
    ["Nemotron", "A family of AI models by NVIDIA; SiteWhy uses them to read rules and evidence."],
    ["moratorium", "A temporary pause on accepting or approving a kind of project."],
    ["Zetaris", "The data backend SiteWhy queries for site and boundary data."],
    ["ISO/RTO", "The power market operator for a region; it runs the grid and the wholesale market."],
    ["No-go", "A verdict meaning a decisive rule applies: the site cannot proceed as proposed."],
    ["NERC", "The North American Electric Reliability Corporation; it sets reliability standards for the grid."],
    ["tpy", "Tons per year, a unit for annual air emissions; permits use it as a threshold."],
    ["Go", "A verdict meaning no blocking rule was found for the site as screened."],
    ["MW", "Megawatt, a unit of electric power; data center size is often stated in megawatts of IT load."]
  ];

  var SCOPES = ["banner", "decisive-first", "lamps", "legend"];
  var SKIP_TAGS = { A: 1, BUTTON: 1, MARK: 1, ABBR: 1, INPUT: 1, SELECT: 1, TEXTAREA: 1, SCRIPT: 1, STYLE: 1 };

  var settings = { density: "full", motion: "system", hints: "on" };
  var gearBtn = null;
  var panel = null;
  var lastFocus = null;

  function load() {
    try {
      var raw = localStorage.getItem(STORE_KEY);
      if (!raw) return;
      var s = JSON.parse(raw);
      if (s.density === "brief" || s.density === "full") settings.density = s.density;
      if (s.motion === "reduced" || s.motion === "system") settings.motion = s.motion;
      if (s.hints === "on" || s.hints === "off") settings.hints = s.hints;
    } catch (e) { /* private mode: keep defaults */ }
  }

  function persist() {
    try {
      localStorage.setItem(STORE_KEY, JSON.stringify(settings));
    } catch (e) { /* private mode */ }
  }

  function escRx(s) {
    return s.replace(/[.*+?^${}()|[\]\\]/g, "\\$&");
  }

  function termRegex(term) {
    /* Hyphen counts as a word char here so "Go" never matches inside "No-go". */
    return new RegExp("(?<![A-Za-z0-9-])" + escRx(term).replace(/\s+/g, "\\s+") + "(?![A-Za-z0-9-])", "i");
  }

  function skipped(node) {
    var el = node.parentElement;
    while (el) {
      if (SKIP_TAGS[el.tagName]) return true;
      el = el.parentElement;
    }
    return false;
  }

  function unwrap(container) {
    var found = container.querySelectorAll("abbr.term");
    for (var i = 0; i < found.length; i++) {
      var text = document.createTextNode(found[i].textContent);
      found[i].parentNode.replaceChild(text, found[i]);
    }
    container.normalize();
  }

  function wrapFirst(container, term, def) {
    var rx = termRegex(term);
    var walker = document.createTreeWalker(container, NodeFilter.SHOW_TEXT);
    var nodes = [];
    var n;
    while ((n = walker.nextNode())) nodes.push(n);
    for (var i = 0; i < nodes.length; i++) {
      var node = nodes[i];
      if (!node.nodeValue || skipped(node)) continue;
      var m = rx.exec(node.nodeValue);
      if (!m) continue;
      var after = node.splitText(m.index);
      var rest = after.splitText(m[0].length);
      void rest;
      var abbr = document.createElement("abbr");
      abbr.className = "term";
      abbr.setAttribute("tabindex", "0");
      abbr.setAttribute("data-def", def);
      abbr.textContent = after.nodeValue;
      after.parentNode.replaceChild(abbr, after);
      return true;
    }
    return false;
  }

  function applyHints() {
    for (var c = 0; c < SCOPES.length; c++) {
      var container = document.getElementById(SCOPES[c]);
      if (!container) continue;
      unwrap(container);
      if (settings.hints !== "on") continue;
      for (var t = 0; t < TERMS.length; t++) {
        wrapFirst(container, TERMS[t][0], TERMS[t][1]);
      }
    }
  }

  function apply() {
    document.body.classList.toggle("density-brief", settings.density === "brief");
    document.body.classList.toggle("reduce-motion", settings.motion === "reduced");
    syncPanel();
    applyHints();
  }

  function demoRunning() {
    return document.body.classList.contains("demo-running");
  }

  function railTools() {
    var t = document.querySelector(".rail-tools");
    if (!t) {
      t = document.createElement("div");
      t.className = "rail-tools";
      var anchor = document.querySelector(".rail .brand") || document.querySelector(".rail");
      if (anchor) anchor.after(t);
      else document.body.prepend(t);
    }
    return t;
  }

  function buildGear() {
    if (document.getElementById("settings-open")) return;
    gearBtn = document.createElement("button");
    gearBtn.type = "button";
    gearBtn.id = "settings-open";
    gearBtn.className = "settings-btn";
    gearBtn.setAttribute("aria-label", "Settings");
    gearBtn.setAttribute("aria-haspopup", "dialog");
    gearBtn.textContent = "\u2699 Settings";
    gearBtn.addEventListener("click", function () {
      if (demoRunning()) return;
      if (panel && !panel.hidden) closePanel();
      else openPanel();
    });
    railTools().appendChild(gearBtn);
  }

  function groupHtml(name, legend, options) {
    var html = '<fieldset class="settings-group" data-group="' + name + '"><legend>' + legend + "</legend>";
    for (var i = 0; i < options.length; i++) {
      html += '<label><input type="radio" name="sitewhy-' + name + '" value="' + options[i][0] + '">'
        + '<span>' + options[i][1] + "</span></label>";
    }
    return html + "</fieldset>";
  }

  function buildPanel() {
    if (document.getElementById("settings-panel")) return;
    panel = document.createElement("div");
    panel.id = "settings-panel";
    panel.className = "settings-panel";
    panel.setAttribute("role", "dialog");
    panel.setAttribute("aria-modal", "false");
    panel.setAttribute("aria-labelledby", "settings-h");
    panel.hidden = true;
    panel.innerHTML =
      '<h2 id="settings-h">Settings</h2>'
      + groupHtml("density", "Reading density", [["full", "Full"], ["brief", "Brief"]])
      + '<p class="settings-note">Brief hides secondary detail; verdict, headline, decisive rule and map stay.</p>'
      + groupHtml("motion", "Motion", [["system", "System"], ["reduced", "Reduced"]])
      + groupHtml("hints", "Term hints", [["on", "On"], ["off", "Off"]])
      + '<p class="settings-note">Term hints explain words like moratorium or MW where they appear.</p>'
      + '<button type="button" class="settings-close">Done</button>';
    document.body.appendChild(panel);
    panel.addEventListener("change", function (ev) {
      var input = ev.target;
      if (!input || input.tagName !== "INPUT") return;
      var group = input.name.replace(/^sitewhy-/, "");
      if (group === "density" || group === "motion" || group === "hints") {
        settings[group] = input.value;
        persist();
        apply();
      }
    });
    panel.querySelector(".settings-close").addEventListener("click", closePanel);
    document.addEventListener("pointerdown", function (ev) {
      if (!panel || panel.hidden) return;
      if (panel.contains(ev.target)) return;
      if (gearBtn && gearBtn.contains(ev.target)) return;
      closePanel();
    });
    document.addEventListener("keydown", function (ev) {
      if (ev.key !== "Escape") return;
      if (!panel || panel.hidden) return;
      if (demoRunning()) return;
      ev.stopPropagation();
      closePanel();
    });
    /* Never hold the panel open over the demo roll. */
    new MutationObserver(function () {
      if (demoRunning() && panel && !panel.hidden) closePanel();
    }).observe(document.body, { attributes: true, attributeFilter: ["class"] });
  }

  function syncPanel() {
    if (!panel) return;
    var groups = { density: settings.density, motion: settings.motion, hints: settings.hints };
    Object.keys(groups).forEach(function (group) {
      var checked = panel.querySelector('input[name="sitewhy-' + group + '"][value="' + groups[group] + '"]');
      if (checked) checked.checked = true;
    });
    if (gearBtn) gearBtn.setAttribute("aria-expanded", panel.hidden ? "false" : "true");
  }

  function openPanel() {
    if (!panel || demoRunning()) return;
    lastFocus = document.activeElement;
    panel.hidden = false;
    syncPanel();
    var first = panel.querySelector("input:checked") || panel.querySelector("input");
    if (first) first.focus();
  }

  function closePanel() {
    if (!panel || panel.hidden) return;
    panel.hidden = true;
    syncPanel();
    if (lastFocus && document.contains(lastFocus)) lastFocus.focus();
    else if (gearBtn) gearBtn.focus();
  }

  load();
  buildGear();
  buildPanel();
  apply();

  document.addEventListener("sitewhy:report", function () {
    if (settings.hints === "on") applyHints();
    else {
      for (var c = 0; c < SCOPES.length; c++) {
        var container = document.getElementById(SCOPES[c]);
        if (container) unwrap(container);
      }
    }
  });

  if (window.SiteWhy && typeof window.SiteWhy.current === "function") {
    try {
      if (window.SiteWhy.current() && settings.hints === "on") applyHints();
    } catch (e) { /* report arrives via event */ }
  }
})();
