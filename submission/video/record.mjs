// Demo recorder v2. Usage: node record.mjs OUT_DIR   (env SEGMENTS=get,report,... to film a subset)
// Films the SiteWhy HQ in Chrome at 1920x1080 against a SAMPLE_MODE server (default http://localhost:8030),
// with a gliding cursor, smooth scrolling, zoom/pan, highlight rings and lower-third captions (fx.js).
// Narration lines (narration.txt) are synthesised first so every beat is paced to its real length.
// Writes OUT_DIR/take.webm + OUT_DIR/shots.json (cue time per narration line, trim window, shot log).
// The intro/outro clips come from cover.mjs; mux.sh joins everything.
import { readFileSync, writeFileSync, mkdirSync, renameSync } from 'node:fs';
import { fileURLToPath } from 'node:url';
import { dirname, resolve } from 'node:path';
import { createStage, loadNarration } from './stage.mjs';

const BASE = process.env.SITEWHY_BASE || 'http://localhost:8030';
if (new URL(BASE).port === '8000') throw new Error('refusing to record against port 8000');
const HERE = dirname(fileURLToPath(import.meta.url));
const ROOT = resolve(HERE, '..', '..');
const OUT = resolve(process.argv[2] || '/tmp/sitewhy-take3');
mkdirSync(OUT, { recursive: true });
const TERM = 'file://' + HERE + '/terminal.html';
const ADDRESS = '100 W Washington St, Hagerstown MD 21740';
const SECRET = /nvapi-|sk-[A-Za-z0-9]{8}|Bearer\s+[A-Za-z0-9]|PROXY_TOKEN|ZETARIS_API_KEY|hackathon-keys/i;

const status = await (await fetch(BASE + '/status')).json();
if (!status.sample_mode) throw new Error('server is not in SAMPLE_MODE; refusing to record');

const USL_LINES = ['$ cat zetaris/usl.sql + evidence (committed files, shown verbatim)'];
{
  const sql = readFileSync(ROOT + '/zetaris/usl.sql', 'utf-8').split('\n')
    .filter((l) => l.trim() && !l.startsWith('--')).slice(0, 6).map((l) => '  ' + l.trim().slice(0, 88));
  const uq = JSON.parse(readFileSync(ROOT + '/zetaris/evidence/usl_queries.json', 'utf-8'));
  const dq = JSON.parse(readFileSync(ROOT + '/zetaris/evidence/dq_rule.json', 'utf-8'));
  USL_LINES.push(...sql, ...uq.queries.map((q) => `  ${q.name} → ${q.row_count} rows`),
    `  dq ${dq.name}: ${dq.passed ? 'PASS' : 'FAIL'} (${dq.violation_count} violations)`);
}
if (USL_LINES.some((l) => SECRET.test(l))) throw new Error('secret pattern in terminal text');

const narration = loadNarration(OUT + '/audio');
const s = await createStage({ outDir: OUT, narration });
const { page, fx, fxBg, glide, click, ring, ringOff, caption, show, reset, beat, mark, sleep } = s;
// The server lists every old run under "Your screenings"; show only the showcase sites and runs made during this take.
const TAKE_START_ID = new Date().toISOString().replace(/[-:]/g, '').slice(0, 15) + 'Z';
await page.route('**/portfolio', async (route) => {
  const res = await route.fetch();
  const rows = await res.json();
  await route.fulfill({ response: res, json: rows.filter((r) => r.kind === 'showcase' || String(r.id) >= TAKE_START_ID) });
});
const AI = { tag: 'AI', kind: 'ai' };
const CODE = { tag: 'CODE', kind: 'code' };

async function scan() {
  const text = await page.evaluate(() => document.body.innerText);
  if (SECRET.test(text)) throw new Error('secret pattern visible on page');
}

// Portfolio rows carry no ids; tag them so beats can address them by site.
async function tagRows() {
  await page.evaluate(() => {
    for (const li of document.querySelectorAll('#portfolio li')) {
      const t = li.innerText;
      const id = t.includes('13820 Pennsylvania') ? 'wash' : t.includes('100 W Washington') ? 'hag'
        : t.includes('255 W Alameda') ? 'az' : t.includes('555 Walnut') ? (t.includes('50 MW') ? 'tx50' : 'tx300') : '';
      if (id) li.setAttribute('data-vid', id);
    }
  });
}

async function pickSite(id) {
  await tagRows();
  const sel = `#portfolio li[data-vid="${id}"]`;
  await Promise.all([reset(600), ringOff(), s.scrollTo(sel, { container: '.rail', at: 0.55, ms: 700 })]);
  await click(sel, { ms: 900 });
  await page.waitForSelector('#report-view:not([hidden]) #banner-verdict:not(:empty)', { timeout: 20000 });
  await sleep(700);
}

