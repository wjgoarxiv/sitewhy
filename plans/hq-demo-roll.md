# Plan: SiteWhy HQ — demo roll, Midnight Ops theme, answer-first layout

> TL;DR: Front-end only. One "▶ Demo roll" walks a judge through the app in about 75 s. The screen shows the answer first and puts evidence one click away. The theme is Midnight Ops. Three herdr muse lanes, 4 todos plus F1–F3. Internal deadline 2026-10-27 22:00 KST.

Input: `.litclaude/evidence/ui-crucible/PACKET.md`, with `ux.md`, `demo.md` and `theme.md` in the same folder. All three were decided with the user on 10/27:
- automatic tour
- answer first, evidence on click
- Midnight Ops theme

## Bootstrap and PIN

- **Objective:** from a cold load of `#/site/md-washington-county-unincorporated` at 1440x800, a judge sees the verdict word, the decisive rule title and its quote above the fold with no click. Pressing "▶ Demo roll" plays 7 steps unattended and ends cleanly.
- **Non-goals:**
  - backend or agent logic changes
  - new samples or re-recording
  - new map layers
  - network fonts
  - M4 docs
  - push, publish, HackOS submission
- **Dirty state:** untracked `.litmuse/` and `scripts/fetch_warm.py` are not ours; never stage them.
- **Server:** the app server runs in herdr pane `server` (w2W:p1S). Do not kill it. It serves `web/` statically, so a browser reload picks up edits.
- **Commits:** todo-level commits are approved, and each commit stages only its own files. No AI attribution, no Co-Authored-By, no session links.
- **Push, publish:** forbidden in this plan.
- **Goal tools:** none exposed. start-work's ledger carries the run.
- **Workflow tool:** not used. The user asked for herdr muse lanes instead.
- **Worktrees:** none. Lanes share the repo and own disjoint files, listed per todo.
- **Shared worker rules:** `.litclaude/evidence/explain-why-upgrade/BRIEF.md` applies, with this plan replacing that one. Evidence goes to `.litclaude/evidence/hq-demo-roll/task-<N>.txt`. Telemetry line: `T<N> DONE <sha> <tests> <note>` or `T<N> BLOCKED <reason>`.

### Anchor contract (shared by Todo 2 and Todo 3)

Todo 2 puts these attributes on the new layout. Todo 3 targets only these attributes and never class names.

- `data-demo="picker"`: portfolio list
- `data-demo="banner"`: verdict word + headline + project line
- `data-demo="decisive"`: first decisive card, including its quote
- `data-demo="flips"`: the inline top flips
- `data-demo="map"`: map wrapper with the chip
- `data-demo="layers"`: compact layer strip
- `data-demo="checked"`: the "How it was checked" disclosure
- `data-demo="catches"`: the double-checks section inside it
- `data-demo="trace"`: the model and data trace section inside it

Two globals let the demo drive the page:
- `window.SiteWhy.selectSite(name)` returns a Promise that resolves after render.
- `window.SiteWhy.openChecked(section)`, where `section` is `"catches"` or `"trace"`, opens the disclosure and scrolls that section into view.

## Execution loop

Every todo runs `PIN -> RED -> GREEN -> VERIFY -> SURFACE -> REVIEW -> CLEAN -> RECORD`.

- **RED/GREEN:** there are no web tests in `tests/`. Behavior that has a backend contract gets a pytest. For the demo, RED/GREEN is a browser assertion script: `node`, or a JS snippet run through claude-in-chrome. It must fail before the change and pass after. Record it in `task-<N>.txt`.
- **VERIFY:** `uv run pytest -q` and `uv run ruff check .` are green.
- **SURFACE:** a real browser at http://localhost:8000, with screenshots saved under the task's evidence folder.

## Todos

