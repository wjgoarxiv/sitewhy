/* SiteWhy explainer: draws the "what you get" / "where AI is used" panel and the provenance chips.
 * Own files: web/explain.js + web/explain-logic.js + web/explain.css. It only listens to events
 * app.js already dispatches (sitewhy:report, sitewhy:events, sitewhy:run-start, sitewhy:run-end),
 * so it never changes how a run or a report behaves. */
(function () {
  "use strict";

  var X = window.SiteWhyExplain;
  var STEPS = X.STEPS, ROLE_STEP = X.ROLE_STEP, roundOf = X.roundOf, secs = X.secs;
  var liveState = X.liveState, replayBeats = X.replayBeats, hasAgentWork = X.hasAgentWork;
  var provenanceText = X.provenanceText, bannerText = X.bannerText, usedUltraRetry = X.usedUltraRetry;
  var REPLAY_MS = X.REPLAY_MS, MIN_BEAT_MS = X.MIN_BEAT_MS, MAX_BEAT_MS = X.MAX_BEAT_MS;
  var STORE_KEY = "sitewhy.explainer.hidden";

  var panel = document.getElementById("explainer");
  if (!panel) return;

  var wrap = document.getElementById("how");
  var body = document.getElementById("ex-body");
  var toggle = document.getElementById("ex-toggle");
  var caption = document.getElementById("ex-caption");
  var oneline = document.getElementById("ex-oneline");
  var roundBadge = document.getElementById("ex-round");
  var replayBtn = document.getElementById("ex-replay");
  var idleOneline = oneline.textContent;
  var chips = {};
  STEPS.forEach(function (s) { chips[s] = panel.querySelector('[data-step="' + s + '"]'); });
  var SR = { active: "working", done: "done", skipped: "not needed for this site" };

  var live = false, timer = null, current = null;

  function setChip(step, state, readout) {
    var el = chips[step];
    el.setAttribute("data-state", state);
    el.querySelector(".ex-readout").textContent = readout || "";
    el.querySelector(".ex-sr").textContent = SR[state] ? " (" + SR[state] + ")" : "";
  }

  function say(text) {
    caption.textContent = text || "";
    oneline.textContent = text || idleOneline;
  }

  function showRound(round, label) {
    roundBadge.hidden = round < 2;
    roundBadge.textContent = label;
  }

  function paintLive(ls) {
    STEPS.forEach(function (s) {
      setChip(s, ls.active === s ? "active" : ls.done.indexOf(s) >= 0 ? "done" : "idle");
    });
    showRound(ls.round, "Round " + ls.round);
    say(ls.text);
  }

  function paintRest(report) {
    var seen = {}, rounds = 1;
    ((report && report.events) || []).forEach(function (e) {
      var step = ROLE_STEP[e.role];
      if (step) { seen[step] = true; rounds = Math.max(rounds, roundOf(e)); }
    });
    var worked = hasAgentWork(report);
    STEPS.forEach(function (s) {
      if (!worked) setChip(s, "idle");
      else if (seen[s]) setChip(s, "done");
      else setChip(s, "skipped", "not needed here");
    });
    showRound(worked ? rounds : 1, rounds + " rounds");
    say("");
  }

  function syncReplay() {
    replayBtn.disabled = live || !hasAgentWork(current);
    replayBtn.textContent = timer ? "Stop replay" : "Replay how this verdict was built";
    if (timer) replayBtn.disabled = false;
  }

  function stopReplay() {
    clearTimeout(timer);
    timer = null;
    paintRest(current);
    syncReplay();
  }

  function finishReplay() {
    var trace = (current && current.model_trace) || [];
    var ms = trace.reduce(function (sum, t) { return sum + (Number(t.latency_ms) || 0); }, 0);
    clearTimeout(timer);
    timer = null;
    paintRest(current);
    say("Replay done · " + trace.length + " model calls · " + secs(ms) + " of model time");
    syncReplay();
  }

  function startReplay() {
    var beats = replayBeats(current);
    if (!beats.length) return;
    var gap = Math.min(MAX_BEAT_MS, Math.max(MIN_BEAT_MS, REPLAY_MS / beats.length));
    var i = 0, round = 1;
    STEPS.forEach(function (s) { setChip(s, "idle"); });
    showRound(1, "Round 1");
    (function beat() {
      if (i >= beats.length) { finishReplay(); return; }
      var b = beats[i++];
      STEPS.forEach(function (s) {
        if (chips[s].getAttribute("data-state") === "active") setChip(s, "done", chips[s].querySelector(".ex-readout").textContent);
        if (b.round !== round) setChip(s, "idle");
      });
      round = b.round;
      showRound(round, "Round " + round);
      setChip(b.step, "active", b.readout);
      say(b.text);
      timer = setTimeout(beat, gap);
    })();
    syncReplay();
  }

  replayBtn.addEventListener("click", function () {
    if (timer) stopReplay(); else if (!live) startReplay();
  });

  function setHidden(hidden, persist) {
    wrap.setAttribute("data-collapsed", hidden ? "true" : "false");
    body.hidden = hidden;
    toggle.setAttribute("aria-expanded", String(!hidden));
    toggle.textContent = hidden ? "Show" : "Hide";
    if (!persist) return;
    try { localStorage.setItem(STORE_KEY, hidden ? "1" : "0"); } catch (err) { /* storage blocked: keep it for this visit only */ }
  }

  toggle.addEventListener("click", function () {
    setHidden(toggle.getAttribute("aria-expanded") === "true", true);
  });

  var stored = null;
  try { stored = localStorage.getItem(STORE_KEY); } catch (err) { stored = null; }
  setHidden(stored === "1", false);

  function chip(text, kind) {
    var el = document.createElement("span");
    el.className = "prov-chip";
    el.setAttribute("data-prov", kind);
    el.textContent = text;
    return el;
  }

  function addProvenance(report) {
    document.getElementById("prov-banner")?.remove();
    if (!report) return;
    var decisive = (report.explanation || {}).decisive || [];
    var cards = document.querySelectorAll("#decisive-first .decisive, #why-rest .decisive");
    decisive.forEach(function (d, i) {
      var card = cards[i], fact = d.fact || {};
      if (!card) return;
      var quote = card.querySelector(".ev-item");
      var text = provenanceText(fact.provenance, fact.verification, usedUltraRetry(report, d.rule_id));
      if (quote && text) {
        quote.appendChild(chip(text, fact.provenance === "primary" || fact.provenance === "county_source" ? "ai" : fact.provenance));
      }
      [".rule-line", ".check-line"].forEach(function (sel) {
        var line = card.querySelector(sel);
        if (line) line.appendChild(chip("Computed by code", "code"));
      });
    });
    var verdict = bannerText(report), headline = document.getElementById("banner-headline");
    if (!verdict || !headline) return;
    var row = document.createElement("p");
    row.id = "prov-banner";
    row.className = "prov-row";
    row.appendChild(chip(verdict, "ai"));
    headline.after(row);
  }

  document.addEventListener("sitewhy:report", function (e) {
    current = (e.detail && e.detail.report) || null;
    clearTimeout(timer);
    timer = null;
    if (!live) paintRest(current);
    syncReplay();
    addProvenance(current);
  });

  document.addEventListener("sitewhy:run-start", function () {
    clearTimeout(timer);
    timer = null;
    live = true;
    paintLive(liveState([]));
    syncReplay();
  });

  document.addEventListener("sitewhy:events", function (e) {
    if (!live) return;
    paintLive(liveState((e.detail && e.detail.events) || []));
  });

  document.addEventListener("sitewhy:run-end", function () {
    live = false;
    paintRest(current);
    syncReplay();
  });

  if (window.SiteWhy && typeof window.SiteWhy.current === "function") {
    try {
      current = window.SiteWhy.current();
      paintRest(current);
      addProvenance(current);
    } catch (err) { /* the report arrives via event */ }
  }
  syncReplay();
})();
