// Builds the intro and outro clips from the README motion cover.
// Usage: node cover.mjs OUT_DIR
// docs/img/cover.webp (1000x500, 200 frames at 25 fps = 8 s) is scaled to 1600x800 and centered on the
// cover's own background colour in a 1920x1080 frame; a caption PNG (rendered in Chrome, transparent) fades in.
import { spawnSync } from 'node:child_process';
import { createRequire } from 'node:module';
import { mkdirSync } from 'node:fs';
import { fileURLToPath } from 'node:url';
import { dirname, resolve } from 'node:path';

const require = createRequire(import.meta.url);
const { chromium } = require(process.env.PLAYWRIGHT_MJS || 'playwright');
const HERE = dirname(fileURLToPath(import.meta.url));
const ROOT = resolve(HERE, '..', '..');
const OUT = resolve(process.argv[2] || '/tmp/sitewhy-cover');
mkdirSync(OUT, { recursive: true });

const COVER = resolve(ROOT, 'docs/img/cover.webp');
const BG = '0x080d12';
const REPO = 'https://github.com/wjgoarxiv/sitewhy';
const CLIPS = [
  { name: 'intro', line: 'SiteWhy — check a site, see why', sub: 'Open Agent Hackathon 2026 · Track 2 · The Agent That Can Explain Why', accent: '#e8e4d6' },
  { name: 'outro', line: REPO, sub: 'SiteWhy — check a site, see why · built with Nemotron on Nightshift', accent: '#ff6a3d' },
];

const html = ({ line, sub, accent }) => `<!doctype html><meta charset="utf-8"><style>
  html,body{margin:0;width:1920px;height:1080px;background:transparent;overflow:hidden}
  .box{position:absolute;left:0;right:0;top:900px;text-align:center;font-family:ui-monospace,Menlo,monospace}
  .l{font-size:${line.length > 40 ? 50 : 58}px;font-weight:700;letter-spacing:1px;color:${accent}}
  .s{font-size:28px;letter-spacing:3px;color:#8b98a8;margin-top:14px;text-transform:uppercase}
</style><div class="box"><div class="l">${line}</div><div class="s">${sub}</div></div>`;

const browser = await chromium.launch({ channel: 'chrome' });
const page = await browser.newPage({ viewport: { width: 1920, height: 1080 } });
for (const c of CLIPS) {
  await page.setContent(html(c));
  await page.screenshot({ path: `${OUT}/${c.name}-caption.png`, omitBackground: true });
}
await browser.close();

for (const c of CLIPS) {
  const args = ['-v', 'error', '-y', '-i', COVER, '-loop', '1', '-framerate', '25', '-i', `${OUT}/${c.name}-caption.png`,
    '-filter_complex',
    `[0:v]fps=25,scale=1600:800:flags=lanczos,pad=1920:1080:160:70:color=${BG}[bg];` +
    '[1:v]format=rgba,fade=in:st=0.15:d=0.5:alpha=1[cap];[bg][cap]overlay=0:0:shortest=1,format=yuv420p[v]',
    '-map', '[v]', '-t', '8', '-c:v', 'libx264', '-preset', 'medium', '-crf', '18', '-r', '25', `${OUT}/${c.name}.mp4`];
  const r = spawnSync('ffmpeg', args, { encoding: 'utf-8' });
  if (r.status !== 0) throw new Error(`ffmpeg ${c.name}: ${r.stderr}`);
  console.log(`wrote ${OUT}/${c.name}.mp4`);
}
