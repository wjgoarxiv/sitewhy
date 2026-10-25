# dc-site-screener — Work Plan

## TL;DR (For humans)

**What you'll get:** A web app where you type any US address and a planned data center size in megawatts, and an AI agent tells you which federal, power-grid, state, and county rules actually apply to that project, which ones are deal-breakers, and why — with every claim tied to a quoted source and a date. It also re-screens a developer's whole list of candidate sites at once. Delivered with a public repo, slide deck, and a short demo video for the Open Agent Hackathon (Track 2).

**Why this approach:** A competitor already lists county rules with source links, so we win on reasoning, not listing: the agent works out whether each rule really applies to this specific project (size thresholds, exemptions, dates, generator emissions), connects power, permitting, and local opposition into one explanation, and shows when sources disagree. Several specialised agents share one evidence graph: a planner splits the question by layer, investigators gather rules, a verifier rejects any quote it cannot find in the source, and a critic attacks the draft verdict and sends weak links back for another round. NVIDIA Nemotron does all the reasoning — a small model on your Mac for bulk reading, a large cloud model for planning, judgment, and critique.

**What it will NOT do:** Give legal advice or guarantee approvals. Cover anything outside the US. Scrape commercial ordinance libraries or run engineering studies.

**Effort:** Large
**Risk:** Medium — sponsor data platform access arrives only at the onboarding call, and the free cloud model quota is tight
**Decisions to sanity-check:** Building in Claude Code (Cursor optional since 2026-10-22); implementing two Meterless engines from their open specs in Python (World Model as the shared evidence graph, Markovian for the long county investigation) rather than calling a hosted service, because Meterless ships specs, not a runtime; capping the critic loop at two rounds so a run stays under five minutes; seeding the county layer from an open moratorium dataset and verifying live rather than researching every county from scratch.

Your next move: do the human prerequisites below, then run start-work once the build window opens (22 Oct 2026, 00:00 UTC / 09:00 KST). The rules make any work committed before then ineligible.

---

> TL;DR (machine): Large, Medium risk — FastAPI + vanilla JS, Nemotron router (3.5 Lightning local / 3.5 Super cloud, 3 Ultra fallback only, RPM-aware), multi-agent orchestrator (planner ↔ layer investigators ↔ evidence verifier ↔ adjudicator ↔ critic, ≤2 revision rounds, escalation to needs-confirmation) over a Meterless World Model evidence graph (Python port of the spec, JSONL provenance log), Markovian chunked county investigation, Zetaris event instance (REST/MCP) w/ DuckDB fallback, deterministic applicability engine, 17-priority-state baseline (other states shown as "baseline pending"), Moratorium-Nation-seeded county layer + live verify, quote verifier, simple portfolio table, eval on 3 showcase sites + critic catch-rate, README + deck + video + metadata.json.

## Scope

### Revisions 2026-10-25 (supersede conflicting lines below)
- Execution order and scope cuts: `plans/roadmap.md` (thin slice → widen; 3 states TX/MD/AZ; seeded counties; HTML report, no map; portfolio table and live source discovery are stretch).
- Submission Requirements (HackOS, read 2026-10-24): Zetaris is the data layer; ≥1 Meterless engine in a working feature with a passing test; **Meterless Nightshift is the app's primary AI provider**; NVIDIA models go through Nightshift (NVIDIA award needs ≥1 Nemotron model via Nightshift and the model shown per request). Cursor is optional (announcement 2026-10-22); the build uses Claude Code and the Cursor award is not pursued.
- Nightshift (Mac M1-M4 edition) verified 2026-10-25 at `http://127.0.0.1:8088/v1`, bearer token read from `~/Library/Application Support/ai.meterless.nightshift.m1m4/runtime-token`, headers `meterless-app: sitewhy` and `meterless-scope: user`. Working models: `nvidia/nemotron-3.5-lightning-30b-a3b` (fast) and `nvidia/nemotron-3-ultra-550b-a55b` (strong; strip `<think>…</think>` from content). `nemotron-3-super-120b` returns 404 and 3.5 Super VL is not offered.
- Zetaris runs locally via Docker Compose in `~/zetaris-platform` (outside this repo), UI on http://localhost:3000. App connection values go in `~/.hackathon-keys.env`.
- `SAMPLE_MODE=true` fallback and HackOS templates (README, deck, metadata.json, demo script) are required parts of todos 14/15.

Source spec: `.litclaude/deep-interview/open-agent-hackathon-2026-spec.md`. Crucible packet + findings: `.litclaude/drafts/dc-site-screener.md`. Context: `.litclaude/deep-interview/open-agent-hackathon-2026-context.md`.

### Official rules (verified on event page 2026-10-17)
- 4.2 Work committed before 2026-10-22 00:00 UTC is not eligible, except clearly declared pre-existing components
- 5.1 Every submission must integrate Zetaris AND Meterless (Cursor requirement dropped 2026-10-22)
- 5.2 Integrate NVIDIA technology wherever it contributes
- 5.4 Pre-existing open-source libraries fine; pre-existing product code must be declared
- 6.1 Demo video 1–4 min showing main workflow, how the agent solves the challenge, key features, how Zetaris and Meterless are integrated
- 6.2 Slide deck: problem + users, solution, workflow/architecture, stack, Zetaris + Meterless usage, what was unique about sponsor tech use, product visuals, future enhancements
- 6.3 GitHub repo with all source + README (setup, usage, dependencies)
- 6.4 Explanation: Zetaris + Meterless integration, where NVIDIA contributes, what was unique
- 9.1 Entrant keeps all IP; 9.2 organizer gets promotional license
- 10.3 Questions: hackathons@genai.works
- Prize stacking (track + Nemotron): not stated