const chip = (name) => `.ex-step[data-step="${name}"]`;
const waitChip = (name, states, timeout = 30000) => page.waitForFunction(
  ([sel, st]) => st.includes(document.querySelector(sel).dataset.state), [chip(name), states], { timeout })
  .then(() => true, () => false);

const SEG = {
  async get() {
    mark('get', BASE + '/');
    await show('.ex-get', { scale: 1.2, zoomMs: 2400, at: 0.4, ringIt: false, driftMs: 9000 });
    await sleep(1500);
    await beat('L03', async (dur) => {
      const tiles = [['verdict', '1 · A verdict'], ['rule', '2 · The deciding rule'], ['math', '3 · The math'], ['flips', '4 · What would change it']];
      const step = Math.max(900, (dur - 400) / tiles.length);
      for (const [t, label] of tiles) {
        await ring(`.ex-tile[data-tile="${t}"]`, { pad: 8 });
        caption(label, { tag: 'YOU GET' });
        await glide(`.ex-tile[data-tile="${t}"]`, { fx: 0.6, fy: 0.45, ms: 700 });
        await sleep(step - 700);
      }
    });
    await ringOff();
  },

  async report() {
    await pickSite('wash');
    mark('verdict', 'wash');
    await beat('L04', async () => {
      caption('No-go, with the reason up front');
      await show('#banner', { scale: 1.2, zoomMs: 2200, at: 0.3, driftMs: 3000 });
      await glide('#banner', { fx: 0.82, fy: 0.3, ms: 900 });
    });
    await beat('L05', async (dur) => {
      caption('Quoted word for word', { ...CODE, sub: 'verified against the source text' });
      await show('#decisive-first .ev-item', { scale: 1.3, zoomMs: 2300, at: 0.42, driftMs: dur });
      await sleep(2300);
      await ring('#decisive-first .ev-item mark', { pad: 6 });
      await glide('#decisive-first .ev-item mark', { ms: 800 });
    });
    await beat('L06', async (dur) => {
      caption('The math, computed by code', CODE);
      await show('#decisive-first .check-line', { scale: 1.4, zoomMs: 2200, at: 0.4, driftMs: dur });
      await glide('#decisive-first .check-line', { fx: 0.5, ms: 900 });
    });
    await beat('L07', async (dur) => {
      caption('What would change the answer');
      await show('[data-demo="flips"]', { scale: 1.25, zoomMs: 2000, at: 0.42, driftMs: dur });
      await glide('[data-demo="flips"] tbody tr', { fx: 0.3, ms: 800 });
    });
    await beat('L08', async (dur) => {
      caption('AI read it, code verified it', { tag: 'AI + CODE' });
      await show('#decisive-first .prov-chip', { scale: 1.35, zoomMs: 2000, at: 0.4, pad: 8, driftMs: dur });
      await glide('#decisive-first .prov-chip', { ms: 900 });
    });
    await ringOff();
    await scan();
  },

  async where() {
    await s.scrollTo('#explainer', { at: 0.2, ms: 900 });
    mark('where');
    await beat('L09', async (dur) => {
      await show('.ex-ai', { scale: 1.12, zoomMs: 2000, at: 0.4, ringIt: false, driftMs: dur });
      const chips = [['planner', 'AI'], ['investigator', 'AI'], ['verifier', 'CODE'], ['rulecheck', 'CODE'], ['adjudicator', 'AI'], ['critic', 'AI']];
      caption('Six steps, four use a model', AI);
      const step = Math.max(600, (dur - 2000) / chips.length);
      for (const [c] of chips) {
        await ring(chip(c), { pad: 6 });
        await glide(chip(c), { fx: 0.5, fy: 0.4, ms: 500 });
        await sleep(step - 500);
      }
    });
    await ringOff();
  },

  async live() {
    await Promise.all([reset(600), ringOff()]);
    await page.evaluate(() => { location.hash = '#/'; });
    await sleep(600);
    await s.scrollTo('#explainer', { at: 0.2, ms: 600 });
    mark('live');
    await beat('L10', async () => {
      await s.scrollTo('#screen-details summary', { container: '.rail', at: 0.4, ms: 700 });
      if (!(await page.evaluate(() => document.getElementById('screen-details').open))) await click('#screen-details summary');
      await sleep(500);
      await fx('setRoot', '.rail', { clamp: false, raise: true });
      await page.evaluate(() => window.__fx.zoomTo(window.__fx.find('#run-form'), { scale: 1.6, ms: 1400, to: [330, 470] }));
      caption('Screen a new address');
      await s.typeInto('#address', ADDRESS, 62);
      if ((await page.inputValue('#address')) !== ADDRESS) throw new Error('address was not typed into the form');
      await click('#permits');
      await page.selectOption('#permits', 'no');
      await sleep(700);
    });
    await page.evaluate(() => { document.getElementById('run-btn').disabled = false; });
    await click('#run-btn');
    const tSubmit = s.nowMs();
    await reset(800);
    await fx('setRoot', 'main.center');
    await show('.ex-ai', { scale: 1.12, zoomMs: 1600, at: 0.42, ringIt: false, driftMs: 34000, drift: 0.09 });

    await waitChip('planner', ['active', 'done'], 20000);
    await beat('L11', async () => { await ring(chip('planner')); caption('Plans the checks', { ...AI, sub: 'Nemotron Ultra' }); await glide(chip('planner'), { fy: 0.4 }); });
    await waitChip('investigator', ['active', 'done'], 20000);
    await beat('L12', async () => { await ring(chip('investigator')); caption('Reads the county sources', { ...AI, sub: 'Nemotron Lightning' }); await glide(chip('investigator'), { fy: 0.4 }); });
    await waitChip('verifier', ['active', 'done'], 30000);
    await beat('L13', async () => { await ring(chip('verifier')); caption('Checks every quote', { ...CODE, sub: 'plain Python, no model' }); await glide(chip('verifier'), { fy: 0.4 }); });
    await beat('L14', async () => { await ring(chip('investigator')); caption('Long documents, small chunks', { tag: 'METERLESS', sub: 'Markovian engine' }); await glide(chip('investigator'), { fy: 0.7 }); });
    await beat('L15', async () => { await ring(chip('verifier')); caption('Failed quote: retry, then Ultra', { tag: 'RETRY', sub: 'Lightning empty, Ultra re-extracts' }); await glide(chip('verifier'), { fy: 0.7 }); });
    await beat('L16', async () => { await ring('.ex-foot', { pad: 8 }); caption('Every call: Nightshift receipt', { tag: 'METERLESS', sub: 'reference data: Zetaris' }); await glide('.ex-foot', { fx: 0.4, ms: 800 }); });
    await waitChip('critic', ['done'], 90000);
    await beat('L17', async () => { await ring(chip('critic')); caption('Ultra drafts, the critic pushes back', AI); await glide(chip('critic'), { fy: 0.4 }); });
    mark('live-done', `run ${((s.nowMs() - tSubmit) / 1000).toFixed(0)}s`);
    let shown = false;
    const reportUp = page.waitForSelector('#report-view:not([hidden]) #banner-verdict:not(:empty)', { timeout: 120000 }).then(() => { shown = true; });
    for (const name of ['adjudicator', 'critic', 'rulecheck', 'verifier'].concat(Array(12).fill('planner'))) {
      if (shown) break;
      await ring(chip(name), { pad: 6 });
      await glide(chip(name), { fx: 0.5, fy: 0.45, ms: 800 });
      await sleep(500);
    }
    await reportUp;
    await sleep(900);
    await beat('L18', async (dur) => {
      await ringOff();
      caption('Replay of recorded model answers');
      await show('#banner', { scale: 1.2, zoomMs: 2200, at: 0.3, driftMs: dur + 4000 });
      await glide('#banner', { fx: 0.82, fy: 0.3, ms: 900 });
    });
    await beat('L18b', async () => {
      caption('It says what is unconfirmed');
      await ring('#banner', { pad: 10 });
    });
    await ringOff();
    await scan();
  },

  async replay() {
    await pickSite('wash');
    await s.scrollTo('#explainer', { at: 0.2, ms: 900 });
    mark('replay');
    await beat('L19', async () => {
      caption('Replay how this verdict was built');
      await show('.ex-ai', { scale: 1.12, zoomMs: 1800, at: 0.42, ringIt: false, driftMs: 14000, drift: 0.06 });
      await ring('#ex-replay', { pad: 8 });
      await sleep(1200);
      await click('#ex-replay');
    });
    await waitChip('critic', ['active'], 15000);
    await beat('L20', async () => { await ring(chip('critic')); caption('Critic objects: six or twelve months?', AI); await glide(chip('critic'), { fy: 0.4 }); });
    await beat('L21', async () => {
      caption('Round 2, then code settles it', CODE);
      for (const name of ['rulecheck', 'verifier', 'rulecheck']) {
        await ring(chip(name), { pad: 6 });
        await glide(chip(name), { fx: 0.5, fy: 0.45, ms: 800 });
        await sleep(700);
      }
    });
    await sleep(800);
    await ringOff();
  },

  async flip() {
    await Promise.all([reset(600), ringOff()]);
    const mapReady = () => page.waitForFunction(() => document.querySelectorAll('.leaflet-tile-loaded').length >= 6, null, { timeout: 20000 });
    await pickSite('wash');
    mark('flip');
    await beat('L22a', async (dur) => {
      caption('Pause covers this site');
      await mapReady();
      await show('[data-demo="map"]', { scale: 1.12, zoomMs: 1800, at: 0.45, scrollMs: 1000, ringIt: false, driftMs: dur });
      await ring('#map-chip', { pad: 8 });
      await glide('#map-chip', { ms: 800 });
    });
    await pickSite('hag');
    await beat('L22', async (dur) => {
      caption('Same county, city limits: Conditional');
      await mapReady();
      await show('[data-demo="map"]', { scale: 1.12, zoomMs: 1800, at: 0.45, scrollMs: 1000, ringIt: false, driftMs: dur });
      await ring('#map-chip', { pad: 8 });
      await glide('#map-chip', { ms: 800 });
      await sleep(3500);
      await ringOff();
      await show('#banner', { scale: 1.2, zoomMs: 2200, at: 0.3, driftMs: 6000 });
      await glide('#banner', { fx: 0.82, fy: 0.3, ms: 900 });
    });
    await ringOff();
  },

  async abilene() {
    await pickSite('tx50');
    mark('abilene');
    await beat('L23', async (dur) => {
      caption('50 MW: two Texas rules stop applying');
      await show('#banner', { scale: 1.15, zoomMs: 2000, at: 0.3, driftMs: 3000 });
      await sleep(3200);
      await show('[data-demo="flips"]', { scale: 1.25, zoomMs: 2200, at: 0.42, driftMs: dur });
      await glide('[data-demo="flips"] tbody tr', { fx: 0.3, ms: 900 });
    });
    await ringOff();
  },

  async trace() {
    await pickSite('wash');
    mark('trace');
    await page.evaluate(() => {
      document.getElementById('disclosure-checked').open = true;
      const c = [...document.querySelectorAll('#checked-catches .catch')].find((e) => /180\s*→\s*182/.test(e.innerText));
      if (c) c.setAttribute('data-vid', 'c182');
    });
    await beat('L23b', async (dur) => {
      caption('Verifier recomputes: 180 to 182 days', CODE);
      await show('[data-vid="c182"]', { scale: 1.3, zoomMs: 2200, at: 0.42, scrollMs: 1100, driftMs: dur });
      await glide('[data-vid="c182"]', { fx: 0.5, ms: 900 });
    });
    await beat('L24', async (dur) => {
      caption('Every call: model and receipt', { tag: 'NIGHTSHIFT' });
      await show('[data-demo="lanes"] .lanes-summary', { scale: 1.35, zoomMs: 2200, at: 0.4, scrollMs: 1100, driftMs: dur });
      await glide('[data-demo="lanes"] .lanes-summary', { fx: 0.4, ms: 900 });
    });
    await ringOff();
  },

  async usl() {
    await s.goto(TERM);
    await fx('setRoot', 'body');
    mark('usl', TERM);
    await beat('L25', async (dur) => {
      caption('Zetaris: one semantic layer', { tag: 'ZETARIS' });
      await page.evaluate(([lines]) => window.termRun('type', 'zetaris — unified semantic layer', lines, 230), [USL_LINES]);
      await page.waitForFunction(() => window.__termDone === true, null, { timeout: 60000 });
      const last = '#term div:last-child span';
      await ring(last, { pad: 10 });
      await show(last, { scale: 1.3, zoomMs: 2200, at: 0.5, driftMs: Math.max(0, dur - 7000) });
      await glide(last, { fx: 0.5, ms: 800 });
    });
    await ringOff();
  },
};

