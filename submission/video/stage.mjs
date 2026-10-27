// Recording engine: browser + motion layer (fx.js) + a narration clock.
// record.mjs owns the script (which beats, in which order); this file owns how a beat is filmed.
import { execFileSync } from 'node:child_process';
import { createRequire } from 'node:module';
import { mkdirSync, readFileSync } from 'node:fs';
import { fileURLToPath } from 'node:url';
import { dirname } from 'node:path';

const require = createRequire(import.meta.url);
const HERE = dirname(fileURLToPath(import.meta.url));
export const sleep = (ms) => new Promise((r) => setTimeout(r, ms));

// narration.txt lines are `shot|id|text`; each line is synthesised once so beats can be paced to its real length.
export function loadNarration(audioDir) {
  mkdirSync(audioDir, { recursive: true });
  const lines = readFileSync(`${HERE}/narration.txt`, 'utf-8').split('\n').filter((l) => l.trim());
  const out = {};
  for (const l of lines) {
    const [shot, id, ...rest] = l.split('|');
    const text = rest.join('|');
    const file = `${audioDir}/${id}.aiff`;
    execFileSync('say', ['-v', 'Samantha', '-r', '185', '-o', file, text]);
    const dur = Number(execFileSync('ffprobe', ['-v', 'error', '-show_entries', 'format=duration', '-of', 'csv=p=0', file], { encoding: 'utf-8' }));
    out[id] = { shot, text, dur };
  }
  return out;
}

export async function createStage({ outDir, narration }) {
  const { chromium } = require(process.env.PLAYWRIGHT_MJS || 'playwright');
  const browser = await chromium.launch({ channel: 'chrome' });
  const ctx = await browser.newContext({
    viewport: { width: 1920, height: 1080 },
    recordVideo: { dir: outDir, size: { width: 1920, height: 1080 } },
  });
  await ctx.addInitScript(readFileSync(`${HERE}/fx.js`, 'utf-8'));
  const t0 = Date.now();
  const page = await ctx.newPage();
  const pageErrors = [];
  page.on('pageerror', (e) => pageErrors.push(e.message));

  const nowMs = () => Date.now() - t0;
  const cues = {};
  const log = [];
  let speechFree = 0;
  let cursor = { x: 150, y: 930 };

  const fx = (fn, ...args) => page.evaluate(([f, a]) => window.__fx[f](...a), [fn, args]);
  const fxBg = (fn, ...args) => { fx(fn, ...args).catch(() => {}); };

  async function ready() {
    await page.waitForFunction(() => window.__fx && window.__fx.ready(), null, { timeout: 15000 });
    await fx('setCursor', cursor.x, cursor.y);
  }

  async function goto(url) {
    await page.goto(url, { waitUntil: 'load' });
    await ready();
  }

  const box = async (sel) => {
    const b = await page.locator(sel).first().boundingBox();
    if (!b) throw new Error(`no box for ${sel}`);
    return b;
  };

  async function glide(sel, { fx: fxr = 0.5, fy: fyr = 0.5, ms = 900 } = {}) {
    const b = await box(sel);
    const x = b.x + b.width * fxr, y = b.y + b.height * fyr;
    await fx('moveTo', x, y, ms);
    await page.mouse.move(x, y);
    cursor = { x, y };
    return { x, y };
  }

  async function click(sel, opts = {}) {
    const { x, y } = await glide(sel, opts);
    await fx('click');
    await page.mouse.click(x, y);
  }

  async function typeInto(sel, text, delay = 70) {
    await click(sel);
    await page.keyboard.press('ControlOrMeta+a');
    await page.keyboard.press('Backspace');
    await page.keyboard.type(text, { delay });
  }

  async function ring(sel, opts = {}) {
    await page.evaluate(([s, o]) => window.__fx.ringOn(window.__fx.find(s), o), [sel, opts]);
  }
  const ringOff = () => fx('ringOff');

  function caption(text, opts = {}) {
    if (text.trim().split(/\s+/).length > 8) throw new Error(`caption over 8 words: ${text}`);
    fxBg('caption', text, opts);
  }

  async function scrollTo(sel, { at = 0.42, ms = 800, container = '' } = {}) {
    await page.evaluate(([s, o]) => window.__fx.scrollToEl(window.__fx.find(s), o), [sel, { at, ms, container }]);
  }

  // Camera move: ease the column back to 1.0 while scrolling `sel` into frame, then push in on it.
  async function show(sel, { scale = 1.25, zoomMs = 2400, at = 0.42, scrollMs = 800, pan = 0.65, drift = 0.05, driftMs = 0, pad = 10, ringIt = true } = {}) {
    await page.evaluate(async ([s, o]) => {
      const el = window.__fx.find(s);
      await Promise.all([window.__fx.zoomReset(o.scrollMs * 0.8), window.__fx.scrollToEl(el, { at: o.at, ms: o.scrollMs })]);
      if (o.ringIt) window.__fx.ringOn(el, { pad: o.pad });
      window.__fx.zoomTo(el, { scale: o.scale, ms: o.zoomMs, pan: o.pan, drift: o.drift, driftMs: o.driftMs });
    }, [sel, { scale, zoomMs, at, scrollMs, pan, drift, driftMs, pad, ringIt }]);
  }

  const reset = (ms = 700) => fx('zoomReset', ms);

  async function speak(id, gapMs = 350) {
    if (!narration[id]) throw new Error(`no narration ${id}`);
    const start = Math.max(nowMs(), speechFree + gapMs);
    if (start > nowMs()) await sleep(start - nowMs());
    cues[id] = nowMs();
    speechFree = cues[id] + Math.round(narration[id].dur * 1000);
    return narration[id].dur * 1000;
  }

  // One narrated beat: narration starts now; `work(durMs)` films it; returns when both are finished.
  async function beat(id, work, tailMs = 250) {
    const dur = await speak(id);
    const end = speechFree + tailMs;
    await Promise.all([work ? work(dur) : null, sleep(Math.max(0, end - nowMs()))]);
  }

  const mark = (name, url = '') => log.push({ name, tMs: nowMs(), url });

  async function close() {
    const video = page.video();
    await ctx.close();
    await browser.close();
    return video ? await video.path() : null;
  }

  return { page, fx, fxBg, ready, goto, glide, click, typeInto, ring, ringOff, caption, scrollTo, show, reset,
    speak, beat, mark, nowMs, cues, log, pageErrors, close, sleep };
}