### Human prerequisites (user)
- Registration: done 2026-10-18 (solo team "SiteWhy" created on HackOS; onboarding checklist 3/3). Official close is 2026-10-22 23:45 UTC (10/23 08:45 KST)
- NVIDIA API key → `NVIDIA_API_KEY`: wait for the credit-claim instructions NVIDIA will add to its HackOS folder before the window; `nemotron-3-super-120b-a12b` on build.nvidia.com shows "deprecated on 10/19/2026"; replacement chosen 2026-10-18: `nvidia/nemotron-3.5-super-vl-120b-a12b` (free endpoint, early access, 262K context, function calling), fallback `nvidia/nemotron-3-ultra-550b-a55b` (free endpoint, 1M context). Re-check both pages on day 1
- Search API key: not needed to start (decided 2026-10-18). Optional `SEARCH_API_KEY` (Tavily or Brave) only if live county search is added mid-window
- `ollama pull nemotron-3.5-lightning:30b-mlx` (19GB) before the window
- Onboarding call 2026-10-21 12:00 UTC (21:00 KST): get Zetaris shared-instance credentials + team prefix; ask (a) confirm that World Model + Markovian implemented from the Meterless specs counts as integration, (b) track + Nemotron prize stacking, (c) how NVIDIA credits are claimed
- No product code or repo commits before 2026-10-22 00:00 UTC (rule 4.2); accounts, Cursor install, and model pulls are fine
- Meterless: read the engine guides in the HackOS Meterless folder and github.com/Meterless/Meterless before the window (no account needed)

### Resource hub findings (HackOS Resources, read 2026-10-18)
- Judges discount single-agent systems presented as agent systems, linear A→B→C pipelines, hardcoded demo paths, and sponsor tech bolted on at the end. They reward planner/executor/evaluator iteration, critique or validation between agents, shared state, branching, retries, escalation, and clear traces. Applied 2026-10-18: see "Agent architecture" below and todos 16–17
- Meterless is not a model host. It ships open-source, provider-agnostic agent engines (World Model: entities, relationships, provenance; Markovian: bounded-context long-task reasoning; H-MEM: hierarchical memory) that take any OpenAI-compatible generator and emit JSONL audit trails. The engines are implementation specs (AGENTS.md-driven, Apache-2.0, TypeScript reference in `engines/world-model/reference/`), not runtime libraries: you implement them in your own stack. Best fit here: World Model as the shared, provenance-stamped rule/evidence graph (todo 16); Markovian for the long county investigation (todo 10). Submission must say which engines were mounted and where, in the README and `metadata.json`. The Meterless hackathon starter README maps each command to the engine service behind it; mirror that mapping in our README
- NVIDIA provides Nemotron credits through API keys; claim steps are still TBC in its folder
- Submission also expects logs or traces, sample inputs and outputs for more than one case, a clean-setup run, `.env.example`, and a `SAMPLE_MODE=true` style fallback when public APIs fail
- Data prepared before the window is allowed if declared as a pre-existing component in the submission form
- Team composition locks when the first submission is created. Additional challenges and prizes are announced at the 10/21 onboarding call

### Agent architecture (revised 2026-10-18 after reading the judging guidance)
Roles are distinct, interact more than once per run, and share one state store. Every message between roles is a typed event appended to the World Model log and streamed to the UI trace.

| Role | Model / implementation | Reads | Writes | Can send work back to |
| --- | --- | --- | --- | --- |
| Planner | Nemotron 3.5 Super (cloud) | jurisdiction, project facts, critic objections | investigation tasks per layer, with source hints and budget | itself (re-plan after objections) |
| Layer investigators (federal+ISO, state, county) | Lightning (local) for extraction; county uses the Markovian chunked loop | tasks, seed layers, fetched sources | candidate rules + claims with quotes into the World Model | — |
| Evidence verifier | deterministic quote check (todo 6) + Lightning `verify_support` (does the quote support the claim?) | claims | verdict per claim: verified / not_found / unsupported | investigator (retry with another source, max 2) |
| Applicability tool | deterministic Python (todo 8), called by the adjudicator | rules, project facts | applies yes/no/unknown + computed values | — |
| Adjudicator | Nemotron 3.5 Super | verified claims, applicability results, conflicts | draft verdict + why-chain | — |
| Critic | Nemotron 3.5 Super with a separate red-team prompt and temperature (scope decision 2026-10-18; 3 Ultra only as fallback if 3.5 Super is unavailable) | draft verdict + World Model graph | objections: unsupported why-chain link, missed exemption, unresolved source conflict, threshold misread | planner (targeted re-investigation) |

