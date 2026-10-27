# Demo video script — SiteWhy (Track: The Agent That Can Explain Why)

Narration says 'investigators' loosely; only the county investigator calls a model.

Final file: `OAH2026-SiteWhy-ExplainWhy-Demo.mp4` · 1920×1080 · h264+aac · target 2:30–3:30.
Narration: `say -v Samantha -r 185` (one aiff per line, mixed at shot times via `mux.sh`).
Recorder: [record.mjs](./record.mjs) · cards: [architecture.html](./architecture.html) ·
terminal: [terminal.html](./terminal.html) · mux: [mux.sh](./mux.sh).

Source honesty: every number/quote below is from a recorded sample, a committed
evidence file, or a real `run.py --sample` execution whose bytes the terminal shots
replay unedited (waiting cut). No secrets on screen: terminal shows only the command
line and the run's own trace output, never env values.
Hook count "321 moratoria across 32 states" per `judging/impact.md` (Electric Choice, 9/2026).
Scope flip: `md-washington-county-unincorporated` (No-go, place null, District 27 Fountain Head)
vs `md-hagerstown-city` (Conditional, place = Hagerstown city) — same county, different answer.
Critic-changes-work moment: Washington run, event 19 (round 1, critic, objections —
draft says six months, Moratorium Nation dataset says adopted ORD-2026-12 is 12 months)
→ event 20 (round 2, planner, targeted_tasks: "six months or twelve months?")
→ event 21 (round 2, county_investigator re-investigation). Fresh-take indices are
logged in `shots.json` as `critic_idx`; the committed sample carries 19→20→21.
Verifier's 180→182 correction (events 8/14/25) plays in the tour catches card.
Input-changes-output: `tx-abilene-ercot-50mw` vs `tx-abilene-ercot` (SB 6 + ERCOT audit
flip yes → no; Title V still decides, verdict stays Conditional).

| # | Time | Shot (URL / anchor) | Narration (≤ 14 words) | Rule 6.1 |
|---|------|---------------------|------------------------|----------|
| 1 | 0:04–0:15 | Title `architecture.html#title` | "Three hundred twenty-one moratoria block data centers across thirty-two states." / "Developers need one answer: is this site blocked, and why?" | problem, user |
| 2 | 0:15–0:33 | Architecture `architecture.html#arch` | "SiteWhy screens a site and proves why, rule by rule." / "Planner, county investigator (model) + rule evaluators (federal/state/grid, curated YAML), verifier, adjudicator, and critic check each other." | workflow, how the agent solves it |
| 3 | 0:33–0:54 | `#/site/md-washington-county-unincorporated` decisive + Recorded-run badge | "Outside Hagerstown, the county moratorium applies. Verdict: No-go." / "One verified quote decides it, with the math on screen." | key features, final output |
| 4 | 0:54–1:06 | `#/site/md-hagerstown-city` banner | "Two miles away, inside city limits, the same rule falls silent." / "Same county, different answer. That is the scope flip." | key features (applicability) |
| 5 | 1:06–1:36 | `#/demo` tour at 2×, catches card | "The verifier caught the duration: one-eighty days became one-eighty-two." | collaboration, feedback loop |
| 6 | 1:36–1:55 | Terminal: critic trace lines (real `logs/*.jsonl`) | "The critic rejected six months: the dataset says twelve." / "The planner sent round two. That is agents changing work." | one agent changes another's work |
| 7 | 1:55–2:21 | Terminal: live `run.py --sample` replay (real bytes) | "A real run, from an input file. Watch the agents hand off." / "Thirty-two trace lines, seven roles, verdict: No-go." | live run on real input |
| 8 | 2:21–2:34 | Lanes `[data-demo="lanes"]` on Washington site | "Every call names its model and receipt; Zetaris rows back the data." | Zetaris + Meterless (trace) |
| 9 | 2:34–2:48 | `#/site/tx-abilene-ercot-50mw` findings | "At fifty megawatts, two Texas findings flip to no." / "Same engine, new answer. That is input changing output." | recorded run, input variation |
| 10 | 2:48–3:02 | Terminal: `zetaris/usl.sql` + query counts + DQ PASS | "One semantic layer joins moratoria, bills, and curated rules." / "Data-quality rule: passed, zero violations." | Zetaris unified layer |
| 11 | 3:02–3:14 | Flips table + why chain + source link | "What would change it, the evidence chain, and a recorded-run badge." | output, confidence, limitations |
| 12 | 3:14–3:21 | End card `architecture.html#outro` (+ ~6 s static linger) | "SiteWhy: not which rules exist, but which apply to your site." | closing summary |

Sponsor-tech callouts (shots 2, 8, 10): Nightshift is the primary LLM route;
Nemotron Lightning extracts, Nemotron Ultra plans, synthesizes, and critiques;
verification itself is deterministic quote matching (`app/evidence.py:100`), not a model call.
Zetaris serves the moratoria + state_legislation lookups the agent loop queries
(`app/seed.py:15-16`); the `SITEWHY.usl_site_screen` layer
(3 USL queries: active_with_context 10 rows, washington_scope_flip 9 rows,
texas_ercot_rules 10 rows; DQ null_join_keys PASS, 0 violations)
is a separately demonstrated artifact, not queried by the loop. Meterless engines —
Markovian chunking and the World Model provenance graph — run inside the agent loop.
NVIDIA line: "Built with Nemotron on Nightshift."
