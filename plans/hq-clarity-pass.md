# hq-clarity-pass — Work Plan

## TL;DR (For humans)

**What you'll get:** When someone opens SiteWhy, the top of the screen says in one line what it does, followed by three steps showing how it works. The key phrase in each source quote is highlighted and the key numbers are in bold. The look switches to light neo-brutalism: cream background, thick black borders, hard shadows, a yellow verdict panel. The guided tour opens with an intro card. It then shows a step list and explains each step as "what you're looking at / why it matters". It closes with a "try it yourself" card.

**Why this approach:** Your five complaints come down to three gaps. The page never says what the app is. Every word carries the same weight, so nothing guides the eye. The tour points at things without explaining them. Each fix targets one gap. Highlighting is driven by data fields, so no fact is hard-coded. The theme is the light version you picked from the previews.

**What it will NOT do:** It won't touch the backend, the agents or the samples. It won't add new map layers or web fonts. It won't push, publish or submit anything.

**Effort:** Medium (about 5 hours of work across 3 lanes)
**Risk:** Medium. Moving from a dark to a light theme can leave behind colour combinations that are hard to read (map chip, place labels, print), so we fix whatever the screen check finds.
**Decisions to sanity-check:**
- The full-page first-visit guide and the "?" button are removed; the always-visible framing strip replaces them.
- One small line in the strip names Nemotron (via Nightshift) and Zetaris.
- The tour's anchored callout card is cut for time; a stronger caption bar takes its place.

Your next move: type `/litclaude:start-work plans/hq-clarity-pass.md` to approve the plan and start it.

---

> TL;DR (machine): Medium, Medium risk. N1 light neo-brutalism tokens + framing strip + data-driven emphasis + demo-roll overhaul (intro, rail, LOOK/WHY captions, dim, outro); 4 todos + F1–F4.

Input: `.litclaude/evidence/clarity-crucible/PACKET.md` (+ `lane-a-first5s.md`, `lane-b-text-emphasis.md`, `lane-c-visual-demo.md`). User decision 10/27: theme C Light brutal (preview `scratchpad/brutal-preview/C-light.png`; CSS used for the preview is reproduced in Todo 1).

## Bootstrap and PIN
- Objective: cold load of `#/site/md-washington-county-unincorporated` at 1440x800 shows (a) a one-line value statement and the 3-step strip, (b) verdict word, headline, decisive rule title and the quote with one highlighted key phrase, all without scrolling; the theme is N1; "▶ Watch the 75-second tour" plays intro → 8 steps → outro unattended and a viewer can name each step from the rail.
- Start commit: `dc443f6`. Dirty: untracked `.litmuse/`, `scripts/fetch_warm.py` (never stage).
- Server: herdr pane `server` (w2W:p1S) serves `web/` statically; do not kill it.
- Commits: todo-level commits approved by the user (standing rule); stage only own files; no AI attribution, no Co-Authored-By, no session links. Push/publish forbidden.
- Goal tools: none exposed. Workflow tool: not used; herdr muse lanes `theme`, `ux`, `demo` (orchestrator spawns them fresh with `herdr agent start <name> --kind muse --pane <id> -- --yolo`). Worktrees: none; lanes own disjoint files per todo.
- Worker brief: `.litclaude/evidence/hq-demo-roll/BRIEF.md` rules apply with this plan replacing that one; evidence to `.litclaude/evidence/hq-clarity-pass/task-<N>.txt`; telemetry `T<N> DONE <sha> <tests> <note>` | `T<N> BLOCKED <reason>`.
- Known harness issue: muse panes stall on "macOS Keychain didn't answer"; orchestrator re-prompts and sends Enter until the agent is `working`.