Loop: plan → investigate → verify (with retries) → adjudicate → critique → if objections and round < 2: planner issues only the targeted tasks, then re-adjudicate → else escalate each unresolved objection to `needs_confirmation`. Hard stops: 5-minute wall clock, cloud RPM budget. Fallbacks: cloud unavailable → local Lightning runs every role with a "degraded" badge; public API down → `SAMPLE_MODE=true` serves cached sources.

### Must have
- Input: US address or lat/lon + MW (+ optional backup generation type). Output per layer (federal, ISO/RTO, state, utility, county/city): rules with grade fatal/major/minor/info, applicability reasoning ("applies because 300MW > 75MW threshold"; "moratorium exempts projects with permits filed before X"), citation (verbatim quote + URL + as-of), "needs confirmation" flags, source-conflict notes
- Cross-layer "why" chain: one narrative linking power, permits, water, local opposition to the overall go / conditional / no-go
- Nemotron for every reasoning step; per-step model/latency/tokens visible in UI; RPM-aware throttling and caching
- Zetaris for pipeline DB ⨝ baseline/moratoria joins (portfolio view) — mandatory (rule 5.1); DuckDB only for local tests
- Meterless integration — mandatory (rule 5.1): World Model engine (todo 16) is the shared state every agent reads and writes; Markovian engine drives the county investigation (todo 10); both documented in README + `metadata.json`
- Multi-agent loop with critique and recovery (todo 17): distinct roles, verifier retries, critic objections that trigger targeted re-investigation, escalation to needs-confirmation, full trace
- All model calls go through Meterless Nightshift (primary AI provider); per-request model shown in the trace
- Seed data: Census Geocoder, EIA-861 (county→utility, ISO flags), Moratorium Nation CSVs (CC-BY-4.0, attribution), eCFR + Federal Register APIs, Aqueduct 4.0 (CC BY 4.0)
- Showcase: ERCOT TX site, PJM county under 2026 moratorium (Washington County MD), western water-stressed site (Pima County AZ); plus live run on an arbitrary address
- Replay mode for the demo

### Must NOT have (guardrails, anti-slop, scope boundaries)
- No legal-advice language or approval guarantees; one-line "screening, not legal advice" notice
- No non-US jurisdictions; no prebuilt research of all 3,000+ counties beyond the seed dataset
- No scraping of Municode, eCode360, American Legal; link out instead and say "ordinance text not retrieved"
- No fabricated citations: unverified claim ⇒ "needs confirmation", never fatal
- No power-flow/hydrology studies, no parcel-level GIS
- No auth, multi-user, mobile-specific work
- No own-AWS Zetaris deployment or Docker install without explicit user approval (ongoing cost)
- No redistribution of all-rights-reserved trackers (e.g. GT 50-state survey) — reference links only
- No employer-internal data or code

## Verification strategy
> Zero human intervention — every verification step is agent-executed.
- Test decision: TDD for pure logic (resolver mapping, quote verifier, applicability engine, verdict schema, router accounting/throttle); tests-after for I/O adapters. pytest (+ pytest-asyncio), ruff
- Live tests marked `@pytest.mark.live`, skipped without keys
- Manual-QA channel per criterion: HTTP (`curl`) for API; browser (claude-in-chrome) for UI; CLI for baseline build and eval
- Evidence: .litclaude/evidence/dc-site-screener/task-<N>.<ext>; record criteria and blockers in the litgoal ledger

## Execution strategy
### Parallel execution waves
> Target 5-8 todos per wave. Fewer than 3 (except the final wave) means you under-split.

- Wave 1: 1, 4, 5, 6, 8 (skeleton, resolver, seed layers, quote verifier, applicability engine — pure/independent)
- Wave 2: 2, 3, 7, 16 (router, data harness, source discovery, World Model engine)
- Wave 3: 9, 10, 11 (state baseline, county investigator, adjudicator)
- Wave 3b: 17 (orchestrator + critic loop)
- Wave 4: 12, 13, 14 (UI + portfolio, eval, replay)
- Wave 5: 15 (package + submit)

### Dependency matrix
| Todo | Depends on | Blocks | Can parallelize with |
| --- | --- | --- | --- |
| 1 | — | 2,3,7,12,16 | 4,5,6,8 |
| 2 | 1 | 9,10,11,17 | 3,7,16 |
| 3 | 1,5 | 9,11,12 | 2,7 |
| 4 | — | 10,11,12 | 1,5,6,8 |
| 5 | — | 3,9,10,11 | 1,4,6,8 |
| 6 | — | 9,10,17 | 1,4,5,8 |
| 7 | 1 | 9,10 | 2,3 |
| 8 | — | 11,17 | 1,4,5,6 |
| 9 | 2,3,5,6,7,16 | 11,13 | 10 |
| 10 | 2,4,5,6,7,16 | 11,13,17 | 9 |
| 11 | 2,3,4,8,9,10,16 | 17 | — |
| 12 | 3,4,17 | 14,15 | 13 |
| 13 | 9,10,17 | 15 | 12,14 |
| 14 | 12,17 | 15 | 13 |
| 15 | 12,13,14 | F1-F4 | — |
| 16 | 1 | 9,10,11,17 | 2,3,7 |
| 17 | 2,6,8,10,11,16 | 12,13,14 | — |