- [x] 1. Midnight Ops theme tokens (lane `theme`)
  - **Files:** `web/app.css` tokens block and verdict/lamp colour rules only; `web/index.html` theme-toggle button; `web/app.js` theme-toggle code only.
  - **Action:**
    - Replace the `:root` tokens with D1 from `theme.md`: bg #0B1416, surface #15272C, text #F2EFE6, muted #9FADAB, accent #FF8A5C, no-go #FF6B6B, conditional #F2B73D, go #5AD08A, unknown #9AA8A6. Choose rule and panel-2 values so text contrast is at least 4.5:1, then compute and record it.
    - Remove the light-theme toggle and its JS. Keep the print stylesheet light.
    - Add `font-variant-numeric: tabular-nums` to numbers.
    - The verdict word is always shown next to its colour.
  - **Output:** the commit `style(ui): Midnight Ops theme tokens, verdict colours always paired with words`.
  - **Verification:**
    - Contrast table computed in `task-1.txt`, all ≥ 4.5:1 for text and ≥ 3:1 for dots.
    - Screenshot at 1440 shows the new tokens.
    - No `theme-toggle` left in `web/`.
  - **Blocked by:** none. Runs first because it is small; Todo 2 starts after its commit.

- [x] 2. Answer-first layout and plain labels (lane `ux`)
  - **Files:** `web/index.html`, `web/app.css` (layout rules), `web/app.js`, excluding theme code and `web/demo.js`.
  - **Action:** implement `ux.md` (c) and (d).
    - **First view:** banner at top of the centre column, then the first decisive card open, then the top 2 flips inline, then the map with its chip, then a one-line layer strip. Portfolio stays in the rail as the site picker.
    - **Tabs:** the 5 tabs become 2 disclosures.
      - "Why": all decisive cards, all flips, open questions.
      - "How it was checked": double-checks, all rules, state watch list, model and data trace, run stats, timeline.
    - **Telemetry** becomes "Run stats" inside "How it was checked". Its 5 numbers stay.
    - **Share:** Copy, Download and Print fold into one Share menu.
    - **SAMPLE_MODE:** hide the screen form behind "Screen a new address". Hide the map-click popup instead of showing a disabled run. Live mode is unchanged.
    - **Plain labels** from `ux.md` (e):
      - Fatal/Major/Minor/Clear/Unknown/Not modelled → Stop / Needs a fix / Noted / Clear / Not checked / Out of scope
      - "What the agents caught" → "Double-checks (n)"
      - "Under the hood" → "How this was built"
      - "needs_confirmation" → "Needs one more check"
    - **Demo hooks:** add the anchor contract attributes and `window.SiteWhy`.
    - **Links and print:** existing deep links `#/site/<name>` and `#/run/<id>` keep working. Print brief still prints banner + decisive.
  - **Output:** the commit `feat(ui): answer-first layout with two disclosures, plain labels and demo anchors`.
  - **Verification:**
    - Cold load of Washington at 1440x800 shows verdict word, decisive rule title and the quote without scrolling (screenshot).
    - All 4 samples render with no console errors.
    - Every anchor in the contract exists (JS check that counts `[data-demo]` = 9 after opening Washington).
    - `#/site/az-tucson-pima` deep link works.
    - At 390 width it is a single column in reading order (screenshot).
  - **Blocked by:** 1.

- [x] 3. Demo roll (lane `demo`)
  - **Files:** new `web/demo.js` and `web/demo.css`. One `<script>`, one `<link>` and the "▶ Demo roll" button in `web/index.html`; the button sits at the top of the rail.
  - **Action:** build option A from `demo.md`, a scripted step tour.
    - **Steps:** the 7 steps of `demo.md` (c), plus step 8 (Tucson vs Abilene) only if the total stays ≤ 90 s.
    - **Highlighting:** each step outlines its anchor. No full-screen dim over the map. A docked caption bar shows "Step N of M", the caption, and the controls ❚❚/▶, ‹ Back, Next ›, ✕ Exit, plus a progress bar with `role="progressbar"`.
    - **Captions** are template strings filled from the loaded report fields named in `demo.md` (c). No fact is hard-coded; for example, the duration comes from the evidence quote and verified fields.
    - **Auto-advance:** about 9 s per step.
    - **Interruption:** Space toggles pause, arrows move back and next, Esc exits. Any click outside the caption bar pauses.
    - **Exit** restores the previous hash, selection and focus.
    - **Reduced motion:** honoured, with instant switches and no pulse.
    - **Start:** only from the button or the `#/demo` hash. Never autostart.
    - **Offline tiles:** if map tiles fail, the map step still shows its caption.
    - **Network:** the roll uses only `GET /samples*`.
    - Drive the page only through the anchor contract and `window.SiteWhy`.
  - **Output:** the commit `feat(ui): demo roll guided tour over the showcase samples`.
  - **Verification:**
    - A browser script starts `#/demo` and polls until the roll ends. It asserts that all steps were shown in order, that every caption contains no `undefined` or `null`, and that the final state restores the hash.
    - The same run with tile requests blocked also completes.
    - GIF of the full unattended roll saved to `.litclaude/evidence/hq-demo-roll/demo-roll.gif`.
    - Esc mid-roll restores state.
  - **Blocked by:**
    - Code against the anchor contract can start in parallel with 1 and 2.
    - The final verification needs 2 committed.

