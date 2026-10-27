# m4-submission — Work Plan

## TL;DR (For humans)

**What you'll get:** A complete, honest hackathon submission: a real README, the metadata file, a 1–4 minute narrated demo video, a pitch deck that covers the eight required points, and a filled-in submission sheet you can copy into HackOS. The app also gets the fixes the judges asked for: no more "any US address" overclaim, a clear "recorded run" label on the showcase reports, a time limit so a live run cannot hang the demo, and, if Nightshift is reachable, one extra recorded run at a smaller project size.

**Why this approach:** The judging panel said the product is prize-worthy but the submission is empty, and an empty README and no video can sink it on their own. So the work runs in dependency order: get the official templates, fix what the video and README will show, write the docs, then record the video and build the deck from the finished app. Nothing is faked: a new sample only comes from a real run, and every number in the README comes from the eval file or the recorded runs.

**What it will NOT do:** It won't move data into Zetaris, add states or rewrite the verification core. It won't push, create the GitHub repo, upload the video or submit to HackOS without your explicit go-ahead at that step.

**Effort:** Large (about 8–10 hours across 3 lanes)
**Risk:** Medium — the HackOS templates live behind your login, and headless video recording can stutter on map tiles.
**Decisions to sanity-check:**
- The extra recorded run is Abilene at 50 MW (2 Nemotron calls via Nightshift); it is skipped if Nightshift is not reachable.
- Narration uses the built-in macOS voice; you can re-record with your own voice later.
- The video file stays out of git; you upload it (for example as an unlisted YouTube video) and paste the link.
- Pre-window datasets (Moratorium Nation, state legislation CSV) and the Meterless specs are declared as pre-existing third-party material; no pre-existing code.

Your next move: type `/litclaude:start-work plans/m4-submission.md` to approve the plan and start it.

---

> TL;DR (machine): Large, Medium risk. Templates → honest copy + recorded badge → run safety (deadline/409/poll cap/markovian reset) → optional 50 MW sample → README + metadata.json + ATTRIBUTION → push gate → video (Playwright recordVideo + say + ffmpeg) → deck (lit-pptx) → submission sheet; F1–F4.

Input: `.litclaude/evidence/submission-crucible/PACKET.md` (crucible verdict pass), `.litclaude/evidence/judging/SYNTHESIS.md` and `judging/{why,tech,sponsor,impact}.md`.

## Bootstrap and PIN
- Objective: by 10/27 22:00 KST the repo holds a README, `metadata.json` and `submission/` (video script + deck + submission sheet) that let a judge score Impact, Technical, Innovation, Demo, UX and Sponsor without reading code; the UI makes no coverage claim the backend cannot back; a live run cannot hang longer than its deadline; the user has a ready-to-push repo and a ready-to-upload mp4.
- Start commit: `2abf2aa`. Dirty: untracked `.litmuse/`, `scripts/fetch_warm.py` (never stage; untracked files are not pushed).
- Server: herdr pane `server` (w2W:p1S) on :8000 in SAMPLE_MODE; static `web/` edits need no restart; backend edits are tested with pytest, and the server is restarted only by the orchestrator after Todo 3 lands (`uv run uvicorn app.main:app --port 8000` in that pane).
- Commits: todo-level commits approved (standing rule); stage only own files; no AI attribution, no Co-Authored-By, no session links. **Push, GitHub repo creation, video upload and HackOS submission are user-gated** (Todo 6, Todo 9).
- Goal tools: none exposed (no `/goal` step). Workflow tool: not used. Lanes: herdr muse panes `fix` (Todos 2–3), `docs` (Todo 5), `media` (Todos 7–8); orchestrator owns Todos 1, 4, 6, 9 and the F-wave. Worktrees: none; lanes own disjoint files.
- Worker brief: `.litclaude/evidence/m4-submission/BRIEF.md` (orchestrator writes it at start: same rules as `.litclaude/evidence/hq-clarity-pass/BRIEF.md`, evidence to `.litclaude/evidence/m4-submission/task-<N>.txt`, telemetry `T<N> DONE <sha> <tests> <note>` | `T<N> BLOCKED <reason>`).
- Known harness issue: muse panes stall on "macOS Keychain didn't answer"; re-prompt and send Enter until `working`.
- Time box: UI/backend changes freeze at 17:00 KST; video recording starts no later than 17:30 KST.

