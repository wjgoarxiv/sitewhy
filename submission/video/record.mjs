// Final-take recorder. Usage: node record.mjs OUT_DIR
// Chrome 1920x1080, recordVideo, scripted shots mirroring script.md.
// Pre-step runs a REAL screening (uv run run.py --sample); the terminal
// shots replay that run's actual trace bytes (waiting cut, output unedited).
// Writes OUT_DIR/take.webm + OUT_DIR/shots.json (per-shot video timestamps).
import { spawnSync } from 'node:child_process';
import { createRequire } from 'node:module';
import { mkdirSync, readFileSync, writeFileSync } from 'node:fs';

const require = createRequire(import.meta.url);
const { chromium } = require(process.env.PLAYWRIGHT_MJS ||
  '~/.npm/_npx/705bc6b22212b352/node_modules/playwright/index.mjs');
import { fileURLToPath } from 'node:url';
import { dirname, resolve } from 'node:path';

const BASE = 'http://localhost:8000';
const HERE = dirname(fileURLToPath(import.meta.url));
const ROOT = resolve(HERE, '..', '..');
const OUT = resolve(process.argv[2] || '/tmp/sitewhy-take2');
mkdirSync(OUT, { recursive: true });
const ARCH = 'file://' + HERE + '/architecture.html';
const TERM = 'file://' + HERE + '/terminal.html';
const sleep = (ms) => new Promise((r) => setTimeout(r, ms));
const shortModel = (m) => String(m || '').replace(/^nvidia\//, '');

// Pre-step: one real sample-mode run; its trace is what the video shows.
const run = spawnSync('uv', ['run', 'python', 'run.py',
  '--input', 'input_examples/md-washington-county-unincorporated.json',
  '--sample', '--output', '/tmp/t7-final-report.json',
  '--logs-dir', '/tmp/t7-final-logs'],
  { cwd: ROOT, encoding: 'utf-8', timeout: 280000 });
if (run.status !== 0) throw new Error('run.py failed: ' + (run.stderr || '').slice(-500));
const traceFiles = [];
try {
  const { readdirSync } = await import('node:fs');
  for (const f of readdirSync('/tmp/t7-final-logs')) if (f.endsWith('.jsonl')) traceFiles.push(f);
} catch { /* handled below */ }
if (!traceFiles.length) throw new Error('no trace jsonl from run.py');
traceFiles.sort();
const trace = readFileSync('/tmp/t7-final-logs/' + traceFiles[traceFiles.length - 1], 'utf-8')
  .split('\n').filter(Boolean).map((l) => JSON.parse(l));
const report = JSON.parse(readFileSync('/tmp/t7-final-report.json', 'utf-8'));
const clip = (s, n) => { const t = String(s || '').replace(/\s+/g, ' '); return t.length > n ? t.slice(0, n - 1) + '…' : t; };

const RUN_LINES = ['$ python run.py --input input_examples/md-washington-county-unincorporated.json --sample'];
{
  const t0 = new Date(trace[0].timestamp).getTime();
  const keep = trace.filter((e) => !['state_watch', 'seeded'].includes(e.action)).slice(0, 12);
  for (const e of keep) {
    const dt = ((new Date(e.timestamp).getTime() - t0) / 1000).toFixed(1);
    RUN_LINES.push(`[${dt}s] ${e.agent_name}.${e.action} -> ${e.target_agent || '—'} [${shortModel(e.model) || 'code'}] ${clip(e.output_summary, 64)}`);
  }
  const roles = new Set(trace.map((e) => e.agent_name)).size;
  RUN_LINES.push(`verdict: ${report.verdict} · ${trace.length} trace lines · ${roles} roles · exit 0`);
}
let CRITIC_LINES = ['$ events 19-21 · md-washington-county-unincorporated.json'];
let CRITIC_IDX = '19→20→21';
{
  const ci = trace.findIndex((e) => e.agent_name === 'critic' && /objection/i.test(e.action || ''));
  if (ci < 0) throw new Error('no critic objection in fresh trace');
  const pi = trace.findIndex((e, i) => i > ci && e.agent_name === 'planner');
  const ii = trace.findIndex((e, i) => i > ci && /investigator/.test(e.agent_name || ''));
  if (pi < 0 || ii < 0) throw new Error('no round-2 re-plan after the critic objection');
  CRITIC_IDX = `${ci}→${pi}→${ii}`;
  const obj = trace[ci];
  const catch0 = ((report.explanation || {}).catches || []).find((c) => c.actor === 'critic');
  const why = catch0 ? clip(catch0.text, 120) : clip(obj.output_summary, 120);
  CRITIC_LINES = [
    `$ critic objection carried the run into round 2 (trace lines ${CRITIC_IDX})`,
    `round 1 · critic.objections [${shortModel(obj.model)}]`,
    `  "${why}"`,
    `  → outcome: ${catch0 ? catch0.outcome : 'round 2'}`,
    `round 2 · planner.targeted_tasks → county_investigator`,
    `round 2 · county_investigator re-investigation (second pass on the same rule)`,
  ];
}
const USL_LINES = ['$ cat zetaris/usl.sql + evidence (committed files, shown verbatim)'];
{
  const sql = readFileSync(ROOT + '/zetaris/usl.sql', 'utf-8').split('\n')
    .filter((l) => l.trim() && !l.startsWith('--')).slice(0, 6).map((l) => '  ' + l.trim().slice(0, 88));
  const uq = JSON.parse(readFileSync(ROOT + '/zetaris/evidence/usl_queries.json', 'utf-8'));
  const dq = JSON.parse(readFileSync(ROOT + '/zetaris/evidence/dq_rule.json', 'utf-8'));
  USL_LINES.push(...sql);
  USL_LINES.push(...uq.queries.map((q) => `  ${q.name} → ${q.row_count} rows`));
  USL_LINES.push(`  dq ${dq.name}: ${dq.passed ? 'PASS' : 'FAIL'} (${dq.violation_count} violations)`);
}
for (const text of [...RUN_LINES, ...CRITIC_LINES, ...USL_LINES]) {
  if (/nvapi-|sk-|Bearer\s+[A-Za-z0-9]|PROXY_TOKEN|ZETARIS_API_KEY/i.test(text)) throw new Error('secret pattern in terminal text');
}

const SHOTS = [
  { name: 'title', url: ARCH + '#title', dwell: 9000 },
  { name: 'arch', url: ARCH + '#arch', dwell: 14000 },
  { name: 'washington-decisive', site: 'md-washington-county-unincorporated', anchor: 'decisive', dwell: 18000 },
  { name: 'hagerstown-flip', site: 'md-hagerstown-city', anchor: 'banner', dwell: 12000 },
  { name: 'tour', tour: true, dwell: 0 },
  { name: 'critic-trace', term: { mode: 'show', title: 'trace — critic sends it back', lines: CRITIC_LINES }, dwell: 18000 },
  { name: 'live-run', term: { mode: 'play', title: 'run.py --sample · real run', lines: RUN_LINES }, dwell: 22000 },
  { name: 'lanes', site: 'md-washington-county-unincorporated', anchor: 'lanes', dwell: 10000 },
  { name: 'abilene50', site: 'tx-abilene-ercot-50mw', anchor: 'banner', dwell: 14000 },
  { name: 'usl', term: { mode: 'show', title: 'zetaris — unified semantic layer', lines: USL_LINES }, dwell: 10000 },
  { name: 'flips', site: 'tx-abilene-ercot-50mw', anchor: 'flips', dwell: 11000 },
  { name: 'outro', url: ARCH + '#outro', dwell: 6000 },
];

const browser = await chromium.launch({ channel: 'chrome' });
const ctx = await browser.newContext({
  viewport: { width: 1920, height: 1080 },
  recordVideo: { dir: OUT, size: { width: 1920, height: 1080 } },
});
await ctx.addInitScript(() => {
  try { localStorage.setItem('sitewhy-demo-speed', '2'); } catch { /* private mode */ }
});
const page = await ctx.newPage();
const pageErrors = [];
const consoleErrors = [];
page.on('pageerror', (e) => pageErrors.push(e.message));
page.on('console', (m) => { if (m.type() === 'error') consoleErrors.push(m.text().slice(0, 200)); });

await page.goto(BASE + '/', { waitUntil: 'load' });
await sleep(2000);

const log = [];
const t0 = Date.now();
const stamp = (name, url) => log.push({ name, tMs: Date.now() - t0, url });

for (const s of SHOTS) {
  if (s.tour) {
    await page.goto(BASE + '/#/demo', { waitUntil: 'load' });
    await page.waitForFunction(() => window.SiteWhyDemo, null, { timeout: 15000 });
    await page.waitForSelector('#demo-bar:not([hidden])', { timeout: 15000 });
    stamp('tour', '#/demo');
    await page.waitForFunction(() => !window.SiteWhyDemo.state.running, null, { timeout: 120000 });
    await sleep(1000);
    continue;
  }
  if (s.term) {
    await page.goto(TERM, { waitUntil: 'load' });
    await page.evaluate(({ mode, title, lines }) => window.termRun(mode, title, lines), s.term);
    await page.waitForFunction(() => window.__termDone === true, null, { timeout: 60000 });
    stamp(s.name, 'terminal:' + s.name);
    await sleep(s.dwell);
    continue;
  }
  const url = s.url || `${BASE}/#/site/${s.site}`;
  await page.goto(url, { waitUntil: 'load' });
  if (s.site) {
    await page.waitForSelector('.recorded-badge', { timeout: 20000 });
    await sleep(2500);
    if (s.anchor) {
      await page.evaluate((a) => {
        const el = document.querySelector(`[data-demo="${a}"]`);
        if (el) {
          const closed = el.closest('details:not([open])');
          if (closed) closed.open = true;
          el.scrollIntoView({ block: 'center' });
        }
      }, s.anchor);
      await sleep(800);
    }
  } else {
    await sleep(1500);
  }
  stamp(s.name, url);
  await sleep(s.dwell);
}

await ctx.close();
await browser.close();
writeFileSync(OUT + '/shots.json', JSON.stringify({ critic_idx: CRITIC_IDX, log }, null, 2));
console.log('critic idx:', CRITIC_IDX);
console.log('shots:');
for (const e of log) console.log(`  ${(e.tMs / 1000).toFixed(1)}s ${e.name} ${e.url}`);
console.log('pageerrors:', pageErrors.length ? pageErrors : 'none');
console.log('console errors:', consoleErrors.length ? consoleErrors : 'none');
if (pageErrors.length) process.exit(1);
