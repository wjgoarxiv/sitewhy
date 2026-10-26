/* SiteWhy HQ demo roll — scripted step tour over the showcase samples.
 * Todo 3, option A from .litclaude/evidence/ui-crucible/demo.md.
 *
 * Contract: drives the page ONLY through [data-demo="…"] anchors and
 * window.SiteWhy.selectSite / window.SiteWhy.openChecked. Until those
 * land (Todo 2), every lookup is guarded — a missing anchor or global
 * skips the highlight and keeps the caption going.
 * Network: only GET /samples/* (SAMPLE_MODE-safe, no POST /runs).
 */
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

  /* Captions are template strings filled from loaded report fields.
   * Nothing is hard-coded; every value has a fallback so no caption
   * can ever contain "undefined" or "null". */
  const captions = {
    picker: (r) =>
      `${num(r.project?.mw)} MW at ${shortAddr(r.project?.address)} screens ${verdictWord(r)} — this is the roll's spine.`,
    banner: (r) =>
      `Verdict up top: ${txt(r.explanation?.headline, "the headline states the verdict and the decisive rule")}.`,
    map: (r) => {
      const county = txt(r.jurisdiction?.county_name, "the county");
      const place = r.jurisdiction?.place;
      return place
        ? `Inside ${place}, the ${county} pause does not reach this lot.`
        : `This lot sits in unincorporated ${county}, so the county pause reaches it.`;
    },
    decisive: (r) => {
      const ev = r.findings?.[0]?.evidence?.[0];
      return `“${clip(ev?.quote, 140) || "the decisive rule cites its source line"}” — recorded as ${txt(ev?.verification, "checked")}.`;
    },
    catches: (r) => {
      const c = r.explanation?.catches?.[0];
      const t = clip(c.text, 130);
      return c
        ? `A second agent (${txt(c.actor, "reviewer")}, ${txt(c.kind, "check").replace(/_/g, " ")}) flagged this run: ${t}${t.endsWith(".") ? "" : "."}`
        : "No double-checks were needed on this run.";
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
  function num(mw) {
    const n = Number(mw);
    return Number.isFinite(n) ? String(Math.round(n)) : "This site";
  }

  /* Eight steps, ~9 s each: about 72 s total, inside the 90 s budget. */
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

  function openChecked(section) {
    try {
      if (window.SiteWhy && typeof window.SiteWhy.openChecked === "function") {
        window.SiteWhy.openChecked(section);
        return;
      }
    } catch { /* guarded: fall through to legacy tabs */ }
    try {
      const bar = $("tablist");
      const legacy = section === "catches" ? "caught" : "hood";
      if (bar && bar._select) bar._select(legacy);
      else $(`tab-${legacy}`)?.click();
    } catch { /* missing tabs: skip, keep caption */ }
  }

  function waitForReport(timeoutMs) {
    const deadline = Date.now() + timeoutMs;
    return new Promise((resolve) => {
      const poll = () => {
        const ready =
          txt($("banner-headline")?.textContent, "") !== "" ||
          ($("map-chip") && !$("map-chip").hidden);
        if (ready || Date.now() > deadline) resolve();
        else setTimeout(poll, 250);
      };
      poll();
    });
  }

  async function navigate(site) {
    try {
      if (window.SiteWhy && typeof window.SiteWhy.selectSite === "function") {
        await window.SiteWhy.selectSite(site);
        return;
      }
    } catch { /* guarded: fall through to hash driving */ }
    if (location.hash !== `#/site/${encodeURIComponent(site)}`) {
      location.hash = `#/site/${encodeURIComponent(site)}`;
    }
    await waitForReport(8000);
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
    if (!el) return false; // missing anchor: skip highlight, keep caption
    el.classList.add("demo-spot");
    try {
      el.scrollIntoView({ block: "nearest", behavior: reducedMotion() ? "auto" : "smooth" });
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
    savedHash: "",
    savedFocus: null,
    log: [],
  };

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

  function armTimer() {
    clearTimeout(demo.timer);
    if (!demo.running || demo.paused) return;
    demo.timer = setTimeout(() => void move(1), STEP_MS);
  }

  async function show(i) {
    demo.index = Math.max(0, Math.min(STEPS.length - 1, i));
    const step = STEPS[demo.index];
    let caption = "The demo roll is playing.";
    try {
      if (step.breadth) {
        const [a, b] = await Promise.all([fetchReport(BREADTH_GO), fetchReport(BREADTH_ERCOT)]);
        await navigate(BREADTH_ERCOT);
        caption = captions.breadth(a, b);
      } else {
        const report = await fetchReport(step.site);
        if (step.checked) openChecked(step.checked);
        await navigate(step.site);
        caption = step.caption(report);
      }
    } catch {
      caption = "This stop is unavailable offline — the roll continues.";
    }
    const highlighted = highlight(step.anchor);
    demo.log.push({ step: demo.index, anchor: step.anchor, highlighted, caption });
    const capEl = $("demo-caption");
    if (capEl) capEl.textContent = caption;
    paint();
    armTimer();
  }

  function move(d) {
    if (!demo.running) return Promise.resolve();
    return show(demo.index + d).then(() => {
      if (demo.index >= STEPS.length - 1 && d > 0) exit();
    });
  }

  function togglePause() {
    if (!demo.running) return;
    demo.paused = !demo.paused;
    paint();
    armTimer();
  }

  function pause() {
    if (demo.running && !demo.paused) togglePause();
  }

  async function start() {
    if (demo.running) return;
    buildBar();
    demo.running = true;
    demo.paused = false;
    demo.log = [];
    demo.savedHash = location.hash;
    demo.savedFocus = document.activeElement;
    const bar = $("demo-bar");
    if (bar) bar.hidden = false;
    await show(0);
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
    demo.running = false;
    demo.paused = false;
    clearTimeout(demo.timer);
    clearSpot();
    const bar = $("demo-bar");
    if (bar) bar.hidden = true;
    // Ending on #/demo would restart the roll via the hash listener,
    // so a #/demo start ends on the spine report instead.
    const endHash =
      demo.savedHash && demo.savedHash !== "#/demo"
        ? demo.savedHash
        : `#/site/${SPINE}`;
    if (location.hash !== endHash) location.hash = endHash;
    try {
      if (demo.savedFocus && demo.savedFocus.focus) demo.savedFocus.focus({ preventScroll: true });
    } catch { /* skip */ }
  }

  document.addEventListener(
    "click",
    (ev) => {
      if (!demo.running) return;
      if (ev.target && ev.target.closest && ev.target.closest("#demo-bar")) return;
      pause(); // any click outside the caption bar pauses, never fights input
    },
    true,
  );

  document.addEventListener("keydown", (ev) => {
    if (!demo.running) return;
    if (ev.key === "Escape") {
      ev.preventDefault();
      exit();
    } else if (ev.key === " ") {
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