## Scope
### Must have
- Official HackOS template text for README, Pitch Deck, Metadata json and Demo Script saved under `submission/templates/` (or user-pasted).
- Honest coverage copy in `web/index.html` and `web/app.js`; "Recorded run · <UTC date>" badge on showcase reports.
- Cooperative run deadline (default 300 s) with a partial `needs_confirmation` report; 409 on a concurrent POST /runs; client poll cap; `markovian_runs` reset per run; RED→GREEN tests.
- README on the HackOS template with problem, users, how it differs, architecture + agent loop, sponsor tech (Nightshift primary, Nemotron per role, Zetaris, World Model, Markovian), eval numbers with sources, setup (SAMPLE_MODE + live), sample I/O, limitations, data licenses, troubleshooting.
- `metadata.json` per the template; `data/ATTRIBUTION.md` matches the code (Esri Dark Gray Canvas).
- Demo video 60–240 s (h264 + aac mp4) covering rule 6.1: workflow, how the agent solves it, key features, Zetaris + Meterless integration; leads with the Washington-unincorporated (No-go) vs Hagerstown-city (Conditional) scope flip.
- Pitch deck (pptx + pdf) covering rule 6.2's 8 points.
- `submission/SUBMISSION.md`: answers for the HackOS form, links, pre-existing declaration, push/upload commands for the user.
### Must NOT have (guardrails, anti-slop, scope boundaries)
- No rules/county sources into Zetaris, no quote→value alignment check, no new states/layers, no Remotion/OBS.
- No hand-edited or synthesised samples; a new sample only from a real recorded run.
- No README claim without a source (eval file, test count, sample field); no accuracy numbers that were never measured.
- No push, repo creation, upload or HackOS submit without the user's explicit approval at that step; never print secrets; mp4/large binaries not committed.

## Verification strategy
> Zero human intervention — every verification step is agent-executed, except the user-gated push/upload/submit actions.
- Test decision: TDD for backend (Todo 3, pytest); tests-after browser assertions for web (Todo 2); content checks for docs (grep/JSON validation/fresh-clone run); media checks via ffprobe + frame grabs + rendered PDF pages.
- Manual-QA channel: browser (headless Chrome via `~/.npm/_npx/705bc6b22212b352/node_modules/playwright`, `channel: 'chrome'`), HTTP (curl for 409/poll), terminal (fresh clone), file inspection (ffprobe, PDF render).
- Evidence: `.litclaude/evidence/m4-submission/task-<N>.txt` + `task-<N>/`; F-wave files `F1-probe/`, `F2-review.md`, `F3-qa.md`, `F4-scope.txt`.

## Execution strategy
### Parallel execution waves
- Wave 1: Todo 1 (orchestrator, templates) ∥ Todo 2 (fix lane, web copy + badge) ∥ Todo 5-draft (docs lane drafts README from the recorded 6.x rules while templates are fetched).
- Wave 2: Todo 3 (fix lane, run safety) ∥ Todo 5-finalise (docs, after Todo 1) ∥ Todo 8-draft (media lane builds deck outline + slides from README draft and existing screenshots).
- Wave 3: Todo 4 (orchestrator, 50 MW sample, after Todo 3 + server restart) → Todo 7 (media, video, after Todos 2–4 committed) ∥ Todo 8-finalise.
- Wave 4: Todo 6 (push gate) after Todo 5; Todo 9 (submission sheet + bookkeeping) after 6–8; F1–F4.

### Dependency matrix
| Todo | Depends on | Blocks | Can parallelize with |
| --- | --- | --- | --- |
| 1 HackOS templates | — | 5-final, 8-final, 9 | 2, 5-draft |
| 2 Honest copy + badge | — | 7, 5-final (screenshots) | 1, 5-draft |
| 3 Run safety | 2 (same lane, `web/app.js`) | 4 | 5, 8-draft |
| 4 50 MW sample (optional) | 3 + server restart | 7, 5-final (sample list) | 8 |
| 5 README + metadata + ATTRIBUTION | 1 (final), 2, 4 | 6, 9 | 3, 8 |
| 6 Push gate (user) | 5 | 9 | 7, 8 |
| 7 Demo video | 2, 3, 4 | 9 | 8, 6 |
| 8 Pitch deck | 1, 5-draft (final: 7 frames) | 9 | 3, 4, 7 |
| 9 Submission sheet + bookkeeping | 5–8, F1–F4 | — | — |

## Todos
> Implementation + Test = ONE todo. Never separate them.
> Rows start at column zero as `- [ ] N. <title>`; start-work cannot see an indented row.
<!-- APPEND TASK BATCHES BELOW THIS LINE — never rewrite the headers above. -->
- [x] 1. Capture the HackOS templates (orchestrator) — done 12:40: README/Pitch Deck/Metadata json/Demo Script templates are no longer listed on HackOS; captured instead the Submission Form Preview, Demo Video Guide, Zetaris Scoring Methodology and Disqualification Checklist into `.litclaude/evidence/m4-submission/templates/` (organizer documents kept private, not committed). metadata.json is not a form field; it stays as a small optional file.
  What to do / Must NOT do: Load claude-in-chrome tools (one ToolSearch call: tabs_context_mcp, tabs_create_mcp, navigate, get_page_text, find, javascript_tool, read_page). Open HackOS Resources → Featured in a new tab of the user's logged-in browser; for each of README, Pitch Deck, Metadata json, Demo Script open the modal and read `document.querySelector('[role=dialog]').innerText` in ≤1000-char slices with URLs stripped (`replace(/https?:\/\/\S+/g,'[url]')`, technique from `HANDOFF.md:47-48`). Save verbatim text to `submission/templates/{readme,pitch-deck,metadata-json,demo-script}.md`. Also record the submission form field labels if visible. Must NOT click submit/accept, enter credentials, or download files. Fallback: if the extension is disconnected or HackOS needs a login, ask the user once to paste the four template texts and continue other waves meanwhile.
  Parallelization: Wave 1 | Blocked by: — | Blocks: 5-final, 8-final, 9
  References: `HANDOFF.md:33-38,47-49`; `plans/dc-site-screener.md:36-44,256` (recorded rule 6.1–6.4 paraphrase); `.litclaude/evidence/submission-crucible/PACKET.md` constraint 2.
  Acceptance criteria: four files exist and are non-empty; `metadata-json.md` contains a JSON skeleton or field list; or a recorded BLOCKED with the user's pasted text substituted.
  QA scenarios: happy — each file's first line matches the modal title; failure — extension disconnected → fallback prompt recorded in `task-1.txt`. Evidence `.litclaude/evidence/m4-submission/task-1.txt`.
  Commit: Y | `docs(submission): save the HackOS submission templates`