## Todos
> Implementation + Test = ONE todo. Never separate them.
> Rows start at column zero as `- [ ] N. <title>`; start-work cannot see an indented row.
<!-- APPEND TASK BATCHES BELOW THIS LINE — never rewrite the headers above. -->
- [x] 1. Project skeleton (uv, FastAPI, pytest, ruff, config)
  What to do / Must NOT do: `app/` (FastAPI), `tests/`, `data/`, `eval/`, `pyproject.toml` via uv (Python 3.12+), `.env.example` (NVIDIA_API_KEY, OLLAMA_BASE_URL, ZETARIS_REST_URL, ZETARIS_API_KEY, ZETARIS_ORG_ID, ZETARIS_PREFIX, SEARCH_API_KEY), `/health`. `git init` only with user approval. Must NOT commit secrets.
  Parallelization: Wave 1 | Blocked by: — | Blocks: 2,3,7,12,16
  References (the executor has NO interview context — be exhaustive): spec `.litclaude/deep-interview/open-agent-hackathon-2026-spec.md`; draft `.litclaude/drafts/dc-site-screener.md`; env: macOS M5 Pro 48GB, uv, Node 22, Ollama, LM Studio, no Docker
  Acceptance criteria (agent-executable): `uv run pytest -q` passes; `uv run ruff check .` clean; `curl -s localhost:8000/health` → `{"status":"ok"}`
  QA scenarios (name the exact tool + invocation): happy: uvicorn + curl /health; failure: no .env → app boots, live features report "not configured". Evidence .litclaude/evidence/dc-site-screener/task-1.txt
  Commit: Y (with approval) | chore(init): project skeleton

- [ ] 2. Nemotron model router (step routing, accounting, RPM throttle, cache)
  What to do / Must NOT do: One OpenAI-compatible client pointed at Meterless Nightshift (`http://127.0.0.1:8088/v1`, bearer token from the Nightshift runtime-token file, headers `meterless-app: sitewhy`, `meterless-scope: user`, 180 s timeout). Routing: `nvidia/nemotron-3.5-lightning-30b-a3b` for `extract`/`classify`/`verify_support`; `nvidia/nemotron-3-ultra-550b-a55b` for `plan`/`synthesize`/`critique` (strip `<think>…</think>`). Status from `GET /v1/models`: 401/403 unauthorized, 200 online, else offline. Fallbacks: local Ollama at http://localhost:11434/v1 only when Nightshift is offline, then `SAMPLE_MODE` cached responses. Token-bucket limiter (default 30 RPM cloud), retry w/ backoff on 429, disk cache keyed by (model, prompt hash). Per-call trace: step, model, latency, tokens. Expose a `generate(step, messages, tools?)` callable that the Meterless engines (todos 10, 16) receive as their injected generator, per the engines' provider-agnostic contract. Role names (planner, investigator, verifier, adjudicator, critic) are part of the trace. Must NOT call non-Nemotron models.
  Parallelization: Wave 2 | Blocked by: 1 | Blocks: 9,10,11,17
  References: draft findings "Nemotron" (build.nvidia.com pages, ollama.com/library/nemotron-3.5-lightning); ~40 RPM free tier UNPROVEN
  Acceptance criteria: unit tests (fake transport) for routing table, accounting, limiter, cache hit, injected-generator contract; `pytest -m live -k router` gets completions from Lightning and Ultra through Nightshift, and the trace records the answering model
  QA scenarios: happy: live probe both; failure: 429 burst → backoff then success; no cloud key → typed error, local steps OK. Evidence .litclaude/evidence/dc-site-screener/task-2.txt
  Commit: Y | feat(router): nemotron step router

- [ ] 3. Data harness: Zetaris adapter (REST primary, MCP if available) + DuckDB fallback
  What to do / Must NOT do: `DataHarness` interface (`list_sources`, `query(sql)`, `register_table`). Zetaris impl against the shared event instance using REST (API key, org ID, REST URL; Management → API Tokens) per github.com/zetaris/getting-started; if onboarding provides MCP endpoint, add MCP client using `zetaris.list_sources`/`zetaris.query`. Upload/register Parquet/CSV (pipeline_sites, state_baseline, moratoria, federal/ISO rules) under team prefix. Synthetic `pipeline_sites(site_id,name,lat,lon,mw,stage,target_cod,backup_gen)` with 3 showcase + ~12 others. DuckDB impl over same files. Trace shows backend per query. Must NOT touch other teams' objects; no own-AWS deploy without approval.
  Parallelization: Wave 2 | Blocked by: 1,5 | Blocks: 9,11,12
  References: https://github.com/zetaris/getting-started (START-HERE.md, open_data/parquet_csv recipes, claude-code-connection.html, client-setup.html)
  Acceptance criteria: DuckDB unit tests; `pytest -m live -k zetaris` lists sources and runs `pipeline_sites ⨝ moratoria` within team prefix
  QA scenarios: happy: portfolio join returns showcase rows w/ flags; failure: Zetaris unreachable → BLOCKED recorded in trace + DuckDB serves. Evidence .litclaude/evidence/dc-site-screener/task-3.txt
  Commit: Y | feat(data): zetaris harness

