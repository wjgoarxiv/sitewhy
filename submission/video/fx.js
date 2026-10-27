// Motion layer injected into every page of the recording (addInitScript).
// Exposes window.__fx: gliding cursor + click ripple, eased smooth scroll,
// slow zoom/pan on a root element, a ring that draws around the narrated
// element, and a lower-third caption. Pure presentation: it never reads or
// changes app data, and it is not part of the product.
(() => {
  if (window.__fx) return;
  const NS = 'http://www.w3.org/2000/svg';
  const ease = (t) => (t < 0.5 ? 4 * t * t * t : 1 - Math.pow(-2 * t + 2, 3) / 2);
  const frame = () => new Promise((r) => requestAnimationFrame(r));
  const lerp = (a, b, t) => a + (b - a) * t;

  const css = `
    #__fx-cursor{position:fixed;left:0;top:0;width:44px;height:44px;z-index:2147483646;pointer-events:none;
      will-change:transform;filter:drop-shadow(3px 4px 3px rgba(0,0,0,.45));transition:scale .12s ease}
    #__fx-cursor.press{scale:.82}
    .__fx-ripple{position:fixed;z-index:2147483645;width:20px;height:20px;margin:-10px 0 0 -10px;border-radius:50%;
      border:5px solid #ff3d2e;pointer-events:none;animation:__fxrip .7s ease-out forwards}
    @keyframes __fxrip{from{transform:scale(.4);opacity:.95}to{transform:scale(4.2);opacity:0}}
    #__fx-svg{position:fixed;inset:0;width:100vw;height:100vh;z-index:2147483644;pointer-events:none}
    #__fx-cap{position:fixed;left:72px;bottom:70px;z-index:2147483643;pointer-events:none;display:flex;align-items:stretch;
      font:700 42px/1.15 -apple-system,"Helvetica Neue",Arial,sans-serif;color:#fff;background:#0b0b0b;
      box-shadow:9px 9px 0 rgba(0,0,0,.38);opacity:0;transform:translateY(26px);transition:opacity .28s ease,transform .28s ease}
    #__fx-cap.on{opacity:1;transform:none}
    #__fx-cap .tag{display:flex;align-items:center;padding:0 20px;font:800 28px/1 ui-monospace,Menlo,monospace;
      letter-spacing:2px;color:#0b0b0b;background:#ffd84a}
    #__fx-cap .tag.ai{background:#6aa6ff}#__fx-cap .tag.code{background:#5fd68a}
    #__fx-cap .txt{padding:14px 28px}
    #__fx-cap .sub{display:block;font:500 25px/1.25 ui-monospace,Menlo,monospace;color:#c9d3df;margin-top:4px}
  `;
  const style = document.createElement('style');
  style.textContent = css;

  const els = {};
  const state = { x: 150, y: 930, root: null, base: null, s: 1, tx: 0, ty: 0, drift: 0, ring: null, ringPulse: 0 };

  function build() {
    if (els.cursor || !document.body) return;
    document.head.appendChild(style);
    const c = document.createElement('div');
    c.id = '__fx-cursor';
    c.innerHTML = '<svg viewBox="0 0 44 44" width="44" height="44"><path d="M5 3 L5 33 L13 26 L19 40 L26 37 L20 24 L31 24 Z" fill="#111" stroke="#fff" stroke-width="2.6" stroke-linejoin="round"/></svg>';
    document.body.appendChild(c);
    els.cursor = c;
    const svg = document.createElementNS(NS, 'svg');
    svg.id = '__fx-svg';
    const rect = document.createElementNS(NS, 'rect');
    rect.setAttribute('fill', 'none');
    rect.setAttribute('stroke', '#ff3d2e');
    rect.setAttribute('stroke-width', '6');
    rect.setAttribute('rx', '14');
    rect.setAttribute('pathLength', '1');
    rect.setAttribute('stroke-linejoin', 'round');
    rect.style.display = 'none';
    svg.appendChild(rect);
    document.body.appendChild(svg);
    els.ring = rect;
    const cap = document.createElement('div');
    cap.id = '__fx-cap';
    document.body.appendChild(cap);
    els.cap = cap;
    place();
    loop();
  }

  function place(sway = false) {
    const t = performance.now();
    const ox = sway ? 5 * Math.sin(t / 650) : 0, oy = sway ? 4 * Math.cos(t / 830) : 0;
    els.cursor.style.transform = `translate(${state.x + ox}px,${state.y + oy}px)`;
  }

  // Keeps the ring glued to its element while the page scrolls or zooms.
  function loop() {
    if (!state.moving) place(true);
    syncRing();
    requestAnimationFrame(loop);
  }

  function syncRing() {
    const r = state.ring;
    if (r && r.el && r.el.isConnected) {
      const b = r.el.getBoundingClientRect();
      const pad = r.pad;
      const pulse = r.done ? 1 + 0.025 * Math.sin(performance.now() / 260) : 1;
      const w = (b.width + pad * 2) * pulse;
      const h = (b.height + pad * 2) * pulse;
      const x = b.left - pad - (w - b.width - pad * 2) / 2;
      const y = b.top - pad - (h - b.height - pad * 2) / 2;
      els.ring.setAttribute('x', x);
      els.ring.setAttribute('y', y);
      els.ring.setAttribute('width', Math.max(w, 8));
      els.ring.setAttribute('height', Math.max(h, 8));
      const per = 2 * (w + h);
      els.ring.setAttribute('stroke-dasharray', `${per} ${per}`);
      const t = Math.min(1, (performance.now() - r.t0) / r.ms);
      els.ring.setAttribute('stroke-dashoffset', String(per * (1 - ease(t))));
      if (t >= 1) r.done = true;
    }
  }

  const api = {
    ready() { build(); return !!els.cursor; },

    find(sel) {
      const all = [...document.querySelectorAll(sel)];
      return all.find((e) => e.getClientRects().length) || all[0] || null;
    },

    setCursor(x, y) { build(); state.x = x; state.y = y; place(); },

    async moveTo(x, y, ms = 900) {
      build();
      state.moving = true;
      const x0 = state.x, y0 = state.y, t0 = performance.now();
      const bow = Math.min(90, Math.hypot(x - x0, y - y0) * 0.12);
      for (;;) {
        const t = Math.min(1, (performance.now() - t0) / ms);
        const e = ease(t);
        state.x = lerp(x0, x, e);
        state.y = lerp(y0, y, e) - Math.sin(Math.PI * e) * bow;
        place();
        if (t >= 1) break;
        await frame();
      }
      state.moving = false;
    },

    async click() {
      build();
      els.cursor.classList.add('press');
      const rip = document.createElement('div');
      rip.className = '__fx-ripple';
      rip.style.left = state.x + 'px';
      rip.style.top = state.y + 'px';
      document.body.appendChild(rip);
      setTimeout(() => rip.remove(), 800);
      await new Promise((r) => setTimeout(r, 140));
      els.cursor.classList.remove('press');
    },

    pos() { return { x: state.x, y: state.y }; },

    // ---- smooth scroll (the main column scrolls, not the document) ----
    scroller() { return document.querySelector('main.center') || document.scrollingElement; },

    async scrollTo(top, ms = 800, sc = api.scroller()) {
      const y0 = sc.scrollTop, t0 = performance.now();
      for (;;) {
        const t = Math.min(1, (performance.now() - t0) / ms);
        sc.scrollTop = lerp(y0, top, ease(t));
        syncRing();
        if (t >= 1) break;
        await frame();
      }
    },

    // Scroll so the element sits at `at` (fraction of the scroller height). The main column is measured in
    // untransformed space; any other container (e.g. the left rail) uses plain rects.
    async scrollToEl(el, { at = 0.42, ms = 800, container = '' } = {}) {
      const sc = container ? document.querySelector(container) : api.scroller();
      const plain = !!container;
      const rr = el.getBoundingClientRect();
      const r = plain ? rr : api.unxform(rr);
      const cb = sc.getBoundingClientRect();
      const box = plain ? cb : api.unxform(cb);
      const want = sc.scrollTop + (r.top + r.height / 2) - (box.top + box.height * at);
      await api.scrollTo(Math.max(0, Math.min(want, sc.scrollHeight - sc.clientHeight)), ms, sc);
    },

    // ---- zoom / pan on the root column (CSS transform, origin = its top-left) ----
    setRoot(sel, { clamp = true, raise = false } = {}) {
      if (state.root) { state.root.style.transform = ''; state.root.style.zIndex = ''; state.root.style.position = state.prevPos || ''; }
      state.drift++;
      state.root = document.querySelector(sel);
      // a zoomed root can overlap its sibling column; keep it on top so clicks land on what is on screen
      state.prevPos = state.root.style.position;
      if (raise) {
        if (getComputedStyle(state.root).position === 'static') state.root.style.position = 'relative';
        state.root.style.zIndex = '30';
      }
      state.clamp = clamp;
      state.base = null; state.s = 1; state.tx = 0; state.ty = 0;
    },
    root() {
      if (!state.root || !state.root.isConnected) state.root = document.querySelector('main.center') || document.body.firstElementChild;
      return state.root;
    },
    baseRect() {
      const root = api.root();
      if (!state.base || state.base.el !== root) {
        const prev = root.style.transform;
        root.style.transform = 'none';
        const b = root.getBoundingClientRect();
        root.style.transform = prev;
        state.base = { el: root, left: b.left, top: b.top, width: b.width, height: b.height };
        root.style.transformOrigin = '0 0';
        root.style.willChange = 'transform';
      }
      return state.base;
    },
    unxform(r) {
      const b = api.baseRect();
      const f = (px, py) => [b.left + (px - b.left - state.tx) / state.s, b.top + (py - b.top - state.ty) / state.s];
      const [l, t] = f(r.left, r.top);
      const [rr, bb] = f(r.right, r.bottom);
      return { left: l, top: t, right: rr, bottom: bb, width: rr - l, height: bb - t };
    },
    applyZoom() {
      const b = api.baseRect();
      b.el.style.transform = `translate(${state.tx}px,${state.ty}px) scale(${state.s})`;
      syncRing();
    },
    // Ease the camera onto el (scale s, pan toward the viewport middle), then keep creeping for `drift`.
    async zoomTo(el, { scale = 1.25, ms = 2400, pan = 0.65, y = 0.44, drift = 0.05, driftMs = 0, to = null } = {}) {
      const b = api.baseRect();
      const token = ++state.drift;
      const c = api.unxform(el.getBoundingClientRect());
      const cx = c.left + c.width / 2, cy = c.top + c.height / 2;
      const dx = to ? to[0] : lerp(cx, innerWidth / 2, pan), dy = to ? to[1] : innerHeight * y;
      const clamp = (v, lo, hi) => Math.max(lo, Math.min(hi, v));
      const s1 = scale;
      let tx1 = dx - b.left - s1 * (cx - b.left);
      let ty1 = dy - b.top - s1 * (cy - b.top);
      if (state.clamp !== false) {
        tx1 = clamp(tx1, innerWidth - b.left - s1 * b.width, 0);
        ty1 = clamp(ty1, innerHeight - b.top - s1 * b.height, 0);
      }
      const s0 = state.s, x0 = state.tx, y0 = state.ty, t0 = performance.now();
      for (;;) {
        if (token !== state.drift) return;
        const t = Math.min(1, (performance.now() - t0) / ms);
        const e = ease(t);
        state.s = lerp(s0, s1, e); state.tx = lerp(x0, tx1, e); state.ty = lerp(y0, ty1, e);
        api.applyZoom();
        if (t >= 1) break;
        await frame();
      }
      if (driftMs > 0) {
        // never a still: keep a very slow push-in under long narration (not awaited by the caller's next beat)
        (async () => {
          const ds = s1 + drift, dtx = tx1 - drift * (cx - b.left), dty = ty1 - drift * (cy - b.top);
          const t1 = performance.now();
          for (;;) {
            if (token !== state.drift) return;
            const t = Math.min(1, (performance.now() - t1) / driftMs);
            state.s = lerp(s1, ds, t); state.tx = lerp(tx1, dtx, t); state.ty = lerp(ty1, dty, t);
            api.applyZoom();
            if (t >= 1) return;
            await frame();
          }
        })();
      }
    },
    async zoomReset(ms = 700) {
      const token = ++state.drift;
      const s0 = state.s, x0 = state.tx, y0 = state.ty, t0 = performance.now();
      if (s0 === 1 && x0 === 0 && y0 === 0) return;
      for (;;) {
        if (token !== state.drift) return;
        const t = Math.min(1, (performance.now() - t0) / ms);
        const e = ease(t);
        state.s = lerp(s0, 1, e); state.tx = lerp(x0, 0, e); state.ty = lerp(y0, 0, e);
        api.applyZoom();
        if (t >= 1) break;
        await frame();
      }
    },

    // ---- ring + caption ----
    ringOn(el, { pad = 10, ms = 700 } = {}) {
      build();
      state.ring = { el, pad, ms, t0: performance.now(), done: false };
      els.ring.style.display = '';
    },
    ringOff() { state.ring = null; if (els.ring) els.ring.style.display = 'none'; },
    caption(text, { tag = '', kind = '', sub = '' } = {}) {
      build();
      const cap = els.cap;
      cap.classList.remove('on');
      if (!text) return;
      cap.innerHTML = (tag ? `<span class="tag ${kind}">${tag}</span>` : '')
        + `<span class="txt">${text}${sub ? `<span class="sub">${sub}</span>` : ''}</span>`;
      void cap.offsetWidth;
      cap.classList.add('on');
    },
    captionOff() { if (els.cap) els.cap.classList.remove('on'); },
  };

  window.__fx = api;
  if (document.readyState === 'loading') document.addEventListener('DOMContentLoaded', build);
  else build();
})();
