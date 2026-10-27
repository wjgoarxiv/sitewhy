(() => {
  "use strict";

  const STEP_MS = 6000;
  const INTRO_MS = 4000;
  const OUTRO_MS = 6000;
  const SPEEDS = [1, 1.5, 2];
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

  // Fixed rail titles (8 stops). Data-driven facts stay in `captions`.
  const TITLES = [
    "Pick a site",
    "The verdict",
    "On the map",
    "The rule that decides",
    "Agents double-check",
    "Who did the work",
    "What would change it",
    "Another grid",
  ];

  const LOOKS = [
    "the showcase site list on the left",
    "the yellow verdict panel at the top",
    "the satellite map with the jurisdiction overlay",
    "the evidence card with the ordinance quote",
    "the double-checks card",
    "the agent lanes: who ran each step, on which model",
    "the sensitivity table",
    "a different site under a different grid",
  ];

  const INTRO_TITLE = "A 60-second tour of how SiteWhy decides";
  const INTRO_LINE = "8 stops · auto-advances · Space pauses · Esc exits";
  const INTRO_LOOK = "the how-it-works strip at the top";
  const OUTRO_LINE = "That's SiteWhy: verdict, the rule behind it, and the agents that checked it.";
  const OUTRO_LOOK = "the portfolio list — pick your next site";
  const OUTRO_CTA = "Try another site";

  const captions = {
    picker: (r) => {
      const mw = Number(r.project?.mw);
      const load = Number.isFinite(mw) ? `${Math.round(mw)} MW at ` : "";
      return `${load}${shortAddr(r.project?.address)} screens ${verdictWord(r)} — this is the site we will walk through.`;
    },
    banner: (r) =>
      `Verdict up top: ${txt(r.explanation?.headline, "the headline states the verdict and the decisive rule")}.`,
    map: (r) => {
      const chip = document.querySelector('[data-demo="map"] .chip');
      const rendered = String(chip?.textContent || "").trim();
      if (rendered) return `${rendered} — the geographic scope of the ruling.`;
      const j = r.jurisdiction || {};
      return `${txt(j.county_name, "the county")} · ${txt(j.iso, "its grid")} — the geographic scope of the ruling.`;
    },
    decisive: (r) => {
      const fact = r.explanation?.decisive?.[0]?.fact;
      if (!fact?.quote) return "This is the single rule that decides the verdict — no verified quote on this run.";
      return `The one rule that decides it: “${clip(fact.quote, 90)}” — ${txt(fact.verification, "checked")}.`;
    },
    catches: (r) => {
      const all = r.explanation?.catches || [];
      const rank = (k) => ({ source_conflict: 0, unsupported_link: 1, correction: 2, conflict: 3 })[k] ?? (k === "retry" ? 9 : 5);
      const c = all.slice().sort((a, b) => rank(a.kind) - rank(b.kind))[0];
      if (!c) return "No double-checks were needed on this run.";
      const t = clip(c.text, 90);
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
        ? `One change rewrites the answer: ${clip(f.change, 80)} reads ${txt(f.estimated_verdict, "differently")}.`
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
    { site: SPINE, anchor: "lanes", caption: captions.trace },
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

  function highlight(anchor, tag) {
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
    if (tag) el.setAttribute("data-demo-tag", tag);
    try {
      el.scrollIntoView({ block: "center", behavior: reducedMotion() ? "auto" : "smooth" });
    } catch { /* skip */ }
    return true;
  }

  function clearSpot() {
    try {
      document.querySelectorAll(".demo-spot").forEach((el) => {
        el.classList.remove("demo-spot");
        el.removeAttribute("data-demo-tag");
      });
    } catch { /* skip */ }
  }

  function targetEl(anchor) {
    if (!anchor) return null;
    try {
      return document.querySelector(`[data-demo="${anchor}"]`);
    } catch {
      return null;
    }
  }

  // No overlay element, so Leaflet keeps receiving pointer events.
  function applyDim(anchor, extra) {
    const target = targetEl(anchor);
    try {
      document.querySelectorAll("[data-demo]").forEach((el) => {
        const keep =
          !!target && (el === target || el.contains(target) || target.contains(el));
        const keepExtra =
          !!extra && (el === extra || el.contains(extra) || extra.contains(el));
        if (keep || keepExtra) {
          el.style.opacity = "";
          el.classList.remove("demo-dim");
        } else {
          el.style.opacity = "0.2";
          el.classList.add("demo-dim");
        }
      });
      document.querySelectorAll(".rail section").forEach((el) => {
        const keep = !!target && (el === target || el.contains(target));
        el.style.opacity = keep ? "" : "0.2";
      });
    } catch { /* skip */ }
  }

  function clearDim() {
    try {
      document.querySelectorAll("[data-demo], .rail section").forEach((el) => {
        el.style.opacity = "";
        if (el.classList) el.classList.remove("demo-dim");
      });
    } catch { /* skip */ }
  }

  const demo = {
    running: false,
    paused: false,
    phase: "idle",
    index: 0,
    timer: 0,
    epoch: 0,
    speed: 1,
    deadline: 0,
    next: null,
    pausedAt: 0,
    etaTimer: 0,
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
    const railBtns = TITLES.map(
      (t, i) =>
        `<button type="button" class="demo-rail-btn" data-i="${i}" data-state="upcoming"><span class="demo-seg" aria-hidden="true"></span>${t}</button>`,
    ).join("");
    const speedBtns = SPEEDS.map(
      (s) =>
        `<button type="button" data-speed="${s}" aria-pressed="${s === demo.speed}">${s}×</button>`,
    ).join("");
    bar.innerHTML =
      `<div class="demo-progress" role="progressbar" aria-label="Demo roll progress" ` +
      `aria-valuemin="1" aria-valuemax="${STEPS.length}" aria-valuenow="1"><span></span></div>` +
      `<nav class="demo-rail" aria-label="Tour stops">${railBtns}</nav>` +
      `<p class="demo-step" id="demo-step"><span id="demo-step-text"></span><span id="demo-paused-badge" hidden>Paused</span></p>` +
      `<p class="demo-eta" id="demo-eta"></p>` +
      `<div class="demo-caption" id="demo-caption" aria-live="polite" tabindex="-1">` +
      `<p class="demo-look"><strong>LOOK:</strong> <span id="demo-look"></span></p>` +
      `<p class="demo-why"><strong>WHY IT MATTERS:</strong> <span id="demo-why"></span></p>` +
      `</div>` +
      `<div class="demo-controls">` +
      `<button type="button" id="demo-pause">Pause</button>` +
      `<button type="button" id="demo-back">Back</button>` +
      `<button type="button" id="demo-next">Next</button>` +
      `<span class="demo-speed" role="group" aria-label="Tour speed">${speedBtns}</span>` +
      `<button type="button" id="demo-try" hidden>${OUTRO_CTA}</button>` +
      `<button type="button" id="demo-exit">Exit</button>` +
      `</div>` +
      `<p class="demo-keys">Space pause · ← → step · Esc exit</p>`;
    document.body.appendChild(bar);
    bar.querySelectorAll(".demo-rail-btn").forEach((b) =>
      b.addEventListener("click", () => jump(Number(b.dataset.i))),
    );
    bar.querySelectorAll("[data-speed]").forEach((b) =>
      b.addEventListener("click", () => setSpeed(Number(b.dataset.speed))),
    );
    $("demo-pause").addEventListener("click", () => togglePause());
    $("demo-back").addEventListener("click", () => move(-1));
    $("demo-next").addEventListener("click", () => move(1));
    $("demo-try").addEventListener("click", () => tryAnother());
    $("demo-exit").addEventListener("click", () => exit());
  }

  function paintRail() {
    const btns = document.querySelectorAll("#demo-bar .demo-rail-btn");
    btns.forEach((b, i) => {
      let state = "upcoming";
      if (demo.phase === "step") {
        state = i < demo.index ? "done" : i === demo.index ? "current" : "upcoming";
      } else if (demo.phase === "outro") {
        state = "done";
      }
      b.dataset.state = state;
      if (state === "current") b.setAttribute("aria-current", "true");
      else b.removeAttribute("aria-current");
    });
  }

  function paintCaption(look, why) {
    const lookEl = $("demo-look");
    const whyEl = $("demo-why");
    if (lookEl) lookEl.textContent = look;
    if (whyEl) whyEl.textContent = why;
  }

  function paint() {
    const stepText = $("demo-step-text");
    const bar = $("demo-bar");
    if (!stepText || !bar) return;
    if (demo.phase === "intro") {
      stepText.textContent = `Intro · ${TITLES.length} stops`;
    } else if (demo.phase === "outro") {
      stepText.textContent = `Outro · ${OUTRO_CTA}`;
    } else {
      stepText.textContent = `Step ${demo.index + 1} of ${STEPS.length} · ${TITLES[demo.index]}`;
    }
    const badge = $("demo-paused-badge");
    if (badge) badge.hidden = !demo.paused;
    const progress = bar.querySelector(".demo-progress");
    if (progress) {
      const now =
        demo.phase === "intro" ? 1 : demo.phase === "outro" ? STEPS.length : demo.index + 1;
      const frac = demo.phase === "intro" ? 0 : now / STEPS.length;
      progress.setAttribute("aria-valuenow", String(now));
      const fill = progress.querySelector("span");
      if (fill) fill.style.width = `${frac * 100}%`;
    }
    paintRail();
    paintSpeed();
    paintEta();
    const pauseBtn = $("demo-pause");
    if (pauseBtn) pauseBtn.textContent = demo.paused ? "Resume" : "Pause";
    const tryBtn = $("demo-try");
    if (tryBtn) tryBtn.hidden = demo.phase !== "outro";
  }

  function paintSpeed() {
    document.querySelectorAll("#demo-bar [data-speed]").forEach((b) => {
      if (Number(b.dataset.speed) === demo.speed) b.setAttribute("aria-pressed", "true");
      else b.setAttribute("aria-pressed", "false");
    });
  }

  function fmtClock(totalSeconds) {
    const s = Math.max(0, Math.ceil(totalSeconds));
    return `${Math.floor(s / 60)}:${String(s % 60).padStart(2, "0")} left`;
  }

  function phasesAfter1xMs() {
    if (demo.phase === "intro") return STEPS.length * STEP_MS + OUTRO_MS;
    if (demo.phase === "outro") return 0;
    return (LAST - demo.index) * STEP_MS + OUTRO_MS;
  }

  function currentPhase1xMs() {
    if (demo.phase === "intro") return INTRO_MS;
    if (demo.phase === "outro") return OUTRO_MS;
    return STEP_MS;
  }

  function paintEta() {
    const el = $("demo-eta");
    if (!el) return;
    if (!demo.running || demo.phase === "idle") {
      el.textContent = "";
      return;
    }
    const now = Date.now();
    const ref = demo.paused ? demo.pausedAt : now;
    const currentLeftMs =
      demo.deadline > 0 ? Math.max(0, demo.deadline - ref) : currentPhase1xMs() / demo.speed;
    el.textContent = fmtClock((currentLeftMs + phasesAfter1xMs() / demo.speed) / 1000);
  }

  function loadSpeed() {
    try {
      const s = Number(localStorage.getItem("sitewhy-demo-speed"));
      if (s === 1 || s === 1.5 || s === 2) demo.speed = s;
    } catch { /* private mode keeps 1× */ }
  }

  function setSpeed(s) {
    if (s !== 1 && s !== 1.5 && s !== 2) return;
    if (s !== demo.speed && demo.running && !demo.paused && demo.next) {
      const now = Date.now();
      const left = Math.max(0, demo.deadline - now);
      const scaled = (left * demo.speed) / s;
      demo.speed = s;
      try {
        localStorage.setItem("sitewhy-demo-speed", String(s));
      } catch { /* private mode: session only */ }
      clearTimeout(demo.timer);
      demo.deadline = now + scaled;
      const next = demo.next;
      demo.timer = setTimeout(next, scaled);
    } else {
      demo.speed = s;
      try {
        localStorage.setItem("sitewhy-demo-speed", String(s));
      } catch { /* private mode: session only */ }
    }
    paintSpeed();
    paintEta();
  }

  function pushLog(entry) {
    const look = String(entry.look ?? "").trim();
    const why = String(entry.why ?? "").trim();
    demo.log.push({
      phase: entry.phase,
      step: entry.step,
      anchor: entry.anchor ?? null,
      highlighted: !!entry.highlighted,
      look,
      why,
      caption: `LOOK: ${look || "—"} WHY IT MATTERS: ${why || "—"}`,
    });
  }

  function armTimer(epoch) {
    clearTimeout(demo.timer);
    if (!alive(epoch) || demo.paused) return;
    let wait;
    let next;
    if (demo.phase === "intro") {
      wait = INTRO_MS;
      next = () => move(1);
    } else if (demo.phase === "outro") {
      wait = OUTRO_MS;
      next = () => exit();
    } else if (demo.index >= LAST) {
      wait = STEP_MS;
      next = () => move(1);
    } else {
      wait = STEP_MS;
      next = () => void move(1);
    }
    const ms = wait / demo.speed;
    demo.deadline = Date.now() + ms;
    demo.next = next;
    demo.timer = setTimeout(next, ms);
    paintEta();
  }

  function restoreAfterStale() {
    if (!demo.running && demo.endHash && location.hash !== demo.endHash) {
      location.hash = demo.endHash;
    }
  }

  async function showIntro(epoch) {
    if (!alive(epoch)) return;
    demo.phase = "intro";
    demo.index = 0;
    const anchor = "how";
    const highlighted = highlight(anchor, "How SiteWhy works");
    applyDim(highlighted ? anchor : null);
    const why = `${INTRO_TITLE} — ${INTRO_LINE}.`;
    paintCaption(INTRO_LOOK, why);
    pushLog({ phase: "intro", step: -1, anchor, highlighted, look: INTRO_LOOK, why });
    paint();
    armTimer(epoch);
  }

  async function showStep(i, epoch) {
    if (!alive(epoch)) return;
    demo.phase = "step";
    demo.index = Math.max(0, Math.min(LAST, i));
    const step = STEPS[demo.index];
    let why = "This stop is unavailable offline — the roll continues.";
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
        why = captions.breadth(a, b);
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
        why = step.caption(report);
      }
    } catch {
      why = "This stop is unavailable offline — the roll continues.";
    }
    if (!alive(epoch)) {
      restoreAfterStale();
      return;
    }
    const look = LOOKS[demo.index] || "";
    const highlighted = highlight(step.anchor, `${demo.index + 1} · ${TITLES[demo.index]}`);
    let chainEl = null;
    if (step.anchor === "decisive") {
      try {
        chainEl = document.querySelector('[data-demo="chain"]');
      } catch {
        chainEl = null;
      }
    }
    // The chain stays bright beside the decisive card but gets no second spotlight (one scrim only).
    applyDim(step.anchor, chainEl);
    paintCaption(look, why);
    pushLog({ phase: "step", step: demo.index, anchor: step.anchor, highlighted, look, why });
    paint();
    armTimer(epoch);
  }

  async function showOutro(epoch) {
    if (!alive(epoch)) return;
    demo.phase = "outro";
    clearSpot();
    applyDim(null);
    paintCaption(OUTRO_LOOK, OUTRO_LINE);
    pushLog({ phase: "outro", step: STEPS.length, anchor: null, highlighted: false, look: OUTRO_LOOK, why: OUTRO_LINE });
    paint();
    armTimer(epoch);
  }

  function move(d) {
    if (!demo.running) return Promise.resolve();
    if (d > 0 && demo.phase === "outro") {
      exit();
      return Promise.resolve();
    }
    const epoch = ++demo.epoch;
    clearTimeout(demo.timer);
    demo.deadline = 0;
    demo.next = null;
    if (demo.phase === "intro") {
      return showStep(d > 0 ? 0 : 0, epoch);
    }
    if (demo.phase === "outro") {
      return showStep(LAST, epoch);
    }
    if (d > 0 && demo.index >= LAST) {
      return showOutro(epoch);
    }
    if (d < 0 && demo.index <= 0) {
      return showIntro(epoch);
    }
    return showStep(demo.index + d, epoch);
  }

  function jump(i) {
    if (!demo.running) return;
    const epoch = ++demo.epoch;
    clearTimeout(demo.timer);
    demo.deadline = 0;
    demo.next = null;
    void showStep(i, epoch);
  }

  function togglePause() {
    if (!demo.running) return;
    demo.paused = !demo.paused;
    if (demo.paused) demo.pausedAt = Date.now();
    paint();
    armTimer(demo.epoch);
  }

  function pause() {
    if (demo.running && !demo.paused) togglePause();
  }

  async function start() {
    if (demo.running) return;
    loadSpeed();
    buildBar();
    const epoch = ++demo.epoch;
    demo.running = true;
    demo.paused = false;
    demo.phase = "intro";
    demo.log = [];
    demo.deadline = 0;
    demo.next = null;
    clearInterval(demo.etaTimer);
    demo.etaTimer = setInterval(paintEta, 1000);
    demo.savedHash = location.hash;
    demo.savedFocus = document.activeElement;
    document.body.classList.add("demo-running");
    const bar = $("demo-bar");
    if (bar) bar.hidden = false;
    await showIntro(epoch);
    const capEl = $("demo-caption");
    if (capEl && capEl.focus) {
      try {
        capEl.focus({ preventScroll: true });
      } catch { /* skip */ }
    }
  }

  function tryAnother() {
    exit();
    try {
      const addr = document.getElementById("address");
      if (addr && addr.focus) {
        addr.focus({ preventScroll: false });
        try {
          addr.scrollIntoView({ block: "center", behavior: reducedMotion() ? "auto" : "smooth" });
        } catch { /* skip */ }
        return;
      }
      const row = document.querySelector("#portfolio .site-row");
      if (row && row.focus) row.focus({ preventScroll: false });
    } catch { /* skip */ }
  }

  function exit() {
    if (!demo.running) return;
    demo.epoch += 1;
    demo.running = false;
    demo.paused = false;
    demo.phase = "idle";
    demo.deadline = 0;
    demo.next = null;
    clearTimeout(demo.timer);
    clearInterval(demo.etaTimer);
    demo.etaTimer = 0;
    clearSpot();
    clearDim();
    paintEta();
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
    setSpeed,
    get state() {
      return { running: demo.running, paused: demo.paused, phase: demo.phase, index: demo.index, speed: demo.speed, log: demo.log.slice() };
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