- [ ] 4. Jurisdiction resolver (address → state, county FIPS, place/CCD, utilities, ISO/RTO)
  What to do / Must NOT do: Census Geocoder `geographies/onelineaddress` and `geographies/coordinates` (benchmark Public_AR_Current, vintage Current_Current); fall back to county subdivision when no incorporated place; EIA-861 2025 Service Territory (county→utilities) + Utility Data (ISO/RTO flags, NERC region) → candidate utilities/ISO with "multiple utilities serve this county" ambiguity flag. Cache responses + EIA tables under `data/geo/`. Must NOT use paid geocoders; no reliance on deactivated HIFLD endpoints.
  Parallelization: Wave 1 | Blocked by: — | Blocks: 10,11,12
  References: https://geocoding.geo.census.gov/geocoder/ ; https://www.eia.gov/electricity/data/eia861/ (f8612025.zip); PUDL alt https://docs.catalyst.coop/pudl/en/stable/data_sources/eia861.html
  Acceptance criteria: TDD with recorded fixtures: TX showcase → ERCOT; Washington County MD (FIPS 24043) → PJM; Pima County AZ (04019) → non-ISO (WECC); non-US → 422
  QA scenarios: happy: 3 showcase addresses live; failure: unparseable address → 422 with message. Evidence .litclaude/evidence/dc-site-screener/task-4.txt
  Commit: Y | feat(geo): jurisdiction resolver

- [ ] 5. Seed layers: federal + ISO rules (curated) and open datasets (ingested)
  What to do / Must NOT do: `data/layers/federal.yaml`, `iso.yaml` entries {id, layer, title, applies_if (machine-checkable predicates), summary, quote, source_url, as_of, status (final|proposed|pending)}: FERC June 18 2026 show-cause orders (EL26-67..72) + PJM co-location order (EL25-49), FERC RM26-4 ANOPR (>20MW), EO 14318 (>100MW), EPA Title V (40 CFR 70.2 via eCFR API), NSPS KKKKa turbines (91 FR 1910), RICE NESHAP ZZZZ emergency-engine hours, CWA (NPDES/stormwater/pretreatment); ERCOT: TX SB 6 + PUCT 16 TAC §25.194 (draft status). Ingest Moratorium Nation `moratorium_inventory.csv` + `state_legislation.csv` (github.com/mjbommar/moratorium-data-2026, CC-BY-4.0 — keep attribution) and Aqueduct 4.0 basin indicators to Parquet. Must NOT hardcode FERC deadlines (link eLibrary); quotes verbatim only.
  Parallelization: Wave 1 | Blocked by: — | Blocks: 3,9,10,11
  References: draft findings "Data"; https://www.ecfr.gov ; https://www.federalregister.gov ; https://www.wri.org/data/aqueduct-global-maps-40-data
  Acceptance criteria: schema validation tests; every entry has source_url + as_of + status; Moratorium CSV row count asserted and recorded; ≥95% quotes verified by todo 6
  QA scenarios: happy: load + validate all; failure: entry lacking source → test fails. Evidence .litclaude/evidence/dc-site-screener/task-5.txt
  Commit: Y | feat(layers): federal, ISO, and seed datasets

- [ ] 6. Evidence fetcher + verbatim quote verifier
  What to do / Must NOT do: fetch HTML→text (readability) and PDF→text (pypdf), cache by URL hash with fetched_at; `verify(quote, url)` normalizes whitespace/Unicode/ligatures/hyphenation and checks containment → {status verified|not_found|unverifiable, matched_span, fetched_at}. Respect robots.txt; skip blocked platforms. Must NOT use an LLM for the verdict; no fuzzy "verified".
  Parallelization: Wave 1 | Blocked by: — | Blocks: 9,10,17
  References: spec acceptance (≥95% verbatim)
  Acceptance criteria: TDD tests: exact, whitespace-variant, ligature, absent, PDF fixture, 403/timeout → unverifiable
  QA scenarios: happy: verify an eCFR 70.2 quote live; failure: 404 → unverifiable. Evidence .litclaude/evidence/dc-site-screener/task-6.txt
  Commit: Y | feat(evidence): quote verifier

- [ ] 7. Source discovery adapter (keyless default, web search optional)
  What to do / Must NOT do: default provider needs no key: Moratorium Nation source URLs for the resolved jurisdiction, Federal Register/eCFR search, and Legistar Web API (webapi.legistar.com) matters/minutes where the county has a client (public access UNVERIFIED; check on day 1). Optional web-search provider (Tavily or Brave) behind the same interface, enabled only when `SEARCH_API_KEY` is set; without it, uncovered counties return "needs confirmation". Query templates for the optional provider for county/state DC rules ("<county> <state> data center moratorium", "data center zoning ordinance", "board minutes data center"); rank .gov/.us and official county domains first; exclude Municode/eCode360/American Legal from fetch (keep as link-out). Must NOT exceed provider terms; cache results.
  Parallelization: Wave 2 | Blocked by: 1 | Blocks: 9,10
  References: draft "Must NOT scrape ordinance platforms"
  Acceptance criteria: unit test with recorded responses; keyless live test returns ≥1 official source URL for Washington County MD; with no `SEARCH_API_KEY` the optional provider is skipped without error
  QA scenarios: happy: live query; failure: quota exceeded → typed error. Evidence .litclaude/evidence/dc-site-screener/task-7.txt
  Commit: Y | feat(search): search adapter