- [x] 2. Honest coverage copy and recorded-run badge (lane `fix`) — 30fe8f9
  What to do / Must NOT do: In `web/index.html`, `web/app.js`, `web/app.css` only: replace "Screen any US address for data center rules — and see why." (`web/index.html:23`), "Showcase sites. Type any US address above to screen it live." (`:52`), "AI agents check federal, state and local rules" (`:59`) and "about 3–4 minutes" (`web/app.js:903`) with accurate copy, e.g. value line "Check a US data center site against the rules that can block it — and see why."; step 2 "AI agents check federal, state, grid and county rules where modelled"; note "Any US address is screened against federal rules and a 1,291-entry moratorium dataset; state and grid rules: Texas/ERCOT; verified county ordinances: Washington Co. MD, Pima Co. AZ."; run note "about 5–8 minutes". Add a "Recorded run · <YYYY-MM-DD HH:MM UTC>" badge for `state.selected.kind === "showcase"` in `projectLine()` (`web/app.js:623-632`) using `report.events[0].at` (fallback: parse `run_id`), hidden for live runs and in print; N1 styling (ink border, mono 12px). Must NOT touch demo/nav/palette/chain/lanes/settings files or backend.
  Parallelization: Wave 1 | Blocked by: — | Blocks: 3 (same lane), 5-final, 7
  References: crucible lane B §(1),(3) in `PACKET.md` constraints 3–4; `app/explain.py:563-573` (coverage note); `web/app.js:559,598` (kind), `:988-997` (sample mode); `app/main.py:84-92,159-176`.
  Acceptance criteria: `grep -n "any US address\|federal, state and local\|3–4 minutes" web/` returns nothing; badge text present on all 4 showcase sites, absent for a stubbed live report object; pytest + ruff green; interface probe 0 HIGH.
  QA scenarios: headless Chrome 1440×800 + 390×844 on 4 sites (screenshots), print emulation (badge hidden); failure — report without `events` → badge falls back to `run_id` date, no "undefined". Evidence `.litclaude/evidence/m4-submission/task-2/`.
  Commit: Y | `fix(ui): honest coverage copy and a recorded-run label on showcase reports`