## Scope
### Must have
- N1 tokens and brutalist component rules; verdict word always paired with colour; all text ≥ 4.5:1.
- Static framing strip (value line, 3 steps, sponsor line) visible without localStorage, above the fold at 1440x800 and 390.
- Data-driven `<mark>` in decisive quotes, bold numbers in RULE/CHECK, headline without repeated verdict prefix.
- Demo roll: intro card, step rail, LOOK/WHY captions, sibling dim, prominent bar, outro card.
- Existing contracts: 9 `data-demo` anchors, `window.SiteWhy`, deep links `#/site/<name>` `#/run/<id>` `#/demo`, print brief (light), SAMPLE_MODE behaviour, reduced motion, Esc/Space/arrows.
### Must NOT have (guardrails, anti-slop, scope boundaries)
- No backend, sample, agent or test-fixture edits; no network fonts; no new map layers.
- No hard-coded report facts in captions, marks or strip (fixed step titles, LOOK lines and strip copy are allowed).
- No full-screen overlay that intercepts Leaflet pointer events.
- No push, publish, GitHub repo creation or HackOS submission.

## Verification strategy
> Zero human intervention — every verification step is agent-executed.
- Test decision: tests-after for front end (no web tests in `tests/`); RED/GREEN as browser assertion scripts (playwright via `~/.npm/_npx/705bc6b22212b352/node_modules/playwright` with `channel: 'chrome'`, or claude-in-chrome when connected) recorded in `task-<N>.txt`. `uv run pytest -q` + `uv run ruff check .` stay green.
- Manual-QA channel: browser (headless Chrome screenshots + claude-in-chrome F3 when the extension is connected).
- Evidence: `.litclaude/evidence/hq-clarity-pass/task-<N>.txt` + `task-<N>/` screenshots; F-wave files `F1-probe/`, `F2-review.md`, `F3-qa.md`, `F4-scope.txt`.

## Execution strategy
### Parallel execution waves
- Wave 1: Todo 1 (theme lane) ∥ Todo 4 (demo lane, demo.js/demo.css only).
- Wave 2 (after Todo 1 commit): Todo 2 (ux lane) then Todo 3 (ux lane, same files, sequential).
- Wave 3: Todo 4 final verification against Todo 2/3 layout; Todo 5 bookkeeping; F1–F4.

### Dependency matrix
| Todo | Depends on | Blocks | Can parallelize with |
| --- | --- | --- | --- |
| 1 Theme N1 | — | 2, 3 | 4 |
| 2 Framing strip | 1 | 3, 4-final | 4 |
| 3 Emphasis | 2 | 4-final | 4 |
| 4 Demo roll overhaul | code: —; final verify: 2, 3 | F | 1, 2, 3 |
| 5 Bookkeeping | 1–4, F1–F4 | — | — |