- [ ] 8. Applicability engine (deterministic threshold + exemption checks)
  What to do / Must NOT do: pure-Python predicates evaluated against project facts {mw, backup_gen type/count/size (default estimate: N+1 diesel gensets sized from MW), permits_filed_date, incorporated?}: MW thresholds (SB 6 75MW, ANOPR 20MW, EO 14318 100MW, state rules), generator potential-to-emit estimate vs Title V 100 tpy and RICE emergency hours, moratorium effective/expiry dates and exemption clauses, unincorporated-area applicability. Output {applies: yes|no|unknown, reason, computed_values}. Assumptions shown explicitly. Must NOT let an LLM decide threshold math.
  Parallelization: Wave 1 | Blocked by: — | Blocks: 11,17
  References: todo 5 `applies_if` schema; user strength = engineering calcs (differentiator vs Spark)
  Acceptance criteria: TDD table tests per predicate incl. boundary values (74.9/75/75.1 MW), date edges, unknown inputs → `unknown`
  QA scenarios: happy: 300MW TX site → SB 6 applies with computed reason; failure: missing generator info → `unknown` + assumption note. Evidence .litclaude/evidence/dc-site-screener/task-8.txt
  Commit: Y | feat(rules): applicability engine

- [ ] 9. State baseline batch researcher (17 priority states)
  What to do / Must NOT do: CLI `uv run python -m app.baseline build [--states ...]`: per state fields {large_load_tariff_or_rule, dc_tax_incentive, pending_or_enacted_dc_legislation, statewide_pause_or_executive_action, water_rule}; seed from Moratorium Nation state_legislation + search; Lightning extracts, Super adjudicates; verify quotes; write `data/layers/state_baseline.parquet` and register in harness. Scope (decision 2026-10-18): only the 17 priority states TX, VA, GA, AZ, OH, IL, OR, NV, NC, PA, IN, IA, NE, UT, WA, MD, NY; every other state is written as a `pending` row with reason "baseline pending" and the UI says so. The CLI accepts `--states` so more can be added if time remains. Throttled to router RPM. Must NOT store unverified quotes as verified; GT survey only as link.
  Parallelization: Wave 3 | Blocked by: 2,3,5,6,7,16 | Blocks: 11,13
  References: draft findings "State layer"; EEI Large Load Projects and Tariffs (Sep 2026) PDF for docket pointers
  Acceptance criteria: all 17 priority states complete; ≥95% quotes verified; the other 33 states + DC present as `pending` rows with reason
  QA scenarios: happy: build TX,MD,AZ and inspect rows; failure: search error → state `pending`. Evidence .litclaude/evidence/dc-site-screener/task-9.txt
  Commit: Y | feat(baseline): state baseline builder

