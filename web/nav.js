(() => {
  "use strict";

  const COLLAPSE_KEY = "sitewhy-rail-collapsed";
  const RESCAN_DEBOUNCE_MS = 150;

  const SECTIONS = [
    { label: "Verdict", sel: "#banner" },
    { label: "The rule", sel: "#decisive-first" },
    { label: "Why chain", sel: "#why-chain" },
    { label: "Map", sel: ".map-wrap" },
    { label: "Layers", sel: ".layers" },
    { label: "Agents", sel: "#agent-lanes" },
    { label: "Why", sel: "#disclosure-why" },
    { label: "How it was checked", sel: "#disclosure-checked" },
  ];

  const reducedMotion = () =>
    window.matchMedia("(prefers-reduced-motion: reduce)").matches;

  let items = [];
  let observer = null;
  let rescanTimer = 0;
  const visible = new Map();

  function ensureRailTools() {
    let t = document.querySelector(".rail-tools");
    if (!t) {
      t = document.createElement("div");
      t.className = "rail-tools";
      (document.querySelector(".rail .brand") || document.querySelector(".rail")).after(t);
    }
    return t;
  }

  function ensureNav() {
    let nav = document.querySelector(".section-nav");
    if (!nav) {
      nav = document.createElement("nav");
      nav.className = "section-nav";
      nav.setAttribute("aria-label", "Report sections");
      const toggle = document.createElement("button");
      toggle.type = "button";
      toggle.className = "nav-collapse";
      toggle.addEventListener("click", () => applyCollapsed(!isCollapsed()));
      nav.appendChild(toggle);
      ensureRailTools().after(nav);
    }
    return nav;
  }

  function isCollapsed() {
    const rail = document.querySelector(".rail");
    return !!rail && rail.classList.contains("rail-collapsed");
  }

  function applyCollapsed(collapsed) {
    const rail = document.querySelector(".rail");
    if (rail) rail.classList.toggle("rail-collapsed", collapsed);
    document.querySelectorAll(".section-nav .nav-collapse").forEach((b) => {
      b.setAttribute("aria-expanded", String(!collapsed));
      b.textContent = collapsed ? "»" : "«";
      b.setAttribute("aria-label", collapsed ? "Expand rail" : "Collapse rail");
    });
    try {
      localStorage.setItem(COLLAPSE_KEY, collapsed ? "1" : "0");
    } catch { /* private mode: session only */ }
  }

  function readCollapsed() {
    try {
      return localStorage.getItem(COLLAPSE_KEY) === "1";
    } catch {
      return false;
    }
  }

  function setActive(item) {
    items.forEach((it) => {
      if (item && it.sel === item.sel) it.btn.setAttribute("aria-current", "true");
      else it.btn.removeAttribute("aria-current");
    });
  }

  function goTo(sel) {
    const el = document.querySelector(sel);
    if (!el) return;
    try {
      const closed = el.closest("details:not([open])");
      if (closed) closed.open = true;
    } catch { /* skip */ }
    try {
      el.scrollIntoView({ block: "start", behavior: reducedMotion() ? "auto" : "smooth" });
    } catch { /* skip */ }
    const item = items.find((it) => it.sel === sel);
    if (item) setActive(item);
  }

  function buildItems(nav, list) {
    nav.querySelector("ol")?.remove();
    const ol = document.createElement("ol");
    items = list.map((s, i) => {
      const li = document.createElement("li");
      const btn = document.createElement("button");
      btn.type = "button";
      const num = document.createElement("span");
      num.className = "nav-num";
      num.textContent = String(i + 1);
      num.setAttribute("aria-hidden", "true");
      const lab = document.createElement("span");
      lab.className = "nav-label";
      lab.textContent = s.label;
      btn.append(num, lab);
      btn.addEventListener("click", () => goTo(s.sel));
      li.appendChild(btn);
      ol.appendChild(li);
      return { label: s.label, sel: s.sel, el: document.querySelector(s.sel), btn };
    });
    nav.appendChild(ol);
    setActive(items[0] || null);
  }

  function scrollRoot() {
    if (window.matchMedia("(min-width: 1180px)").matches) {
      return document.querySelector(".center");
    }
    return null;
  }

  function observe() {
    if (observer) {
      observer.disconnect();
      observer = null;
    }
    visible.clear();
    if (!items.length || !("IntersectionObserver" in window)) return;
    const root = scrollRoot();
    observer = new IntersectionObserver(
      (entries) => {
        entries.forEach((e) => {
          const it = items.find((x) => x.el === e.target);
          if (!it) return;
          if (e.isIntersecting) visible.set(it.sel, e.boundingClientRect.top);
          else visible.delete(it.sel);
        });
        if (!visible.size) return;
        let best = null;
        visible.forEach((top, sel) => {
          if (best === null || top < visible.get(best)) best = sel;
        });
        const item = items.find((it) => it.sel === best);
        if (item) setActive(item);
      },
      { root, rootMargin: "-20% 0px -70% 0px", threshold: 0 },
    );
    items.forEach((it) => {
      if (it.el) observer.observe(it.el);
    });
  }

  let lastKey = "";
  function rescan() {
    const nav = ensureNav();
    const list = SECTIONS.filter((s) => document.querySelector(s.sel));
    const key = list.map((s) => s.sel).join("|");
    if (key !== lastKey) {
      lastKey = key;
      buildItems(nav, list);
    }
    updateVisibility();
    observe();
  }

  function scheduleRescan() {
    clearTimeout(rescanTimer);
    rescanTimer = setTimeout(rescan, RESCAN_DEBOUNCE_MS);
  }

  function updateVisibility() {
    const view = document.getElementById("report-view");
    const show = !!view && !view.hidden;
    document.querySelectorAll(".section-nav").forEach((n) => {
      n.hidden = !show;
    });
  }

  function init() {
    ensureNav();
    applyCollapsed(readCollapsed());
    rescan();
    document.addEventListener("sitewhy:report", () => {
      if (window.requestAnimationFrame) window.requestAnimationFrame(rescan);
      else scheduleRescan();
    });
    const view = document.getElementById("report-view");
    if (view && "MutationObserver" in window) {
      new MutationObserver((mutations) => {
        if (mutations.some((m) => m.type === "attributes")) updateVisibility();
        if (mutations.some((m) => m.type === "childList")) scheduleRescan();
      }).observe(view, { attributes: true, attributeFilter: ["hidden"], childList: true, subtree: true });
    }
    let resizeTimer = 0;
    window.addEventListener("resize", () => {
      clearTimeout(resizeTimer);
      resizeTimer = setTimeout(observe, 200);
    });
  }

  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", init);
  } else {
    init();
  }
})();
