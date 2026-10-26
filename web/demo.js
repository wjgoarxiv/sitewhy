(() => {
  "use strict";

  const STEP_MS = 9000;
  const SPINE = "md-washington-county-unincorporated";
  const BREADTH_GO = "az-tucson-pima";
  const BREADTH_ERCOT = "tx-abilene-ercot";

  const $ = (id) => document.getElementById(id);
  const txt = (v, fb) => {
    const s = String(v ?? "").trim();
    return s ? s : fb;
  };
  const shortAddr = (address) => String(address || "").split(",")[0].trim() || "this site";
  const shortModel = (m) => String(m || "").replace(/^nvidia\//, "") || "the screening model";
  const clip = (s, n) => {
    const t = String(s || "").trim().replace(/\s+/g, " ");
    return t.length > n ? `${t.slice(0, n - 1)}…` : t;
  };
  const reducedMotion = () =>
    window.matchMedia("(prefers-reduced-motion: reduce)").matches;

  const VERDICT_WORD = {
    "no-go": "No-go",
    go: "Go",
    conditional: "Conditional",
    needs_confirmation: "Needs one more check",
  };
  const verdictWord = (r) => txt(VERDICT_WORD[r.verdict], "this site");

  const cache = new Map();
  async function fetchReport(site) {
    if (cache.has(site)) return cache.get(site);
    const res = await fetch(`/samples/${encodeURIComponent(site)}`);
    if (!res.ok) throw new Error(`samples ${res.status}`);
    const report = await res.json();
    cache.set(site, report);
    return report;
  }

  const captions = {
    picker: (r) => {
      const mw = Number(r.project?.mw);
      const load = Number.isFinite(mw) ? `${Math.round(mw)} MW at ` : "";
      return `${load}${shortAddr(r.project?.address)} screens ${verdictWord(r)} — this is the roll's spine.`;
    },
    banner: (r) =>
      `Verdict up top: ${txt(r.explanation?.headline, "the headline states the verdict and the decisive rule")}.`,
    map: (r) => {
      const chip = document.querySelector('[data-demo="map"] .chip');
      const rendered = String(chip?.textContent || "").trim();
      if (rendered) return rendered;
      const j = r.jurisdiction || {};
      return `${txt(j.county_name, "the county")} · ${txt(j.iso, "its grid")}`;
    },
    decisive: (r) => {
      const fact = r.explanation?.decisive?.[0]?.fact;
      if (!fact?.quote) return "The decisive card states the rule and its source.";
      return `“${clip(fact.quote, 140)}” — recorded as ${txt(fact.verification, "checked")}.`;
    },
    catches: (r) => {
      const all = r.explanation?.catches || [];
      const rank = (k) => ({ source_conflict: 0, unsupported_link: 1, correction: 2, conflict: 3 })[k] ?? (k === "retry" ? 9 : 5);
      const c = all.slice().sort((a, b) => rank(a.kind) - rank(b.kind))[0];
      if (!c) return "No double-checks were needed on this run.";
      const t = clip(c.text, 130);
      return `A second agent (${txt(c.actor, "reviewer")}, ${txt(c.kind, "check").replace(/_/g, " ")}) flagged this run: ${t}${/[.…]$/.test(t) ? "" : "."}`;
    },
    trace: (r) => {
      const m = r.model_trace?.[0];
      const zetaris = (r.data_trace || []).filter((q) => (q.backend || "").toLowerCase() === "zetaris").length;
      const chunks = r.explanation?.stats?.markovian_chunks;
      return `Built by ${shortModel(m?.model)} (receipt ${txt(m?.receipt_id, "on file")}); ${zetaris || "its"} Zetaris queries and ${chunks ?? "its"} token-saving passes back it.`;
    },
    flips: (r) => {
      const f = r.explanation?.flips?.[0];
      return f
        ? `One change rewrites the answer: ${clip(f.change, 110)} reads ${txt(f.estimated_verdict, "differently")}.`
        : "No single change flips this answer.";
    },
    breadth: (a, b) =>
      `${shortAddr(a.project?.address)} screens ${verdictWord(a)} under ${txt(a.jurisdiction?.iso, "its grid")}; ` +
      `${shortAddr(b.project?.address)} screens ${verdictWord(b)} under ${txt(b.jurisdiction?.iso, "its grid")} — same engine, different grids.`,
  };

  const STEPS = [
    { site: SPINE, anchor: "picker", caption: captions.picker },
    { site: SPINE, anchor: "banner", caption: captions.banner },
    { site: SPINE, anchor: "map", caption: captions.map },
    { site: SPINE, anchor: "decisive", caption: captions.decisive },
    { site: SPINE, anchor: "catches", checked: "catches", caption: captions.catches },
    { site: SPINE, anchor: "trace", checked: "trace", caption: captions.trace },
    { site: SPINE, anchor: "flips", caption: captions.flips },
    { site: BREADTH_ERCOT, anchor: "banner", breadth: true, caption: null },
  ];
  const LAST = STEPS.length - 1;

  function openChecked(section) {
    window.SiteWhy?.openChecked?.(section);
  }

  async function navigate(site) {
    await window.SiteWhy.selectSite(site);
  }

  function highlight(anchor) {
    clearSpot();
    if (!anchor) return false;
    let el = null;
    try {
      el = document.querySelector(`[data-demo="${anchor}"]`);
    } catch {
      el = null;
    }
    if (!el) return false;
    try {
      const closed = el.closest("details:not([open])");
      if (closed) closed.open = true;
    } catch { /* skip */ }
    el.classList.add("demo-spot");
    try {
      el.scrollIntoView({ block: "center", behavior: reducedMotion() ? "auto" : "smooth" });
    } catch { /* skip */ }
    return true;
  }

  function clearSpot() {
    try {
      document.querySelectorAll(".demo-spot").forEach((el) => el.classList.remove("demo-spot"));
    } catch { /* skip */ }
  }

  const demo = {
    running: false,
    paused: false,
    index: 0,
    timer: 0,
    epoch: 0,
    savedHash: "",
    savedFocus: null,
    endHash: "",
    log: [],
  };
  const alive = (epoch) => epoch === demo.epoch && demo.running;

  function buildBar() {
    if ($("demo-bar")) return;
    const bar = document.createElement("div");
    bar.id = "demo-bar";
    bar.hidden = true;
    bar.setAttribute("role", "region");
    bar.setAttribute("aria-label", "Demo roll");
    bar.innerHTML =
      `<div class="demo-progress" role="progressbar" aria-label="Demo roll progress" ` +
      `aria-valuemin="1" aria-valuemax="${STEPS.length}" aria-valuenow="1"><span></span></div>` +
      `<p class="demo-step" id="demo-step"></p>` +
      `<p class="demo-caption" id="demo-caption" aria-live="polite"></p>` +
      `<div class="demo-controls">` +
      `<button type="button" id="demo-pause">Pause</button>` +
      `<button type="button" id="demo-back">Back</button>` +
      `<button type="button" id="demo-next">Next</button>` +
      `<button type="button" id="demo-exit">Exit</button>` +
      `</div>`;
    document.body.appendChild(bar);
    $("demo-pause").addEventListener("click", () => togglePause());
    $("demo-back").addEventListener("click", () => move(-1));
    $("demo-next").addEventListener("click", () => move(1));
    $("demo-exit").addEventListener("click", () => exit());
  }

  function paint() {
    const stepEl = $("demo-step");
    const capEl = $("demo-caption");
    const bar = $("demo-bar");
    if (!stepEl || !capEl || !bar) return;
    stepEl.textContent = `Step ${demo.index + 1} of ${STEPS.length}`;
    const progress = bar.querySelector(".demo-progress");
    if (progress) {
      progress.setAttribute("aria-valuenow", String(demo.index + 1));
      const fill = progress.querySelector("span");
      if (fill) fill.style.width = `${((demo.index + 1) / STEPS.length) * 100}%`;
    }
    const pauseBtn = $("demo-pause");
    if (pauseBtn) pauseBtn.textContent = demo.paused ? "Resume" : "Pause";
  }

  function armTimer(epoch) {
    clearTimeout(demo.timer);
    if (!alive(epoch) || demo.paused) return;
    if (demo.index >= LAST) demo.timer = setTimeout(() => exit(), STEP_MS);
    else demo.timer = setTimeout(() => void move(1), STEP_MS);
  }

  function restoreAfterStale() {
    if (!demo.running && demo.endHash && location.hash !== demo.endHash) {
      location.hash = demo.endHash;
    }
  }

  async function show(i, epoch) {
    if (!alive(epoch)) return;
    demo.index = Math.max(0, Math.min(LAST, i));
    const step = STEPS[demo.index];
    let caption = "The demo roll is playing.";
    try {
      if (step.breadth) {
        const [a, b] = await Promise.all([fetchReport(BREADTH_GO), fetchReport(BREADTH_ERCOT)]);
        if (!alive(epoch)) {
          restoreAfterStale();
          return;
        }
        await navigate(BREADTH_ERCOT);
        if (!alive(epoch)) {
          restoreAfterStale();
          return;
        }
        caption = captions.breadth(a, b);
      } else {
        if (step.checked) openChecked(step.checked);
        const report = await fetchReport(step.site);
        if (!alive(epoch)) {
          restoreAfterStale();
          return;
        }
        await navigate(step.site);
        if (!alive(epoch)) {
          restoreAfterStale();
          return;
        }
        caption = step.caption(report);
      }
    } catch {
      caption = "This stop is unavailable offline — the roll continues.";
    }
    if (!alive(epoch)) {
      restoreAfterStale();
      return;
    }
    const highlighted = highlight(step.anchor);
    demo.log.push({ step: demo.index, anchor: step.anchor, highlighted, caption });
    const capEl = $("demo-caption");
    if (capEl) capEl.textContent = caption;
    paint();
    armTimer(epoch);
  }

  function move(d) {
    if (!demo.running) return Promise.resolve();
    if (d > 0 && demo.index >= LAST) {
      exit();
      return Promise.resolve();
    }
    const epoch = ++demo.epoch;
    clearTimeout(demo.timer);
    return show(demo.index + d, epoch);
  }

  function togglePause() {
    if (!demo.running) return;
    demo.paused = !demo.paused;
    paint();
    armTimer(demo.epoch);
  }

  function pause() {
    if (demo.running && !demo.paused) togglePause();
  }

  async function start() {
    if (demo.running) return;
    buildBar();
    const epoch = ++demo.epoch;
    demo.running = true;
    demo.paused = false;
    demo.log = [];
    demo.savedHash = location.hash;
    demo.savedFocus = document.activeElement;
    document.body.classList.add("demo-running");
    const bar = $("demo-bar");
    if (bar) bar.hidden = false;
    await show(0, epoch);
    const capEl = $("demo-caption");
    if (capEl && capEl.focus) {
      capEl.setAttribute("tabindex", "-1");
      try {
        capEl.focus({ preventScroll: true });
      } catch { /* skip */ }
    }
  }

  function exit() {
    if (!demo.running) return;
    demo.epoch += 1;
    demo.running = false;
    demo.paused = false;
    clearTimeout(demo.timer);
    clearSpot();
    document.body.classList.remove("demo-running");
    const bar = $("demo-bar");
    if (bar) bar.hidden = true;
    demo.endHash = demo.savedHash === "#/demo" ? `#/site/${SPINE}` : demo.savedHash;
    if (location.hash !== demo.endHash) location.hash = demo.endHash;
    try {
      if (demo.savedFocus && demo.savedFocus.focus) demo.savedFocus.focus({ preventScroll: true });
    } catch { /* skip */ }
  }

  document.addEventListener(
    "click",
    (ev) => {
      if (!demo.running) return;
      if (ev.target && ev.target.closest && ev.target.closest("#demo-bar")) return;
      pause();
    },
    true,
  );

  document.addEventListener("keydown", (ev) => {
    if (!demo.running) return;
    if (ev.key === "Escape") {
      ev.preventDefault();
      exit();
      return;
    }
    const t = ev.target;
    if (t && t.closest && (t.closest("input, textarea, select") || t.closest("#demo-bar button"))) return;
    if (ev.key === " ") {
      ev.preventDefault();
      togglePause();
    } else if (ev.key === "ArrowRight") {
      ev.preventDefault();
      void move(1);
    } else if (ev.key === "ArrowLeft") {
      ev.preventDefault();
      void move(-1);
    }
  });

  document.addEventListener("visibilitychange", () => {
    if (document.hidden) pause();
  });

  function hashIsDemo() {
    return location.hash === "#/demo";
  }

  window.addEventListener("hashchange", () => {
    if (hashIsDemo() && !demo.running) void start();
  });

  window.SiteWhyDemo = {
    start,
    exit,
    get state() {
      return { running: demo.running, paused: demo.paused, index: demo.index, log: demo.log.slice() };
    },
  };

  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", () => {
      $("demo-roll")?.addEventListener("click", () => void start());
      if (hashIsDemo()) void start();
    });
  } else {
    $("demo-roll")?.addEventListener("click", () => void start());
    if (hashIsDemo()) void start();
  }
})();