- [ ] 10. County/city investigator (seeded + live verification, Meterless Markovian loop)
  What to do / Must NOT do: given resolved county/place: pull matching Moratorium Nation instruments (geo/jurisdiction match); then live: discover sources (7), fetch (6), and run the extraction as a Meterless Markovian chunked loop (Python port of engines/markovian spec: bounded chunks, compressed carryover state of open questions + found rules, `maxChunks` cap) so long minutes/ordinance PDFs never exceed a fixed context; Lightning extracts status/dates/exemptions/zoning requirements; every candidate claim goes to the World Model (16) for the verifier. Log projected-vs-actual token savings per run (Markovian's demo metric). Reconcile seed vs live (newer wins, conflicts written as `contradicts` edges). Accept targeted re-investigation tasks from the orchestrator (17). Timebox ≤3 min, stream progress. Must NOT present unverified rule as fact.
  Parallelization: Wave 3 | Blocked by: 2,4,5,6,7,16 | Blocks: 11,13,17
  References: 2026 moratoria in context.md (Boone/Grant IN, Washington/Worcester MD, Pima AZ, Knox TN); https://github.com/Meterless/Meterless/tree/main/engines/markovian (README savings model, AGENTS.md)
  Acceptance criteria: Washington County MD → active moratorium with verified quote, dates, and exemption text if present; seed/live conflict surfaced in a fixture test; Markovian unit test: carryover stays ≤ configured size across 10 chunks and the savings log is written
  QA scenarios: happy: Washington County MD; failure: county with nothing → "no county-specific DC rules found (searched N sources, seed: 0)". Evidence .litclaude/evidence/dc-site-screener/task-10.txt
  Commit: Y | feat(county): seeded live investigator

- [ ] 11. Adjudicator: verdict synthesizer (cross-layer why-chain)
  What to do / Must NOT do: the adjudicator role in the agent loop (17); reads verified claims from the World Model. Inputs: jurisdiction, project facts, rules from all layers (federal/ISO/state via harness join, county), applicability results (8). Super/Ultra writes pydantic-validated JSON {layers[{layer, rules[{id, grade, applies, why, citation{quote,url,as_of,status}}]}], why_chain (ordered narrative linking power/permits/water/local), conflicts[], decisive_layer, overall go|conditional|no_go, needs_confirmation[]}. Every why_chain link cites World Model node IDs so the critic can check it. Re-prompt on schema failure. Must NOT grade fatal unless verified AND applies=yes.
  Parallelization: Wave 3 | Blocked by: 2,3,4,8,9,10,16 | Blocks: 17
  References: spec output definition; competition gap list in draft
  Acceptance criteria: schema tests; invariant test "unverified or applies≠yes ⇒ not fatal"; valid JSON for all 3 showcase sites
  QA scenarios: happy: TX → conditional (SB 6 costs/curtailment), MD → no_go (moratorium), AZ → conditional (water); failure: invalid JSON → repaired or typed error. Evidence .litclaude/evidence/dc-site-screener/task-11.json
  Commit: Y | feat(verdict): synthesizer

- [ ] 12. API + web UI (map, layered report, why-chain, evidence, model trace, simple portfolio table)
  What to do / Must NOT do: `POST /screen {address|lat,lon, mw, backup_gen?}` w/ SSE progress; `GET /portfolio` screens all pipeline sites against prebuilt layers via one Zetaris join (no live calls) and returns one row per site {site, state, county, mw, decisive flag, top risk, baseline status}; the UI shows it as a plain sortable table with a "screen this site" link per row (scope decision 2026-10-18: no portfolio map, charts, or drill-down); vanilla JS + Leaflet (CDN): form, map pins, why-chain panel, layer cards with grade colors, expandable quote/link/as-of/status, conflict and "needs confirmation" badges, model-routing panel, agent-loop trace (role, round, objection, retry, escalation) and a World Model graph view of the evidence behind each why-chain link, Moratorium Nation attribution, "screening, not legal advice" line. Must NOT add frontend build tooling.
  Parallelization: Wave 4 | Blocked by: 3,4,17 | Blocks: 14,15
  References: judging weights Demo 15 / UX 10 / Sponsor 10
  Acceptance criteria: curl POST returns schema-valid report; browser QA renders 3 showcase reports + portfolio with no console errors
  QA scenarios: happy: browser run on Pima County AZ; failure: MW ≤ 0 → inline validation. Evidence .litclaude/evidence/dc-site-screener/task-12.png
  Commit: Y | feat(ui): screening web app

- [ ] 13. Showcase ground truth + eval harness
  What to do / Must NOT do: `eval/ground_truth.yaml` for 3 showcase sites (hand-verified decisive layer, key rule ids, expected overall, expected applicability values); `uv run python -m eval.run` reports decisive-layer match, applicability match, citation coverage (100%), verified-quote rate (≥95%), latency (≤5 min), and critic catch-rate on seeded faults (fixtures with a wrong threshold, a missing exemption, and an unsupported quote; the loop must catch ≥2 of 3 and end with correct grades or needs_confirmation). Must NOT tune prompts on eval without logging changes.
  Parallelization: Wave 4 | Blocked by: 9,10,17 | Blocks: 15
  References: spec acceptance criteria
  Acceptance criteria: all thresholds pass on 3 sites
  QA scenarios: happy: full eval; failure: miss → report names metric + site. Evidence .litclaude/evidence/dc-site-screener/task-13.json
  Commit: Y | test(eval): showcase eval harness

- [ ] 14. Replay mode for demo
  What to do / Must NOT do: record full run (SSE events + report + trace) to `runs/<site>.jsonl`; `?replay=<site>` streams with original timing × speed factor; UI shows "Recorded run" badge. Must NOT label replay as live.
  Parallelization: Wave 4 | Blocked by: 12,17 | Blocks: 15
  References: spec decision boundary "live demo unstable → recorded runs"; todo 12 SSE format
  Acceptance criteria: replayed report byte-identical to recorded; badge visible
  QA scenarios: happy: browser replay; failure: missing run → 404 message. Evidence .litclaude/evidence/dc-site-screener/task-14.png
  Commit: Y | feat(demo): replay mode

- [ ] 15. README, deck, demo video, sponsor-tech write-up, submission
  What to do / Must NOT do: README (problem, users, why-chain + applicability differentiator vs listing tools, agent-role diagram with the critique loop, a command → Meterless engine service map, architecture diagram, Nemotron routing rationale with measured latency/tokens, Zetaris usage, data licenses/attribution, setup, eval results, limitations); slide deck covering every rule 6.2 item; declaration of pre-existing components (none expected); 1–4 min demo video script that shows Zetaris and Meterless integration (rule 6.1) (MD no-go → TX conditional → AZ water → portfolio → live arbitrary address); sponsor-tech explanation per rule 6.4 (Zetaris, Meterless engines and where they are mounted, NVIDIA role (Nemotron via Nightshift), what was unique); `metadata.json` naming the Meterless engines and NVIDIA models used; sample inputs/outputs for ≥3 cases; submit via HackOS. Must NOT claim accuracy beyond eval numbers; no AI attribution in commits/PRs.
  Parallelization: Wave 5 | Blocked by: 12,13,14 | Blocks: F1-F4
  References: judging weights (Impact 30, Technical 20, Innovation 15, Demo 15, UX 10, Sponsor 10); official rules 6.1–6.4 (Scope section)
  Acceptance criteria: fresh clone → README steps run app; README eval numbers equal eval output; submission confirmation captured
  QA scenarios: happy: follow README in clean dir; failure: missing key → troubleshooting section covers it. Evidence .litclaude/evidence/dc-site-screener/task-15.md
  Commit: Y | docs: readme, deck, demo

- [ ] 16. Meterless World Model engine (Python port) as the shared evidence graph
  What to do / Must NOT do: implement the World Model spec (github.com/Meterless/Meterless engines/world-model AGENTS.md: entity, context, relationship records; content-derived stable hash IDs; idempotent append-only ingest log; versioned schema; derived views rebuildable from the log) in `app/worldmodel/` over SQLite or DuckDB. Domain mapping: entities = jurisdiction, project, rule, source_document, claim; contexts = screening run, layer; relationships = applies_to, cites, supports, contradicts, supersedes, exempts, objection_on. Every write carries provenance (agent role, model, round, source URL, fetched_at). JSONL event log per run in `runs/<run_id>/worldmodel.jsonl` (submission evidence). Read surface: `claims_for(layer)`, `conflicts()`, `evidence_path(node_id)`, `open_objections()`. Must NOT vendor the TypeScript reference into the repo; credit the spec (Apache-2.0) in README.
  Parallelization: Wave 2 | Blocked by: 1 | Blocks: 9,10,11,17
  References: https://github.com/Meterless/Meterless/tree/main/engines/world-model (README, AGENTS.md, docs/aggregate-shapes.md, reference/scripts/idempotency-check.ts for the core invariant); HackOS Meterless folder (AGENT ENGINES INDEX)
  Acceptance criteria: TDD: re-ingesting the same claim yields the same ID and no duplicate (idempotency, mirrors the reference check); rebuilding views from the log reproduces query results; `contradicts` edge created for conflicting seed vs live claims; `evidence_path` returns quote → source → rule chain
  QA scenarios: happy: ingest Washington County MD fixture and print the evidence path for the moratorium rule; failure: write without provenance → rejected with typed error. Evidence .litclaude/evidence/dc-site-screener/task-16.txt
  Commit: Y | feat(worldmodel): meterless world model engine

- [ ] 17. Agent orchestrator with verifier retries, critic loop, and escalation
  What to do / Must NOT do: `app/agents/` implementing the roles and loop in "Agent architecture": planner → layer investigators (federal+ISO, state, county from todo 10) → evidence verifier (todo 6 + Lightning `verify_support`, up to 2 retries per claim with a different source) → adjudicator (todo 11, applicability via todo 8) → critic (3.5 Super with a separate red-team prompt; 3 Ultra only as fallback) returning typed objections {kind: unsupported_link|missed_exemption|unresolved_conflict|threshold_misread, node_ids, ask}. Objections become `objection_on` edges in the World Model; planner issues only targeted tasks; max 2 revision rounds, then each open objection escalates to `needs_confirmation`. Budget guard: 5-minute wall clock and cloud RPM; degrade to local-only roles with a visible badge. Every step emits an SSE event {role, round, action, model, tokens, latency}. Must NOT hardcode per-site paths or outcomes (judges discount hardcoded demo paths); must NOT skip the critic in live runs.
  Parallelization: Wave 3b | Blocked by: 2,6,8,10,11,16 | Blocks: 12,13,14
  References: HackOS "Hackathon Overview" §4 (weak vs strong agent systems) and §14 (what judges prioritise); "Agent architecture" in this plan
  Acceptance criteria: unit tests with fake generators: (a) verifier rejection triggers an investigator retry, (b) critic objection triggers a targeted second round and changes the verdict, (c) objection unresolved after round 2 lands in needs_confirmation, (d) budget exhaustion returns a partial report with a degraded flag; live run on the 3 showcase sites shows the critic step in every trace
  QA scenarios: happy: `curl` POST /screen for Pima County AZ and inspect the SSE stream for planner → investigators → verifier → adjudicator → critic → round 2; failure: cloud key missing → local-only run completes with degraded badge. Evidence .litclaude/evidence/dc-site-screener/task-17.txt
  Commit: Y | feat(agents): orchestrator and critic loop

## Final verification wave
> Runs in parallel after ALL todos. ALL must APPROVE. Surface the results and wait for the user's explicit okay before declaring the work complete.
- [ ] F1. Plan compliance audit
- [ ] F2. Code quality review
- [ ] F3. Real Manual-QA
- [ ] F4. Scope fidelity

## Commit strategy
- Git repo initialized only after user approval; one conventional commit per todo after its tests pass
- No "Co-Authored-By", no "Generated with Claude Code", no AI attribution (user global rule)
- Public GitHub push only with explicit user approval, before submission

## Success criteria
- Address + MW → report in ≤5 minutes
- 3 showcase sites match hand-checked decisive layer and applicability values
- 100% claims cited with URL + as-of; ≥95% quotes verified verbatim; no unverified fatal grades
- Zetaris serves the portfolio join; Meterless World Model is the shared agent state and Markovian drives the county loop; all model calls go through Nightshift
- Agent loop: every run trace shows ≥2 distinct role interactions and the critic step; seeded-fault eval catches ≥2 of 3
- Nemotron serves every reasoning step; routing visible in UI
- Submission completed by 2026-10-27 night KST (deadline 10/28 08:45 KST)