- [x] 3. Run safety: deadline, single-run guard, poll cap, Markovian reset (lane `fix`, after 2) — 9e77ab1
  What to do / Must NOT do: TDD. (a) `app/orchestrator.py`: accept a deadline (default `RUN_DEADLINE_S=300` from `app/config.py`, injectable clock); check before each round, each `_investigate`, inside the retry loop and before adjudicate/critique; on expiry stop cooperatively and return a partial report with verdict `needs_confirmation`, a `needs_confirmation` item "Run stopped at the 5-minute limit before <stage>", and an `escalated`/timeout event. (b) `app/llm.py`: check the same deadline before each `_post` attempt and the Ultra retry (no new thread). (c) `app/main.py`: POST /runs returns 409 `{"detail":"A screening is already running"}` while `run_lock` is held (acquire non-blocking in the request, release in the worker's finally); copy run state under a small lock in `get_run`. (d) `app/agents.py`: reset `CountyInvestigator.runs` at the start of each run so `markovian_runs` holds only that run. (e) `web/app.js` `pollRun`: stop after deadline + 60 s and show "The run did not finish in time — try again"; handle 409 with "Another screening is running". Must NOT abandon threads, change report schema fields that samples use, or touch other web files.
  Parallelization: Wave 2 | Blocked by: 2 | Blocks: 4
  References: crucible lane B §(2): `app/main.py:61,71-77,111-151`; `app/orchestrator.py:185,478-482,620-663,685-709`; `app/llm.py:76-83,111-142,166-185`; `app/agents.py:82,128`; `web/app.js:886-908,936-941`; tests `tests/test_api_runs.py:13,41`, `tests/test_orchestrator.py:60-70,97`, `tests/test_llm.py:151`.
  Acceptance criteria: new tests fail before and pass after: deadline → partial `needs_confirmation` report with the timeout item; second POST → 409; `markovian_runs` length equals that run's count across two sequential runs; existing 153 tests still pass; ruff clean.
  QA scenarios: pytest output; HTTP — with the FakeOrchestrator in a test client, POST twice → 201/409; browser — stubbed slow poll shows the timeout message. Evidence `.litclaude/evidence/m4-submission/task-3.txt`.
  Commit: Y | `fix(runs): stop at a 5-minute deadline and refuse a second concurrent run`

- [x] 4. Recorded 50 MW Abilene sample (orchestrator, optional) — d3c4a13 (conditional; SB 6 + ERCOT audit flip to no)
  What to do / Must NOT do: After Todo 3 and a server restart in live mode is NOT needed — run the recorder directly. Add an `--mw` option and an output-name option to `scripts/record_samples.py` (default unchanged 300 MW); preflight Nightshift (`/v1/models` 200) and Zetaris as the script already does; record Abilene at 50 MW to `samples/tx-abilene-ercot-50mw.json`. Expected (not asserted): SB 6 and ERCOT audit "no", Title V "yes" → conditional; record the actual verdict whatever it is. Skip (mark N/A with reason) if Nightshift/Zetaris preflight fails. Must NOT edit any report by hand, change the 4 existing samples, or exceed 1 recording attempt plus 1 retry.
  Parallelization: Wave 3 | Blocked by: 3 | Blocks: 5-final, 7
  References: crucible lane B §(4): `scripts/record_samples.py:21,51`; cache key `app/llm.py:111-113`; thresholds `app/applicability.py:93-112` (50 MW → 21 generators, 185.2 tpy NOx); `main.py:181,202` (samples auto-listed); `tests/test_applicability.py:88-93` (add 25/26/50 MW cases).
  Acceptance criteria: new sample loads at `#/site/tx-abilene-ercot-50mw` with 0 console errors and `project.mw == 50`; model_trace entries all Nemotron via Nightshift; applicability test cases for 25/26/50 MW pass; or N/A recorded with the preflight output.
  QA scenarios: happy — browser screenshot of the 50 MW report next to the 300 MW one; failure — preflight non-200 → skip without partial files in `samples/`. Evidence `.litclaude/evidence/m4-submission/task-4.txt`.
  Commit: Y | `feat(samples): recorded Abilene run at 50 MW`

- [x] 5. README, metadata.json and attribution (lane `docs`) — fbf7692 … 2b2cda0; task-5.txt
  What to do / Must NOT do: Draft immediately from `plans/dc-site-screener.md:36-44,63-75,256-260`, `judging/SYNTHESIS.md` and the judge reports; finalise on the template from Todo 1. README sections (template order wins): one-line pitch; problem with sourced numbers (`judging/impact.md` market sources); users; what SiteWhy does that listing tools do not; architecture + agent loop (Mermaid: planner → investigators → verifier → applicability → adjudicator → critic → re-plan); sponsor tech (Nightshift primary with headers, Nemotron Lightning/Ultra per role, Zetaris tables and queries, World Model, Markovian with test names); eval numbers only from `data/eval/results.json` (3/3 ground truth, 3/3 seeded critic faults) and test count from a fresh `uv run pytest -q`; per-model calls/tokens/latency computed from `samples/*.json model_trace` (script output saved to evidence); setup (SAMPLE_MODE quick start, live mode with Nightshift + Zetaris, `.env.example`); sample I/O table (4–5 samples with verdicts); screenshots (from Todo 2 renders, committed under `docs/img/`, ≤ 300 KB each); limitations (Markovian saved 0 tokens on current sources; curated seed rules; coverage scope; sequential live runs with 5-min deadline); data licenses + World Model spec credit (Apache-2.0); troubleshooting. `metadata.json` per template fields (Meterless engines: World Model, Markovian; NVIDIA models `nvidia/nemotron-3.5-lightning-30b-a3b`, `nvidia/nemotron-3-ultra-550b-a55b`; Nightshift; Zetaris). Update `data/ATTRIBUTION.md` (CARTO → Esri Dark Gray Canvas). Add `.litmuse/` to `.gitignore`. Must NOT claim unmeasured accuracy/latency, include secrets, or edit code.
  Parallelization: Wave 1 (draft) → Wave 2/3 (final) | Blocked by: 1 (final), 2, 4 | Blocks: 6, 9
  References: `.env.example`; `data/eval/results.json:37-47`; `scripts/eval.py`; `app/llm.py:20-21,37`; `app/data.py:108-119`; `app/worldmodel/`; `tests/test_worldmodel_conformance.py`, `tests/test_markovian_conformance.py`; `branding/sitewhy-team.png`; `submission/templates/*`.
  Acceptance criteria: every number in README traces to a file listed in `task-5.txt`; `python -c "import json;json.load(open('metadata.json'))"` passes and fields match the template; fresh clone (`git clone . /tmp/...-clone` inside the private temp folder, `uv sync`, `SAMPLE_MODE=true uv run uvicorn app.main:app --port 8010`) serves `/portfolio` with the samples; `grep -n CARTO data/ATTRIBUTION.md` empty; no secret patterns (`grep -nE "sk-|nvapi-|Bearer [A-Za-z0-9]"` empty).
  QA scenarios: happy — fresh-clone run + curl `/portfolio`; README rendered via pandoc to HTML and inspected; failure — missing `.env` in live mode → README troubleshooting covers the error text. Evidence `.litclaude/evidence/m4-submission/task-5.txt`.
  Commit: Y | `docs: README, metadata.json and data attribution for submission`

- [x] 6. Public repository gate (orchestrator + user) — user ran `gh repo create sitewhy --public --source . --remote origin --push`; https://github.com/wjgoarxiv/sitewhy PUBLIC, origin/master = 2b2cda0 = local HEAD; task-6.txt
  What to do / Must NOT do: Prepare, do not run: confirm `git status` clean except untracked `.litmuse/`/`scripts/fetch_warm.py`, list tracked files for secrets (`git grep -nE "nvapi-|sk-|PROXY_TOKEN=|ZETARIS_API_KEY=[^$]"` empty), size check (`git count-objects -vH`). Ask the user once: "push 승인?" with the exact commands (`gh repo create sitewhy --public --source . --remote origin --push` or manual remote + `git push -u origin master`). On approval the user runs them via `! <command>` (start-work forbids push in the session); record the remote URL and pushed sha. Must NOT push or create the repo without the explicit approval in this step.
  Parallelization: Wave 4 | Blocked by: 5 | Blocks: 9
  References: `HANDOFF.md:55`; `plans/dc-site-screener.md:289`; `.gitignore`.
  Acceptance criteria: secret scan empty; after approval `git remote -v` shows origin and `git ls-remote origin master` sha equals local HEAD; README renders on GitHub (fetch the repo page). If not approved: recorded as user-deferred, Todo 9 lists the commands.
  QA scenarios: happy — GitHub page shows README; failure — `gh` not authenticated → give the user `! gh auth login`. Evidence `.litclaude/evidence/m4-submission/task-6.txt`.
  Commit: N | —

- [x] 7. Demo video (lane `media`) — 3c66592; `submission/video/OAH2026-SiteWhy-ExplainWhy-Demo.mp4` 3:26.6, h264+aac 1080p, 14.1 MB, git-ignored
  What to do / Must NOT do: Write `submission/video/script.md` (shots + narration lines ≤ 14 words each, ≤ 3:30 total) following the template from Todo 1 and the storyboard in `.litclaude/evidence/judging/impact.md` (hook with sourced moratoria count; Washington unincorporated No-go → Hagerstown city Conditional scope flip; decisive card with verified quote; flips table; agent lanes with Nemotron + receipts + Zetaris row; why chain + source; TX ERCOT different grid (+ 50 MW contrast if Todo 4 exists); recorded-run badge visible; outro). Build `submission/video/record.mjs` (Playwright, Chrome, `recordVideo` 1920×1080, warm-up visit, scripted navigation + the `#/demo` tour, per-shot timestamp log JSON), narration with `say -v "Samantha" -r 185 -o NN.aiff`, ffmpeg: trim head, `adelay`/`amix` at logged times, title + end cards (ImageMagick), encode `-c:v libx264 -crf 18 -pix_fmt yuv420p -c:a aac -b:a 192k` → `submission/video/sitewhy-demo.mp4` (git-ignored) plus a 20 s README GIF `docs/img/demo.gif` (≤ 4 MB). One throwaway take, then the real take. Must NOT commit the mp4, use `?tiles=invalid`, or show secrets.
  Parallelization: Wave 3 | Blocked by: 2, 3, 4 | Blocks: 9
  References: crucible lane C (tools: ffmpeg 9.0.2, Playwright 1.64.1, `say` voices, ImageMagick); `.litclaude/evidence/hq-clarity-pass/F3/gif.mjs` (tour polling template); `web/demo.js` (`window.SiteWhyDemo` start/exit/setSpeed/state.log); rule 6.1 (`plans/dc-site-screener.md:38`).
  Acceptance criteria: `ffprobe` shows h264 + aac, duration 60–240 s; frame grabs at each logged shot time show the intended screen (tiles loaded, no blank map) and are saved; narration audible and not cut (each clip shorter than its shot); rule 6.1 items mapped to timestamps in `task-7.txt`.
  QA scenarios: happy — contact sheet of frame grabs (`ffmpeg -vf fps=1/10,tile`) inspected; failure — blank tiles in a shot → re-take that segment after warm-up. Evidence `.litclaude/evidence/m4-submission/task-7/`.
  Commit: Y | `docs(submission): demo video script, recorder and README GIF`

- [x] 8. Pitch deck (lane `media` → ran on `deck`) — b08f370 → cd0860e (v2) → 45ff311 (v3) → 05b425c (claims match code); Cursor line pending Todo 12
  What to do / Must NOT do: Use the lit-pptx skill (runtime python-pptx 1.0.2 cached) to build `submission/deck/sitewhy-deck.pptx` and `.pdf` (via `soffice --headless --convert-to pdf`) on the Pitch Deck template from Todo 1, covering rule 6.2: (1) problem + users, (2) solution, (3) workflow/architecture, (4) stack, (5) Zetaris + Meterless usage, (6) what was unique about the sponsor tech use, (7) product visuals, (8) future enhancements; 10–14 slides, 16:9, screenshots from Todo 2/7 renders, team image `branding/sitewhy-team.png`, numbers only from README sources. Must NOT invent metrics or customer claims.
  Parallelization: Wave 2 (draft) → Wave 3 (final) | Blocked by: 1, 5-draft | Blocks: 9
  References: `plans/dc-site-screener.md:39`; README draft; `.litclaude/evidence/judging/impact.md` (pitch + market sources).
  Acceptance criteria: lit-pptx QA gate passes; rendered PDF pages inspected (no overflow, readable at 1280 px); slide-to-rule-6.2 mapping table in `task-8.txt` covers all 8 points.
  QA scenarios: happy — page images reviewed; failure — overflow flagged by the QA gate → fix and re-render. Evidence `.litclaude/evidence/m4-submission/task-8/`.
  Commit: Y | `docs(submission): pitch deck`

- [x] 9. Submission sheet and bookkeeping (orchestrator) — SUBMISSION.md filled (repo URL, video link in repo, Cursor line); README redesigned with an orbit-loop motion cover (lit-typographic-motion, gate PASS+TARGET) and the demo MP4 committed per user request; committed and pushed by the docs lane with user approval
  What to do / Must NOT do: Write `submission/SUBMISSION.md`: every HackOS form field from Todo 1 with the answer to paste (title, tagline, track, description, repo URL, video link placeholder, deck file, sponsor tech explanation, NVIDIA models per request, pre-existing components declaration: pre-window datasets + Meterless specs, no pre-existing code), plus the user's remaining steps (upload mp4 unlisted, paste link, submit before 10/28 08:45 KST, capture confirmation). Tick rows here, add an M4 line to `plans/roadmap.md`, append a Results section. Must NOT submit to HackOS or upload anything.
  Parallelization: last | Blocked by: 5–8, F1–F4 | Blocks: —
  References: `plans/roadmap.md` M4; `HANDOFF.md:14,37,94`; `plans/hq-clarity-pass.md` Results as format model.
  Acceptance criteria: `grep -c "^- \[x\]" plans/m4-submission.md` = 16 (or 15 with Todo 4 marked N/A and explained); every form field has an answer or an explicit user action.
  QA scenarios: `git status --short` shows only untracked `.litmuse/` (now ignored) and `scripts/fetch_warm.py`. Evidence `.litclaude/evidence/m4-submission/task-9.txt`.
  Commit: Y | `docs(plan): record submission results`

- [x] 10. Sample mode runs real agent logic; run.py, examples and JSONL traces (lane `fix`, after 3) — ca294d1 + 103e822. Deviation accepted by orchestrator: Hagerstown replay reaches needs_confirmation (recorded showcase: conditional after round 2; 4 re-recordings all needs_confirmation = model variance on a borderline case). Kept both as real runs; README limitations state it.
  Added 10/27 12:45 by user decision after reading HackOS "Disqualification Checklist" (`.litclaude/evidence/m4-submission/templates/disqualification-checklist.md`): "SAMPLE_MODE=true runs the whole thing without Zetaris, Nightshift or credentials … still runs real agent logic on cached data, rather than replaying a saved output"; recommended run.py, input_examples/ (≥3), output_examples/ (≥3), logs/ JSONL traces to stdout + logs/.
  What to do / Must NOT do: (a) In SAMPLE_MODE, allow POST /runs (remove the 503 at `app/main.py:140-141`) and run the real orchestrator with: LLM responses replayed from `data/llm_cache` (`app/llm.py:160-164`), evidence pages from `data/sources`, geocoding from a cache (add one if missing), data queries via the existing DuckDB fallback (Zetaris unreachable). Pin `as_of` in sample mode to the recorded date so cache keys match (cache key includes the site with `as_of`, `app/llm.py:111-113`, `app/orchestrator.py:492`). A cache miss returns a clear 4xx/`needs_confirmation` message, not a hang. (b) Commit only the cache files needed for the 4 showcase inputs (force-add; keep the rest ignored); size ≤ 5 MB total. (c) `run.py`: `python run.py --input input_examples/<x>.json [--sample]` → writes the report JSON to stdout/`output_examples/` and traces to `logs/<run_id>.jsonl` + stdout, reusing the orchestrator (no duplicate logic). (d) `input_examples/` 4 files (the showcase inputs: address, mw, permits) and `output_examples/` 4 matching outputs produced by `run.py --sample` (generated, not copied from samples/). (e) Trace JSONL per event: timestamp, agent_name, action, input_summary, output_summary, target_agent, model, retry_count, status (map from existing `events` + `model_trace`; never hand-written). Must NOT add demo-only branches or map inputs to prewritten outputs.
  Parallelization: Wave 3 | Blocked by: 3 | Blocks: 5-final, 7, 12
  References: crucible lane B §(3),(4); `app/main.py:84-176`; `app/llm.py:111-173`; `app/orchestrator.py:478-709`; `app/geo.py:108`; `app/evidence.py:54`; `app/data.py:73-119` (fallback harness); `scripts/record_samples.py:21` (showcase inputs).
  Acceptance criteria: fresh clone, empty `.env`, Zetaris + Nightshift unreachable, `SAMPLE_MODE=true`: `python run.py --input input_examples/md-washington-county-unincorporated.json --sample` exits 0 with verdict `no-go` and a trace file with ≥2 agents, a critic event, model per request; `curl -X POST /runs` in sample mode completes; the 4 outputs differ and match the recorded samples' verdicts; a non-cached address returns a clear sample-mode message within 10 s; new tests green.
  QA scenarios: happy — the fresh-clone run above for all 4 inputs; failure — unknown address in sample mode → message, no hang. Evidence `.litclaude/evidence/m4-submission/task-10.txt`.
  Commit: Y | `feat(sample): sample mode runs the real agents on cached data, with run.py, examples and traces`

- [x] 11. Zetaris unified semantic layer (lane `zetaris`) — f0f2b9b (5 tables incl. materialized USL, 12 exploratory + 3 USL queries, DQ rule PASS, REFLECTION.md)
  Added 10/27 12:45 by user decision after reading HackOS "Zetaris Scoring Methodology" (`.litclaude/evidence/m4-submission/templates/zetaris-scoring.md`, card tagged REQUIRED).
  What to do / Must NOT do: Using the local Zetaris instance (check Docker Desktop is running: `/Applications/Docker.app/Contents/Resources/bin/docker ps`; Zetaris REST per `.env.example`, keys only via env), register ≥3 sources: existing moratoria CSV and state legislation CSV plus curated rules (`data/layers/rules.yaml`) and county sources (`data/layers/county_sources.yaml`) exported to CSV under `data/seed/` (or a REST source if quicker); run 2–3 exploratory queries per source; build 1 USL joining them (e.g. jurisdiction → moratoria → state bills → curated rules) and save its DDL to `zetaris/usl.sql`; 2–3 queries showing the USL is active; 1 data-quality rule shown to execute; script it all in `scripts/zetaris_usl.py` so setup is automated (DQ checklist: "data setup automated, including sources registered in Zetaris"); save query outputs to `zetaris/evidence/`. Optionally route one orchestrator lookup through the USL with the existing DuckDB fallback. Write the three reflection documents in `zetaris/REFLECTION.md` (time saved vs hand-coded with a small hand-coded comparison; would it help in your work; PM-style requirement to make the USL stronger). Must NOT break the existing Zetaris/DuckDB path or commit keys. If Zetaris cannot be started, write `BLOCKED` with the exact error and still deliver the DDL, scripts and reflection marked "not executed".
  Parallelization: Wave 2–3 | Blocked by: — | Blocks: 5-final, 7
  References: `app/seed.py:14-16`; `app/data.py:73-119`; `.env.example`; HackOS Zetaris docs list (Build Your First Unified Semantic Layer, Lightning SQL Reference) in Resources; `HANDOFF.md:80` (Zetaris connectivity check).
  Acceptance criteria: `scripts/zetaris_usl.py` runs end-to-end against local Zetaris and writes `zetaris/evidence/*.json` with ≥3 sources, ≥2 queries each, USL DDL, ≥2 USL queries, 1 DQ rule result; `zetaris/REFLECTION.md` has the 3 sections; pytest + ruff green.
  QA scenarios: happy — script run log; failure — Zetaris down → script exits non-zero with a clear message and DuckDB path still serves the app. Evidence `.litclaude/evidence/m4-submission/task-11.txt`.
  Commit: Y | `feat(zetaris): unified semantic layer over moratoria, legislation and curated rules`

- [x] 12. Dockerfile (lane `cursor` — developed in a Cursor session, per user) — 30d5b90; files written in a Cursor Agent CLI session (its shell was refused by the start-work guard), build/run/sample POST verified and committed by the muse fix lane; evidence task-12.txt
  Added 10/27 12:45 by user decision ("Dockerfile", and delegate some current work to a Cursor session so the Cursor sponsor line is truthful).
  What to do / Must NOT do: In a Cursor agent session (cursor-agent CLI in a herdr pane, or the Cursor IDE agent driven by the user if the CLI is unavailable), add `Dockerfile` + `.dockerignore`: python base, uv sync from lockfile, copy app/web/data/samples/scripts/run.py, expose 8000, default `SAMPLE_MODE=true`, `CMD uvicorn app.main:app --host 0.0.0.0 --port 8000`; document `host.docker.internal` for live Zetaris/Nightshift. Must NOT bake `.env` or keys into the image. Record in `task-12.txt` that it was produced in Cursor (session evidence: screenshot or Cursor transcript excerpt).
  Parallelization: Wave 3 | Blocked by: 10 (SAMPLE_MODE must work for the default container) | Blocks: 5-final
  References: DQ checklist "Can a judge run it" section; `pyproject.toml`, `uv.lock`.
  Acceptance criteria: `docker build -t sitewhy .` succeeds and `docker run -p 8001:8000 sitewhy` serves `/portfolio` and a sample-mode POST /runs; or BLOCKED if Docker is not available, with the Dockerfile linted by `hadolint` if present.
  QA scenarios: happy — container curl; failure — build error recorded. Evidence `.litclaude/evidence/m4-submission/task-12.txt`.
  Commit: Y | `build: Dockerfile for one-command sample-mode run`

## Final verification wave
> Runs in parallel after ALL todos. ALL must APPROVE. Surface the results, then complete the work; a commit and push still ask first.
- [x] F1. Plan compliance audit (probe exit 0, Approve, 0 HIGH, 14:2x KST) — interface probe on `http://localhost:8000/#/site/md-washington-county-unincorporated` to `.litclaude/evidence/m4-submission/F1-probe` exit 0 (0 HIGH); every Must-have maps to a commit or file.
- [x] F2. Code quality review (round 1 FAIL → 11874d0/07b7440; round 2 FAIL → 3b717fc/7fc5aa7/4952931; round 3 PASS 0 P0/P1; F2-review-r3.md) — `litclaude:quality-reviewer` on `git diff 2abf2aa..HEAD -- app web scripts tests`, plus a claims check: every README/deck number traced to evidence; no P0/P1; `F2-review.md`.
- [x] F3. Real Manual-QA (16/16 PASS at 4952931: fresh-clone 4 sample verdicts, 177 passed, 409/timeout 9 passed, live endpoints, deck 15 pp, video 206.6 s; F3-qa.md; UI 1440/390 covered by F1 probe) — fresh clone SAMPLE_MODE run; 4–5 showcase sites with badge and honest copy at 1440/390; 409 + timeout behaviour via test client; video frame grabs; deck PDF pages; README rendered; `F3-qa.md`.
- [x] F4. Scope fidelity (PASS; F4-scope.txt) — `git diff --stat 2abf2aa..HEAD` limited to the Scope files; no edits to existing samples; no mp4 tracked (`git ls-files "*.mp4"` empty); secret scan empty; `F4-scope.txt`.

## Commit strategy
One commit per todo with the message given; lanes stage only their files; orchestrator commits Todos 1, 4, 9; no AI attribution. Push only in Todo 6 after explicit approval, executed by the user.

## Stop rules
- Stop and report BLOCKED on: HackOS unreadable and the user has not pasted templates by 15:00 KST (then finalise docs on the recorded 6.x rules and flag it); Nightshift preflight failure (Todo 4 → N/A, continue); the same failure three times; any step needing push/upload/submit without approval; contradiction between README claims and evidence.
- Cut order if late: Todo 4 → Todo 3 parts (e) poll cap and (d) Markovian reset → deck polish → video narration (silent captions fallback). Never cut: Todo 2, Todo 3 (a)–(c), README, metadata.json, video, push gate.

## Success criteria
DoneClaim:
- Commits for Todos 1–3, 5, 7–9 (+4 if recorded); pytest + ruff green with the new tests; probe exit 0; F2 no P0/P1; F3 PASS; F4 clean; `submission/` holds templates, video script + recorder, deck pptx + pdf, SUBMISSION.md; mp4 present locally and untracked; README numbers traced; push either done by the user (remote URL + sha recorded) or explicitly deferred with commands; lanes closed, server health 200; receipt "no upload, no HackOS submission by the agent".

## Results (10/27)
- Repo public: https://github.com/wjgoarxiv/sitewhy, pushed by the user at 2b2cda0.
- Code: honest coverage copy + recorded-run badge (30fe8f9); run safety with 600 s deadline and 409 (9e77ab1, 11874d0); Abilene 50 MW sample (d3c4a13); Zetaris USL (f0f2b9b); sample mode on real agent logic with run.py, examples and traces (ca294d1, 103e822); county-source label fix (7fc5aa7); Dockerfile written in a Cursor Agent CLI session (30d5b90).
- Docs and media: README and metadata.json (fbf7692 … 2b2cda0); demo video 3:27 (local mp4, 3c66592/a12197e); deck 15 pages (b08f370 … 4952931); `submission/SUBMISSION.md` form answers.
- Verification: F1 probe 0 HIGH; F2 three rounds (FAIL → FAIL → PASS, 0 P0/P1); F3 16/16 PASS (fresh clone 4/4 sample verdicts, 177 tests); F4 clean (no secrets, mp4 or keys tracked).
- Deviations: Hagerstown replay gives needs_confirmation vs recorded conditional (model variance, disclosed). Cursor's shell was refused by the start-work guard, so a muse lane built, verified and committed its files. The mp4 narration still says "investigators" loosely (disclosed in script.md).
- Left to the user: upload the mp4 unlisted, paste the link and team fields, submit on HackOS before 10/28 08:45 KST. No upload or HackOS submission was done by the agent.