## Todos
> Implementation + Test = ONE todo. Never separate them.
> Rows start at column zero as `- [ ] N. <title>`; start-work cannot see an indented row.
<!-- APPEND TASK BATCHES BELOW THIS LINE — never rewrite the headers above. -->
- [x] 1. Light neo-brutalism theme (lane `theme`) — 77bf2ec
  What to do / Must NOT do: In `web/app.css` only, replace `:root` tokens with N1 (bg #FAF5EB, panel #FFFFFF, panel-2 #FFFFFF or #F3EDE0, rule/line #111111, ink #111111, ink-2 #4A4A4A, accent #FF6B35, accent-ink #111111, no-go #D32F2F, conditional/amber #F9A825, ok/go #2E7D32, grey/unknown #757575, new `--highlight:#FFF176`, `--shadow:#111111`, `--banner:#FFF176`, color-scheme light). Apply brutalist rules: 3px solid borders, radius 0, `box-shadow:5px 5px 0 var(--shadow)` on `.banner .decisive .disclosure .map-wrap .site-row .lamp` and rail buttons; square verdict dots 18px with 2px border; verdict line 30px/900; h1 28px/900; decisive h3 18px/900; h2 with 3px bottom rule in ink. Verdict chips: white text on no-go/go/unknown fills, ink on conditional. Re-tune dark-era leftovers: `.chip`, `.city-label`, `.map-fallback`, `.mist` tags, code/estimate chips, focus rings, Leaflet control panels, `@media print` (stays light). Do NOT edit `web/demo.css`, `web/app.js`, `web/index.html`.
  Parallelization: Wave 1 | Blocked by: — | Blocks: 2, 3
  References: `web/app.css:1-30` (tokens), `:67-73` site-row, `:79-91` map/chip/fallback, `:103-110` lamps, `:130-165` disclosure/banner/decisive, `:215-233` print, `:249-251` city-label; preview CSS `/private/tmp/claude-501/-Users-woojin-Desktop-00-INBOX-2026-10-Open-Agent-Hackathon-2026--GenAI-Works-/0544c0ac-6c4a-4bad-9a8a-0cd3007315b4/scratchpad/brutal-preview/C-light.css` + `common.css`; contrast table `.litclaude/evidence/clarity-crucible/lane-c-visual-demo.md` (N1).
  Acceptance criteria: contrast table for every text/fill pair in `task-1.txt`, all ≥ 4.5:1 text, ≥ 3:1 dots/borders; `grep -n "#0b1416\|#15272c" web/app.css` returns nothing; 1440 screenshot matches the C-light preview look; pytest + ruff green.
  QA scenarios: headless screenshots at 1440 and 390 of Washington and Tucson, plus map with Satellite/Streets/Dark basemaps (chip readable on each), plus print emulation (`page.emulateMedia({media:'print'})`); failure case: tiles blocked → `.map-fallback` readable. Evidence `.litclaude/evidence/hq-clarity-pass/task-1/`.
  Commit: Y | `style(ui): light neo-brutalism theme with hard borders and shadows`

- [x] 2. Framing strip and first-view cleanup (lane `ux`) — e91b57c
  What to do / Must NOT do: In `web/index.html`, `web/app.js`, `web/app.css` (layout rules only, after Todo 1 is committed; re-read before editing):
  - Replace the tagline with the value line "Screen any US address for data center rules — and see why."
  - Add a static `<section id="how" data-ui-moment>` at the top of the centre column (above `#report-view`, static HTML, no JS, no localStorage): three numbered cells "1 Pick a site or enter an address" / "2 AI agents check federal, state and local rules" / "3 Get a verdict with cited, verified sources", and one small line "Powered by NVIDIA Nemotron via Nightshift · data in Zetaris · Meterless engines". On 390 it stacks; it must sit above the verdict banner and keep the banner + decisive title above the fold at 1440x800 (compact: ≤ 96px tall at 1440).
  - Remove the full-page guide (`#guide`, `showGuide`/`hideGuide`/`dismissGuide`/`guideDismissed` logic and the "?" `#guide-open` button); move the glossary entries into the status-key legend; `bootPortfolio` always opens the first showcase site (or the hash target). Keep `#/demo` early return.
  - Rename the tour button text to "▶ Watch the 75-second tour" (id `demo-roll` unchanged).
  - Keep all 9 `data-demo` anchors and `window.SiteWhy` unchanged; add `data-demo="how"` on the strip (10th anchor, used by Todo 4's intro step).
  Must NOT: touch `web/demo.js`, `web/demo.css`, theme tokens.
  Parallelization: Wave 2 | Blocked by: 1 | Blocks: 3, 4-final
  References: `web/index.html:15-21,53-62,68-81`; `web/app.js:29-40,84-90,829-833,941-943,959-969`; `.litclaude/evidence/clarity-crucible/lane-a-first5s.md`.
  Acceptance criteria: in a fresh browser context (empty localStorage) and in a context with the old dismissed key, the strip is visible above the fold at 1440x800 and 390x844; `document.querySelectorAll('[data-demo]').length === 10` after Washington loads; no `#guide`/`guide-open` left in `web/`; deep links `#/site/az-tucson-pima`, `#/demo` work; 4 samples render with 0 console errors; pytest + ruff green.
  QA scenarios: headless playwright script RED (strip absent) → GREEN; screenshots 1440/390/320. Evidence `.litclaude/evidence/hq-clarity-pass/task-2/`.
  Commit: Y | `feat(ui): framing strip says what SiteWhy does before the answer`

- [x] 3. Data-driven emphasis (lane `ux`, after 2) — 2ea8cca
  What to do / Must NOT do: In `web/app.js` and `web/app.css`:
  - `markKeyPhrase(escapedQuote, field, parameters)`: field `duration_days` → number-word/digit + optional "(n)" + months|days|weeks|years; `effective` → written date; `scope` → `parameters.scope` literal or jurisdiction county/place name; null/other → generic quantity regex (tpy, MW, megawatts, kV, kW, %, days, months). Wrap the FIRST match in `<mark>`; no match → unchanged. Apply in `evItem()` after `esc()`.
  - Bold (`<strong>`) dates `YYYY-MM-DD` and quantities in RULE and CHECK lines (escape first, then wrap).
  - Headline: if `explanation.headline` starts with the verdict word + ":", drop that prefix and render the rest in `<strong>` (escaped).
  - Type tiers in the first view: L verdict, M 15–16px body (decisive h3, quote, RULE/CHECK/RESULT), S 12px mono metadata; quote `max-width:65ch`; `mark{background:var(--highlight);color:var(--ink);padding:0 3px}`.
  Must NOT: hard-code any phrase; change JSON; touch demo files.
  Parallelization: Wave 2 | Blocked by: 2 | Blocks: 4-final
  References: `web/app.js:498-500` (evItem), `:583-602` (projectLine/decisiveCard), `:799` (headline); `.litclaude/evidence/clarity-crucible/lane-b-text-emphasis.md` (field → regex table; per-sample expected marks: Washington "six (6) months", Hagerstown/Tucson "100 tpy", Abilene "75 megawatts").
  Acceptance criteria: browser script asserts exactly one `mark` in each sample's first decisive quote with the expected text above (or records the actual match and why); `<strong>` present in Washington CHECK line around both dates; headline text no longer starts with "No-go:"; no `undefined`/`null` rendered; pytest + ruff green.
  QA scenarios: 4 samples × 1440 screenshots; failure case: a quote with no number → no mark, no error (inject via a copied report object in the page, not by editing samples). Evidence `.litclaude/evidence/hq-clarity-pass/task-3/`.
  Commit: Y | `feat(ui): highlight the verified phrase and key numbers in each answer`

- [x] 4. Demo roll overhaul (lane `demo`) — 62ae981
  What to do / Must NOT do: In `web/demo.js` and `web/demo.css` only:
  - Intro card (step 0, anchor `how` when present, else no highlight): "A 75-second tour of how SiteWhy decides" + one line "8 stops · auto-advances · Space pauses · Esc exits".
  - Step rail inside the bar: 8 fixed short titles — Pick a site · The verdict · On the map · The rule that decides · Agents double-check · Who did the work · What would change it · Another grid; states current/done/upcoming; clicking a title jumps (cut first if late).
  - Caption = two lines: `LOOK:` fixed per step (e.g. "the yellow verdict panel at the top") and `WHY IT MATTERS:` a template filled from report fields (existing caption functions supply the facts).
  - Dim: while running, add `body.demo-running` and set `opacity:.35` on `[data-demo]` sections that are not the current target (and on `.rail` sections), restoring on exit; no overlay element; reduced motion → no transition.
  - Bar: N1 look (3px ink border top, hard shadow, accent progress, 16–17px caption, bold LOOK/WHY labels), max height ~40% viewport on 390 with scroll inside.
  - Outro card: "That's SiteWhy: verdict, the rule behind it, and the agents that checked it." + button "Try another site" that exits and focuses the portfolio (live mode: the address input).
  - Keep: epoch guard, Esc/Space/arrows rules, click-outside pause, `#/demo` start, hash restore, only `GET /samples*`, offline tiles, total ≤ 90 s.
  Parallelization: Wave 1 (code) | Blocked by: 2, 3 for final verification only | Blocks: F
  References: `web/demo.js:42-95` (captions/STEPS), `:150-200` (show/highlight/timer), `:269-313` (start/exit); `web/demo.css`; `.litclaude/evidence/clarity-crucible/lane-c-visual-demo.md` Part 2 table (titles, LOOK/WHY).
  Acceptance criteria: unattended `#/demo` run logs intro + 8 steps + outro in order, each caption has non-empty LOOK and WHY with no `undefined`/`null`, rail shows exactly 8 titles, non-target anchors have opacity < 0.5 during the run and 1 after exit, hash restored; same run with tile hosts blocked completes; Esc mid-roll restores; re-record `.litclaude/evidence/hq-clarity-pass/demo-roll.gif`; pytest + ruff green.
  QA scenarios: headless playwright script (normal, tiles blocked, Esc), GIF via frame capture. Evidence `.litclaude/evidence/hq-clarity-pass/task-4/`.
  Commit: Y | `feat(ui): demo roll explains each stop with a step rail, intro and outro`

- [x] 6. Section nav sidebar with scrollspy and collapse (lane `nav` → ran on `demo`, muse) — 09ae3ac — spec, acceptance and commit in `.litclaude/evidence/hq-clarity-pass/FEATURES.md` Todo 6. Files `web/nav.js`, `web/nav.css`.
- [x] 7. Ctrl+K command palette (lane `palette` → ran on `chain`, muse) — f36f7e9 — FEATURES.md Todo 7. Files `web/palette.js`, `web/palette.css`.
- [x] 8. Demo roll speed, pause badge, key hints (lane `demo` → finished on `chain`, muse) — 95b806c — FEATURES.md Todo 8. Files `web/demo.js`, `web/demo.css`.
- [x] 9. Why chain (lane `chain`, muse) — 45797c4 — FEATURES.md Todo 9. Files `web/chain.js`, `web/chain.css`.
- [x] 10. Agent lanes "Who did the work" (lane `lanes` → ran on `settings`, muse) — 64ded17 — FEATURES.md Todo 10. Files `web/lanes.js`, `web/lanes.css`.
- [x] 11. Settings: density, motion, term hints (lane `settings`, muse) — 741cb98 — FEATURES.md Todo 11. Files `web/settings.js`, `web/settings.css`.
  Lane change 10/27: the three Claude Code sonnet panes stalled at start and were closed (user: kill lanes that are not useful); Todo 6 runs on `demo` after 8, Todo 7 on `chain` after 9, Todo 10 on `settings` after 11.
  Shared for 6–11: user request 10/27 ("Proceed all the ideas in parallel"); orchestrator added the `sitewhy:report` event, `SiteWhy.current()/sites()` and linked stub files beforehand. UI freeze 18:00 KST; unfinished add-ons are dropped (unlink tag) rather than shipped half-done. Excluded by decision: site compare, interactive counterfactual, voice narration.

- [x] 5. Bookkeeping (orchestrator)
  What to do: tick rows 1–4, 6–11 and F1–F4 here; add one line under `plans/roadmap.md` M3 for the clarity pass; append a Results section (commits, F verdicts, known limitations).
  Parallelization: last | Blocked by: 1–4, F1–F4 | Blocks: —
  References: `plans/roadmap.md` M3 section; `plans/hq-demo-roll.md` Results section as the format model.
  QA scenarios: `grep -c` check above; `git status --short` shows only untracked `.litmuse/` and `scripts/fetch_warm.py` after the commit.
  Acceptance criteria: `grep -c "^- \[x\]" plans/hq-clarity-pass.md` = 15.
  Commit: Y | `docs(plan): record clarity pass results`

## Final verification wave
> Runs in parallel after ALL todos. ALL must APPROVE. Surface the results, then complete the work; a commit and push still ask first.
- [x] F1. Plan compliance audit (exit 0, Approve, 0 HIGH; 390 strip gutter fixed after the look round) — interface probe `node ~/.litclaude/marketplaces/litclaude-ai/plugins/litclaude/skills/frontend-ui-ux/scripts/interface-probe.mjs "http://localhost:8000/#/site/md-washington-county-unincorporated" --out .litclaude/evidence/hq-clarity-pass/F1-probe` exit 0 (0 HIGH) at 320/390/768/1440, reduced motion, 200% zoom; orchestrator looks at 320/390/1440 screenshots.
- [x] F2. Code quality review (5 P1 found and fixed, 0 P0/P1 open; P2 limitations listed in F2-review.md) — `litclaude:quality-reviewer` on `git diff dc443f6..HEAD -- web/`; no P0/P1; `F2-review.md`.
- [x] F3. Real Manual-QA (16/16 PASS on 4fc27ee, 0 bugs; re-run after F2 fixes recorded in F3-qa.md) — claude-in-chrome (headless playwright if the extension is disconnected): (1) cold load 1440x800 fresh profile: strip + verdict + rule title + marked quote above the fold; (2) unattended tour intro→outro; (3) Space/arrows/row click/Esc mid-roll; (4) `#/demo` deep link; (5) all 4 samples; (6) 390 width; (7) print preview light and readable. PASS/FAIL per scenario in `F3-qa.md` with screenshots.
- [x] F4. Scope fidelity (PASS: web/ only, no hard-coded facts) — `git diff --stat dc443f6..HEAD` touches only `web/*` and `plans/*`; no hard-coded facts (`grep -n "six (6)\|100 tpy\|75 megawatts\|Washington County" web/*.js` returns nothing); `F4-scope.txt`.

## Commit strategy
One commit per todo with the messages above (approved standing rule), plus fix commits named `fix(ui): <what>` if F2/F3 require them. Stage only the todo's files. No push.

## Stop rules
- Stop and report BLOCKED on: a needed field missing from samples; the server pane dying twice; the same failure three times; any step needing push/publish; contradiction between this plan and live samples.
- Cut order if late: outro card → rail click-to-jump → sponsor line → RULE/CHECK bolding. Never cut: theme, framing strip, quote mark, LOOK/WHY captions.

## Success criteria
DoneClaim:
- 4 feature commits + bookkeeping commit; pytest and ruff green; probe exit 0; F2 no P0/P1; F3 7/7 PASS; F4 clean; new `demo-roll.gif`; lanes closed and server health 200; receipt "no push, no publish".

## Results (10/27)
- Commits (dc443f6..): 77bf2ec theme · 62ae981 tour rail/intro/outro · 7d90163 add-on event + slots · 741cb98 settings · 45797c4 why chain · e91b57c framing strip · f36f7e9 Ctrl+K palette · 64ded17 agent lanes · 09ae3ac section nav · 2ea8cca highlighted phrase + bold figures · 95b806c tour speed/pause/hints · 4fc27ee strip gutter fix · 8c357bc review fixes.
- Scope grew by user request ("Proceed all the ideas in parallel"): Todos 6–11 added. Excluded by decision: site compare, interactive counterfactual, voice narration.
- Lanes: muse ux/demo/chain/settings did all work; three Claude Code sonnet lanes stalled at start and were closed.
- F1 probe exit 0, Approve, 0 HIGH (one look-round fix: 390 strip gutter). F2 5 P1 fixed, 0 P0/P1 open. F3 16/16 PASS (11 scenarios, incl. print, palette, settings, nav), re-run 16/16 after fixes; F2-fix checks 8/8. F4 PASS. pytest 153 passed, ruff clean. GIF re-recorded (`.litclaude/evidence/hq-clarity-pass/demo-roll.gif`).
- Known limitations (F2 P2): motion setting is CSS-only; collapsed rail hides portfolio/settings/search; term-hint verdict words match case-insensitively and need Safari ≥ 16.4; tour step 6 spotlights the trace, not the agent lanes; dead guide CSS left; no front-end tests.
- No push, no publish.
