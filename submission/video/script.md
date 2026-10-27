# Demo video script v2 — SiteWhy (Track: The Agent That Can Explain Why)

Narration says "investigators" loosely in places; only the county investigator calls a model for extraction.

Final file: `OAH2026-SiteWhy-ExplainWhy-Demo.mp4` · 1920×1080 · 25 fps · h264+aac · ≤ 30 MB · 3:02 (181.7 s).
Why v2: v1 was mostly stills (cards and terminal replays). v2 is one continuous screen recording in
which something always moves: a gliding cursor with click ripples, eased scrolling, slow zoom/pan onto the
narrated element, a ring that draws around it, a lower-third caption (≤ 8 words, tagged AI or CODE where
the claim is about who did the work), a typed form entry and a run that streams.

Pipeline (all files in this folder):
`node cover.mjs OUT` (intro/outro from `docs/img/cover.webp`) · `node record.mjs OUT` (take.webm, shots.json,
audio/*.aiff) · `bash mux.sh OUT COVER_OUT FINAL.mp4`. Motion layer: [fx.js](./fx.js); engine: [stage.mjs](./stage.mjs);
terminal card for the Zetaris beat: [terminal.html](./terminal.html). `architecture.html` is not used in v2:
the HQ's own "Where AI is used" panel (six chips that light up during a run) replaces the old architecture card.
Narration: recorded with `say -v Samantha -r 185` at the cue time `record.mjs` logs for each line; the final cut replaces each line with a VoiceStudio (OmniVoice, voice design "female, young adult, american accent", seed 42) rendering placed at the same start time.

Recording setup: a SAMPLE_MODE server on port 8030 (`SAMPLE_MODE=true uv run uvicorn app.main:app --port 8030`),
never port 8000. The streamed run is a real `POST /runs` against that server: in SAMPLE_MODE the model answers are
replayed from the committed cache (the form says so on screen; the narration says so too), so it finishes in
under a minute where a live run takes minutes. The run button is disabled by the UI in SAMPLE_MODE; the recorder enables it
for this one submit. Permits is set to "No" because that is the cached input for this address.
The portfolio list is filtered in the page (Playwright route) to the showcase sites plus runs made during the take,
so old unrelated runs on the machine do not appear under "Your screenings".

Source honesty: every number and quote is on screen from the committed recorded reports or the live replay.
Hook count "321 moratoria and restrictions across 32 states" per README / `judging/impact.md` (Electric Choice, 9/2026).
Scope flip: `md-washington-county-unincorporated` (No-go; map chip "Washington County pause covers this
unincorporated site") vs `md-hagerstown-city` (Conditional; chip "Washington pause does not reach this site").
Critic round 2 (Washington recorded run): critic objects, "six months or twelve?"; planner re-plans; the
conflict is "resolved by code: applies under every conflicting reading". Verifier correction 180 → 182 days is
the first correction in "How it was checked". 50 MW contrast: `tx-abilene-ercot-50mw` — SB 6 and the ERCOT audit
do not apply at 50 MW (they apply from 76 MW); Title V still decides, verdict stays Conditional.
No secrets on screen: the Settings panel is never opened, keys are never read, the terminal shows only committed files.

| # | Time (s) | Beat (what moves) | Narration | Answers |
|---|----------|-------------------|-----------|---------|
| 0 | 0–8 | README motion cover, title caption fades in | "SiteWhy. Check a data center site, and see why." / 321 moratoria hook | what is it |
| 1 | 8–19 | HQ explainer: ring + cursor hop across the four "What you get" tiles, camera pushes in | "a verdict, the deciding rule, the math, and what would change it" | what do I get |
| 2 | 19–45 | Pick the Washington site; zoom to verdict, quote with highlighted "six (6) months", the CHECK math line, the flips table, the AI/code provenance chip | "No-go … quoted word for word … the math is on screen … what would change the answer … Nemotron read it, code verified it" | what do I get |
| 3 | 45–52 | Back to the explainer; ring hops over the six chips | "Six steps: four use a model, two are plain code" | where is AI used |
| 4 | 52–93 | Type the Hagerstown city address (zoomed form), set permits, submit; chips light up as events stream; captions name the model per step | Ultra plans; Lightning reads county sources; code checks quotes; Markovian chunks; retry then Ultra; Nightshift receipts + Zetaris; Ultra drafts, critic pushes back | where is AI used |
| 5 | 93–109 | Live result "Needs one more check" | "replays recorded model answers … says plainly what is unconfirmed" | honesty |
| 6 | 109–130 | Washington report: click "Replay how this verdict was built"; critic round 2 badge; code chips | "critic saw a conflict: six months, or twelve? … round two … code showed it applies either way" | agents change each other's work |
| 7 | 130–146 | Map of the unincorporated site, then the Hagerstown city map and verdict | "county pause covers this site … city limits, it does not reach … scope flip" | scope flip |
| 8 | 146–155 | 50 MW Abilene: banner then flips table | "fifty megawatts, two Texas rules stop applying" | input changes output |
| 9 | 155–165 | "How it was checked": 180 → 182 correction; "Who did the work" summary with receipts | "verifier recomputed a duration … every call lists its model and Nightshift receipt" | verification, Nightshift |
| 10 | 165–174 | Terminal types `zetaris/usl.sql` + evidence; ring on the DQ PASS line | "one semantic layer … zero violations" | Zetaris |
| 11 | 174–182 | Cover loop, repo URL | "SiteWhy: not which rules exist, but which apply to your site." | close |

Sponsor-tech callouts: Nightshift is the route for every model call (receipts in the model trace);
Nemotron 3 Ultra plans, drafts the verdict and plays the critic; Nemotron 3.5 Lightning extracts from county
sources (Ultra re-extracts if Lightning returns nothing); verification and applicability math are deterministic
code (`app/evidence.py`, `app/applicability.py`); Meterless Markovian chunks long documents and the World Model
holds the evidence graph; Zetaris serves the moratoria and state-legislation lookups and the
`SITEWHY.usl_site_screen` layer shown in the terminal beat (3 USL queries, DQ null_join_keys PASS, 0 violations).
NVIDIA line: "Built with Nemotron on Nightshift."
