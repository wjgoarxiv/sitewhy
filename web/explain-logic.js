/* SiteWhy explainer logic: which pipeline chip is working, replay beats, provenance wording.
 * Pure functions over a run's events and a report's model_trace; no DOM access.
 * Loaded before web/explain.js, which draws what these return. */
(function () {
  "use strict";

  var STEPS = ["planner", "investigator", "verifier", "rulecheck", "adjudicator", "critic"];
  var LABELS = {
    planner: "Planner", investigator: "County investigator", verifier: "Evidence verifier",
    rulecheck: "Rule check", adjudicator: "Adjudicator", critic: "Critic",
  };
  // Report event / model_trace role -> pipeline chip. "system" events belong to no chip.
  var ROLE_STEP = {
    planner: "planner", county_investigator: "investigator", evidence_verifier: "verifier",
    applicability: "rulecheck", adjudicator: "adjudicator", critic: "critic",
  };
  var NEXT = {
    planner: "investigator", investigator: "verifier", verifier: "verifier",
    rulecheck: "adjudicator", adjudicator: "critic", critic: null,
  };
  var MAX_ROUNDS = 2; // Orchestrator(max_rounds=2): the critic can send work back once.
  var REPLAY_MS = 8000, MIN_BEAT_MS = 450, MAX_BEAT_MS = 1600;
  var STORE_KEY = "sitewhy.explainer.hidden";

  function modelName(m) {
    var s = String(m || "").replace(/^nvidia\//, "");
    if (/ultra/i.test(s)) return "Nemotron Ultra";
    if (/lightning/i.test(s)) return "Nemotron Lightning";
    return s || "unknown model";
  }

  function secs(ms) {
    var s = ms / 1000;
    return (s >= 10 ? Math.round(s) : s.toFixed(1)) + " s";
  }

  function roundOf(e) {
    return Number(e.round) || 1;
  }

  // The critic sends work back only for objections the planner can act on (orchestrator.run).
  function sendsBack(e, round, localRules) {
    if (round >= MAX_ROUNDS || !Array.isArray(e.detail)) return false;
    return e.detail.some(function (o) {
      return o.type !== "unknown_input" && localRules.indexOf(o.rule_id) >= 0;
    });
  }

  /* Which chip is working after these run events, and which have produced output this round.
   * Each event is emitted when a step finishes, so the working chip is the one that follows. */
  function liveState(events) {
    var round = 1, seen = {}, active = null, agentSeen = false, localRules = [];
    (events || []).forEach(function (e) {
      if (e.action === "seeded" && e.detail) localRules = e.detail.local || [];
      var step = ROLE_STEP[e.role];
      if (!step) {
        if (e.action === "timeout") active = null;
        return;
      }
      agentSeen = true;
      if (roundOf(e) > round) { round = roundOf(e); seen = {}; }
      seen[step] = true;
      active = NEXT[step];
      if (step === "planner" && Array.isArray(e.detail) && !e.detail.length) active = "rulecheck";
      if (step === "investigator" && e.action === "ultra_reextract") active = "investigator";
      if (step === "verifier" && (e.action === "verified" || e.action === "retry_requested")) {
        active = "investigator";
      }
      if (step === "critic") {
        if (sendsBack(e, round, localRules)) { round += 1; seen = {}; active = "planner"; }
        else active = null;
      }
    });
    if (!agentSeen && (events || []).length) active = "planner";
    var done = STEPS.filter(function (s) { return seen[s] && s !== active; });
    var text;
    if (!(events || []).length) text = "Resolving the site…";
    else if (active) text = (round > 1 ? "Round " + round + " · " : "") + LABELS[active] + " working…";
    else text = "Wrapping up…";
    return { round: round, active: active, done: done, text: text };
  }

  // model_trace has no round field: the critic closes each round, so count critic calls.
  function callsByRoundStep(trace) {
    var map = {}, round = 1;
    (trace || []).forEach(function (t) {
      var step = ROLE_STEP[t.role];
      if (!step) return;
      var key = round + ":" + step;
      (map[key] = map[key] || []).push(t);
      if (t.role === "critic") round += 1;
    });
    return map;
  }

  function modelReadout(list) {
    if (!list.length) return "no model call needed";
    var groups = [], total = 0;
    list.forEach(function (t) {
      var name = modelName(t.model);
      var g = groups.filter(function (x) { return x.name === name; })[0];
      if (!g) { g = { name: name, n: 0 }; groups.push(g); }
      g.n += 1;
      total += Number(t.latency_ms) || 0;
    });
    var parts = groups.map(function (g) {
      return (groups.length > 1 ? g.name.replace("Nemotron ", "") : g.name) + (g.n > 1 ? " ×" + g.n : "");
    });
    return parts.join(" + ") + " · " + secs(total);
  }

  function codeReadout(step, round, events) {
    var role = step === "verifier" ? "evidence_verifier" : "applicability";
    var action = step === "verifier" ? "verified" : "computed";
    var checked = 0, failed = 0, rules = 0;
    events.forEach(function (e) {
      if (e.role !== role || e.action !== action || roundOf(e) !== round) return;
      if (step === "verifier" && e.detail) {
        checked += Number(e.detail.checked) || 0;
        failed += Number(e.detail.failed) || 0;
      } else if (Array.isArray(e.detail)) {
        rules = e.detail.length;
      }
    });
    if (step === "verifier" && checked) {
      return checked + " quotes checked · " + (failed ? failed + " not verbatim" : "all verbatim");
    }
    if (step === "rulecheck" && rules) return rules + " rules computed";
    return "Python · no model call";
  }

  /* One beat per chip per round, in the order the report's own events first show them. */
  function replayBeats(report) {
    var events = (report && report.events) || [];
    var calls = callsByRoundStep(report && report.model_trace);
    var beats = [], seen = {}, rounds = 1;
    events.forEach(function (e) {
      var step = ROLE_STEP[e.role];
      if (!step) return;
      var key = roundOf(e) + ":" + step;
      rounds = Math.max(rounds, roundOf(e));
      if (!seen[key]) { seen[key] = true; beats.push({ round: roundOf(e), step: step }); }
    });
    beats.forEach(function (b) {
      var code = b.step === "verifier" || b.step === "rulecheck";
      b.readout = code ? codeReadout(b.step, b.round, events)
        : modelReadout(calls[b.round + ":" + b.step] || []);
      b.text = (rounds > 1 ? "Round " + b.round + " · " : "") + LABELS[b.step] + " · " + b.readout;
    });
    return beats;
  }

  function provenanceText(provenance, verification, ultraRetry) {
    var base;
    if (provenance === "curated") base = "Curated rule text";
    else if (provenance === "county_source" || provenance === "primary") {
      base = "Pulled from the county source by Nemotron Lightning" + (ultraRetry ? ", Ultra on retry" : "");
    } else if (provenance === "dataset") return "From the Moratorium Nation dataset in Zetaris";
    else return "";
    return base + " · " + (verification === "verified"
      ? "verified word for word by code" : "not verified word for word");
  }

  function bannerText(report) {
    var trace = (report && report.model_trace) || [];
    var events = (report && report.events) || [];
    var drafts = trace.filter(function (t) { return t.role === "adjudicator"; });
    if (!drafts.length) return "";
    var text = "Verdict drafted by " + modelName(drafts[drafts.length - 1].model) + " from code-checked rules";
    var challenged = events.some(function (e) { return e.role === "critic"; })
      || trace.some(function (t) { return t.role === "critic"; });
    return challenged ? text + ", then challenged by the critic" : text;
  }

  function usedUltraRetry(report, ruleId) {
    var retried = ((report && report.events) || []).some(function (e) {
      return e.action === "ultra_reextract" && String(e.detail).indexOf(ruleId + ":") === 0;
    });
    return retried || ((report && report.model_trace) || []).some(function (t) {
      return t.role === "county_investigator" && t.escalated_from;
    });
  }

  function hasAgentWork(report) {
    return ((report && report.events) || []).some(function (e) { return !!ROLE_STEP[e.role]; });
  }

  window.SiteWhyExplain = {
    STEPS: STEPS, ROLE_STEP: ROLE_STEP, REPLAY_MS: REPLAY_MS, MIN_BEAT_MS: MIN_BEAT_MS,
    MAX_BEAT_MS: MAX_BEAT_MS, liveState: liveState, replayBeats: replayBeats,
    provenanceText: provenanceText, bannerText: bannerText, modelName: modelName,
    usedUltraRetry: usedUltraRetry, hasAgentWork: hasAgentWork, roundOf: roundOf, secs: secs,
  };
})();