const ORDER = ['get', 'report', 'where', 'live', 'replay', 'flip', 'abilene', 'trace', 'usl'];
const only = (process.env.SEGMENTS || ORDER.join(',')).split(',');
const todo = ORDER.filter((n) => only.includes(n));
if (todo[0] !== 'usl') {
  await s.goto(BASE + '/');
  await page.waitForSelector('#explainer .ex-tile', { timeout: 20000 });
  await page.waitForSelector('#portfolio li', { timeout: 20000 });
  await page.waitForSelector('#report-view:not([hidden]) #banner-verdict:not(:empty)', { timeout: 20000 });
  await sleep(1200);
}
const trimStartMs = s.nowMs();
for (const name of todo) {
  console.log(`[${(s.nowMs() / 1000).toFixed(1)}s] segment ${name}`);
  await SEG[name]();
}
const trimEndMs = s.nowMs() + 400;
await sleep(400);
const videoPath = await s.close();
renameSync(videoPath, OUT + '/take.webm');
writeFileSync(OUT + '/shots.json', JSON.stringify({ trimStartMs, trimEndMs, cues: s.cues, log: s.log, base: BASE }, null, 2));
console.log('take:', OUT + '/take.webm', `${((trimEndMs - trimStartMs) / 1000).toFixed(1)}s`);
console.log('pageerrors:', s.pageErrors.length ? s.pageErrors : 'none');
if (s.pageErrors.length) process.exit(1);