- [x] 4. Bookkeeping (orchestrator)
  - **Action:**
    - Tick rows 1–3 and F1–F3.
    - Add one line under `plans/roadmap.md` M3 Scope for the demo roll and the theme.
  - **Output:** the commit `docs(plan): record demo roll and HQ layout results`.
  - **Verification:** `grep -c "\[x\]" plans/hq-demo-roll.md` = 7.

## Final verification

- [x] F1. Interface probe and visual QA
  - Run the frontend-ui-ux interface probe on http://localhost:8000:

    ```
    node ~/.litclaude/marketplaces/litclaude-ai/plugins/litclaude/skills/frontend-ui-ux/scripts/interface-probe.mjs http://localhost:8000 --out .litclaude/evidence/hq-demo-roll/probe
    ```

  - Required result: exit 0 (0 HIGH) at 320/390/768/1440, reduced motion and 200% zoom.
  - Look at the 320, 390 and 1440 screenshots yourself.
  - This also closes `plans/explain-why-upgrade.md` row C010.
- [x] F2. Review
  - `litclaude:quality-reviewer` reviews the diff since the plan start commit.
  - Required result: no P0/P1, recorded in `F2-review.md`.
- [x] F3. Real Manual-QA (orchestrator, claude-in-chrome)
  1. Cold load of Washington: the 5-second check passes.
  2. Unattended demo roll to the end.
  3. Mid-roll: Space, arrows, a click on a portfolio row, Esc.
  4. `#/demo` deep link.
  5. All 4 samples.
  6. 390 width.
  - PASS/FAIL per scenario, recorded in `F3-qa.md` with screenshots.

## Stop rules

- Stop and report BLOCKED on any of:
  - a missing anchor-contract element that Todo 2 cannot add without backend changes
  - a contradiction between `PACKET.md` and live samples, for example a caption field that is absent
  - the server pane dying twice
  - the same failure repeated three times
  - any step that needs push or publish
- **Cut order if late:**
  1. step 8
  2. the label renames
  3. Share-menu folding
  - Never cut: the roll, the answer-first first view, the theme tokens.

## DoneClaim

Completion requires all of:
- 3 feature commits + 1 bookkeeping commit
- `uv run pytest -q` green
- `uv run ruff check .` green
- probe exit 0 with screenshots
- `demo-roll.gif`
- F2 and F3 PASS files
- no files outside the Files lists changed (`git diff --stat` against the plan start commit)
- cleanup: lanes `ux`, `demo` and `theme` closed or left idle and reported; `server` pane still serving (health 200)
- release-action receipt: "no push, no publish"

## Results (2026-10-27)

- Commits: 63f8f0d theme, cc89c81 demo roll, 39153f8 answer-first layout, 89172c9 + d9abf33 review fixes, 902de20 double-check caption, plus this bookkeeping commit.
- F1: interface probe exit 0, 0 HIGH (`.litclaude/evidence/hq-demo-roll/probe/`).
- F2: round 1 FAIL (3 P1), round 2 PASS (`F2-review.md`).
- F3: 6/6 PASS (`F3-qa.md`); 390 width taken from the probe because the Chrome window could not shrink below 1152 px.
- `demo-roll.gif` was recorded at d9abf33, before the step-5 caption fix; re-record for the M4 video.
- No push, no publish.
