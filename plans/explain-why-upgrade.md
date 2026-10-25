# explain-why-upgrade — Work Plan

## TL;DR (For humans)

**What you'll get:** SiteWhy becomes one integrated HQ console that a site-selection team can use without instructions.

Using it:
- Pick a site by typing an address, clicking a spot on the satellite map, or choosing one from the portfolio.
- Each site gets a link you can share.
- Screened sites stay in the portfolio after a restart.

What the screen shows:
- the site on the map, with county lines, city limits and nearby transmission lines
- five warning lamps, one per rule layer
- an answer that reads in 30 seconds:
  - one plain verdict
  - a short chain from source sentence to rule to math to result
  - what would flip the answer
  - what the agents caught in each other's work

Behind the screen, the screening gets more honest:
- a missing state rule layer is added, including the August 2026 Texas grid-connection audit
- fake "source conflicts" are removed, and the real 12-vs-6-month conflict now surfaces
- the three showcase sites are scored against hand-checked answers

**Why this approach:** Track 2 judges explanation. The map makes the key "why" visible: the Tucson site sits inside city limits, so the county moratorium does not reach it. One integrated flow (pick a site, read the answer, check why) is what makes the product feel real to judges. Every explanation is computed by code from the run's own data, so there is no extra model cost and no invented reasoning. Map data comes from free public services and is cached so demos survive slow networks.

**What it will NOT do:**
- No Google Maps engine (it needs a billing-enabled key); an "open in Google Maps" link is provided instead.
- No address autocomplete, no new states, no speed-up of the ~4-minute live run.
- No README, deck or video (that is the next plan).

**Effort:** XL (about 19 hours; tight against the 10/27 22:00 KST submit target, see cut order)
**Risk:** Medium.
- Re-recorded runs depend on Nightshift.
- Public map services can be slow, so they are cached and degrade gracefully.
- Esri imagery expects attribution, and an ArcGIS account for commercial use.

**Decisions to sanity-check:**
- (1) The map sits at the center, with the report in a tabbed side panel.
- (2) The Texas audit enters as a "major" state rule and may change the Texas answer.
- (3) The four showcase runs are re-recorded live.
- (4) If time runs short, cut in this order: transmission lines → print/download → map pins for the portfolio → click-on-map screening → live run outside modelled states → second critic prompt round.

Your next move: approve, then run `/litclaude:start-work`. Full execution detail follows below.

---

> TL;DR (machine): XL, Medium risk; deliverables: honest conflicts, state layer via Zetaris, deterministic explanation layer, cached site-context geo endpoint, HQ console (map + lamps + portfolio), report panel, integrated flow (map-click screening, persistent portfolio, deep links, guide/glossary, print/download), coverage handling, re-recorded samples, eval (Todo 13), SAMPLE_MODE clean clone (Todo 14).

## Context and objective

Bounded objective: a first-time user opens SiteWhy and, without reading docs, picks a site in one of three ways: a showcase in the portfolio, a typed address, or a click on the satellite map. They then see:
- the site on the map with county and city boundaries
- per-layer status lamps
- the answer with its decisive why-chain (verified quote → rule → computation → result)
- what would flip the answer, and which mistakes the agents caught

Every view is reachable by a shareable link and survives a server restart. All of it is backed by deterministic code and passing tests, and it runs from a clean clone in `SAMPLE_MODE=true` with no keys. Map tiles need network access; everything else is cached.

This closes M3 of `plans/roadmap.md` (Todos 12, 13 and 14 of `plans/dc-site-screener.md`). It replaces the roadmap's "No map" cut by user request on 2026-10-26: "show where the site is on a map; an HQ platform with a SCADA-like overview; an integrated app the user can use intuitively."

Judging weights: Impact 30, Technical 20, Innovation 15, Demo 15, Product & UX 10, Sponsor tech 10 (`.litclaude/deep-interview/open-agent-hackathon-2026-context.md`).

Gaps found in the 2026-10-25 review of the running app:

| # | Gap | Evidence | Judging axis |
|---|---|---|---|
| G1 | No framing: page never states the user's question or who it is for | `web/index.html` header only | Impact, UX |
| G2 | "Why" is one LLM paragraph; no visible fact → rule → math → result chain | report `why` only | Track 2 core |
| G3 | Raw dumps: `key=value` params, 7+ quotes per rule, model-invented field tags | Washington sample screenshot | UX |
| G4 | False conflicts, and the real 12-vs-6-month conflict is missed | Washington sample: `paused_activities: "None" vs …`, case-only diffs; the 6-month quote is tagged `duration_draft_ordinance`, so it is never compared with `duration_days` | Technical, trust |
| G5 | Agent self-correction is invisible except as debug rows | `events` rendered verbatim | Innovation, Demo |
| G6 | No counterfactual ("what would change the answer") | none | Track 2 core |
| G7 | State layer missing; Zetaris holds one table | `app/seed.py` registers only `moratoria`; `state_legislation.csv` (440 rows) unused; TX `tx-abbott-2026-08-03-data-center-audit-directive` is `in_force` | Correctness, Sponsor tech |
| G8 | No eval numbers | roadmap Todo 13 open | Technical |
| G9 | Clean clone without keys unverified | roadmap Todo 14 open | Demo safety |
| G10 | Out-of-coverage address behavior untested | EIA subset TX/MD/AZ only (`app/geo.py`) | Demo safety |
| G11 | No map; the Tucson "inside city limits" reason is invisible | user request 2026-10-26 | UX, Demo, Impact |
| G12 | Not an integrated app: live runs vanish on restart (in-memory `runs` dict in `app/main.py`); samples and live runs live in separate controls; no shareable links; no onboarding; jargon (grades, ISO/RTO, Title V) unexplained | `app/main.py:40`, `web/index.html` | UX, Demo |

External sources checked 2026-10-26; each responded with no key:
- Esri World Imagery tiles `https://server.arcgisonline.com/ArcGIS/rest/services/World_Imagery/MapServer/tile/{z}/{y}/{x}`
- OSM tiles `https://tile.openstreetmap.org/{z}/{x}/{y}.png`
- CARTO dark `https://{s}.basemaps.cartocdn.com/dark_all/{z}/{x}/{y}.png`
- TIGERweb `https://tigerweb.geo.census.gov/arcgis/rest/services/TIGERweb/tigerWMS_Current/MapServer`
  - layer 82 Counties (`GEOID='24043'` returned Washington County, 231 KB unsimplified)
  - layer 28 Incorporated Places (the point -110.9747, 32.2226 returned "Tucson city")
- HIFLD `https://services1.arcgis.com/Hp6G80Pky0om7QvQ/arcgis/rest/services/Electric_Power_Transmission_Lines/FeatureServer/0`
- Census coordinate geocoder `https://geocoding.geo.census.gov/geocoder/geographies/coordinates?x=<lon>&y=<lat>&benchmark=Public_AR_Current&vintage=Current_Current&format=json`. It returns the same `geographies` structure as the `onelineaddress` call used in `app/geo.py:18,122-129` (Counties, Incorporated Places, States), so `Resolver` parsing can be reused.
- The Google Maps JS API needs a billing-enabled key, so it is excluded. A deep link `https://www.google.com/maps/search/?api=1&query=<lat>,<lon>` is used instead.

## Scope

### Must have
- Canonical decision fields and value normalization (G4).
- State layer:
  - TX audit directive as a curated rule with a live-verified quote
  - Zetaris-backed state watch list (G7)
- `app/explain.py`: decisive chain, headline, flips, sensitivity, catches, layer status and stats. Pure code, applied to live runs and served samples (G2, G5, G6).
- `app/sitecontext.py` + cached context endpoints (G11).
- HQ console:
  - left rail with form and portfolio
  - center satellite map with overlays, status lamps and telemetry
  - right report panel with tabs (G1, G3, G11)
- Integrated flow (G12):
  - one portfolio of showcase and live runs, persisted on disk
  - click-on-map screening via coordinates
  - deep links with working back/forward
  - first-visit guide and glossary tooltips
  - print-friendly report and JSON download
- Coverage handling, re-recorded samples, eval, SAMPLE_MODE clean clone (G8–G10).
- Attribution for Esri, OSM, CARTO, Census TIGERweb and HIFLD in the map and in `data/ATTRIBUTION.md`.

### Must NOT have (guardrails, anti-slop, scope boundaries)
- No Google Maps JS API, Mapbox, address autocomplete or any key-requiring service; no new keys.
- No new LLM calls for explanation, map annotation or onboarding. `explain.py` never changes `verdict`; flips carry an `estimated_verdict` labelled as an estimate.
- Dataset-only state actions are never decisive.
- No parcel/GIS analysis, distance-based rule logic or zoning layers. Transmission lines are visual context only.
- No React or bundler. Vanilla HTML/JS/CSS with system fonts; Leaflet 1.9.4 (vendored) is the only library.
- No user accounts, auth, multi-user sync or editing of portfolio entries beyond what this plan lists.
- No README, deck, video, metadata.json or GitHub push (next plan). No new states. No Tier 4 factors.
- No scraping of Municode, eCode360 or American Legal. Honor robots.txt (`gov.texas.gov` allows `/news/` for `*`).
- Do not print or commit keys. Do not hand-edit recorded samples.
- The browser never calls TIGERweb, HIFLD or the Census geocoder directly; everything goes through backend endpoints.

## Bootstrap (executor reads first)
- PIN, reread before starting:
  - `AGENTS.md`, `plans/roadmap.md`, this plan
  - `app/orchestrator.py` (`parse_fact`, `_record_fact`, `_params`, `_findings`, `_guard`, `run`)
  - `app/agents.py` (about line 102: field vocabulary)
  - `app/applicability.py`, `app/layers.py`, `data/layers/rules.yaml`, `app/seed.py`, `app/screen.py:58-82`
  - `app/geo.py` (`Resolver.resolve`, `Jurisdiction` with `lat`, `lon`, `county_fips`, `place`)
  - `app/main.py` (in-memory `runs` dict at line 40, `RunRequest`), `web/index.html`, `tests/test_orchestrator.py` (ScriptedRouter), `tests/test_geo.py` (Census fixtures)
- Runtime facts:
  - Python 3.13 with uv: run tests with `uv run pytest -q`; `live` tests are deselected by default; lint with `uv run ruff check .`.
  - Nightshift at `http://127.0.0.1:8088/v1`; Zetaris local Docker in `~/zetaris-platform`.
  - A uvicorn server may be running on :8000. Restart it after backend changes.
- Dirty worktree:
  - `data/geo/cache/*` and `data/llm_cache/*` are untracked caches; ignore them in Todo 1.
  - `data/geo/context/` is committed only for the 4 showcase sites.
  - `runs/` stays ignored.
- Commit approval: todo-level commits were approved on 2026-10-25. Push, repo creation and HackOS submission need separate explicit approval. No AI attribution or Co-Authored-By; end each message with the session line from the active system reminder, if one is present.
- Resume ledger: `.litclaude/evidence/explain-why-upgrade/task-<N>.*` plus checkboxes here.
- Time budget and cut order:
  - Start about 01:00 KST 10/26. Target M3 done by 10/27 12:00 KST.
  - If behind at 10/27 06:00 KST, cut in this order:
    1. transmission layer (Todo 4c)
    2. print/download (Todo 7e)
    3. portfolio pins on the map (Todo 5)
    4. map-click screening (Todo 7b)
    5. optional live VA run (Todo 8)
    6. second critic prompt round (Todo 10)
  - Each cut is recorded in the evidence file and named to the user.
- Cleanup:
  - Stop any uvicorn a todo starts (record the PID).
  - Close QA browser tabs.
  - Remove `/private/tmp/sitewhy-clean`.

## Verification strategy
> Zero human intervention: every verification step is agent-executed.
- Test decision: TDD with pytest. Backend todos write the failing test first. External HTTP is mocked with `httpx.MockTransport`; `live`-marked tests hit the real services.
- Manual-QA channels:
  - HTTP (curl on uvicorn)
  - browser (claude-in-chrome on http://localhost:8000)
  - frontend-ui-ux interface probe (320/390/768/1440, dark mode, reduced motion, 200% zoom)
- Evidence: `.litclaude/evidence/explain-why-upgrade/task-<N>.<ext>`.

## Execution strategy
### Parallel execution waves
Single executor, sequential. Todos 1–3 share `app/orchestrator.py`; Todos 5–7 share `web/`. Todo 4 is independent and may run after Todo 1 for a context switch.
- Wave 1 (backend truth): 1 → 2 → 3
- Wave 2 (map data + surface): 4 → 5 → 6 → 7
- Wave 3 (data + proof): 8 → 9 → 10
- Wave 4: 11 → 12, then F1–F4

### Dependency matrix
| Todo | Depends on | Blocks | Can parallelize with |
| --- | --- | --- | --- |
| 1 Honest conflicts | — | 3, 9 | 4 |
| 2 State layer via Zetaris | — | 3, 9 | 4 |
| 3 Explanation layer | 1, 2 | 5, 6, 8, 9 | 4 |
| 4 Site context geo endpoint | — | 5 | 1, 2, 3 |
| 5 Console shell: map, lamps, portfolio | 3, 4 | 6 | — |
| 6 Report panel and live feed | 5 | 7 | — |
| 7 Integrated flow | 6 | 9, 11 | — |
| 8 Out-of-coverage handling | 2, 3 | 9 | 5–7 |
| 9 Re-record showcase runs | 1–8 | 10, 11 | — |
| 10 Eval | 9 | 12 | 11 |
| 11 SAMPLE_MODE clean clone | 7, 9 | 12 | 10 |
| 12 Bookkeeping | 10, 11 | F1–F4 | — |

## Todos
> Implementation + Test = ONE todo. Never separate them.
> Rows start at column zero as `- [ ] N. <title>`; start-work cannot see an indented row.
<!-- APPEND TASK BATCHES BELOW THIS LINE — never rewrite the headers above. -->
- [x] 1. Honest conflicts: canonical decision fields and normalized values
  What to do:
  - In `app/orchestrator.py` add `DECISION_FIELDS = ("effective", "duration_days", "scope", "exempt_if_permits_submitted")` and `canonical_field(name)`. Rules, applied after lowercasing and replacing spaces/hyphens with `_`:
    - starts with `effective`/`adopt`/`enact` → `effective`
    - contains `duration` → `duration_days`
    - starts with `scope` → `scope`
    - contains `exempt` and `permit` → `exempt_if_permits_submitted`
    - otherwise unchanged
  - `parse_fact` returns `None` for null-like values (`""`, `none`, `null`, `n/a`, `unknown`, `not stated`, case-insensitive) in every field.
  - `_record_fact`:
    - canonicalize the field before storing and comparing
    - detect conflicts only for `DECISION_FIELDS`
    - add `quote`, `url`, `other_quote` and `other_url` to the conflict event detail, keeping the existing keys
  - Investigator prompt: "field must be exactly one of effective, duration_days, scope, exempt_if_permits_submitted, other".
  - `.gitignore`: add `data/llm_cache/` and `data/geo/cache/` if missing.

  Must NOT do: change `_params` precedence beyond canonical fields; drop non-decision facts.
  Parallelization: Wave 1 | Blocked by: — | Blocks: 3, 9
  References: `app/orchestrator.py:66-82,207-244`; `app/agents.py:100-110`; Washington sample events; press release "twelve (12) month" vs draft ordinance "six (6) months"
  Acceptance criteria:
  - New tests in `tests/test_orchestrator.py`:
    - (a) `duration_draft_ordinance` "six (6) months" + `duration` "twelve (12) months" from two verified sources gives exactly one `duration_days` conflict (183 vs 365), with both quotes and urls
    - (b) a "None" value gives zero conflicts
    - (c) case-only `other` differences give zero conflicts
  - `uv run pytest -q` and `uv run ruff check .` are green.
  QA scenarios: show RED, then GREEN. Evidence `task-1.txt`
  Commit: Y | fix(agents): compare only canonical decision fields so source conflicts are real

- [x] 2. State layer: TX audit directive rule plus a Zetaris state watch list
  What to do:
  - (a) Append to `data/layers/rules.yaml`:

    ```yaml
    id: tx-ercot-data-center-audit-2026
    layer: state
    title: "Texas Governor's data center interconnection audit (ERCOT)"
    scope: {iso: ERCOT}
    check: {mw_threshold: 75, inclusive: false, label: "ERCOT large load"}
    quote: "The PUCT and ERCOT must complete this audit before any data center project moves forward."
    source_url: "https://gov.texas.gov/news/post/governor-abbott-directs-comprehensive-data-center-audit"
    source_title: "Office of the Texas Governor press release, 2026-08-03"
    as_of: "2026-08-03"
    status: in_force
    ```

    Branch:
    - If the quote is not verified, pick another verbatim sentence from that page stating the precondition.
    - If the page cannot be fetched, keep the rule as `unverifiable`; the guard cannot make it fatal.
  - (b) Watch list:
    - `app/seed.py` registers `STATE_LEGISLATION_CSV` as `state_legislation`.
    - `app/screen.py` gains `state_actions(j)`, selecting `policy_action_id, bill, status, key_provisions, policy_mechanism, scope_of_action, legal_effect_status, bill_status_category, last_action_date_iso, primary_source_url` from `SITEWHY.state_legislation`, where state matches AND (enacted OR in_force), ordered by date desc.
    - `Orchestrator.run` stores the rows in `report["state_watch"]`, each with `provenance: "dataset"`, the source string, and `covered_by_rule` when `primary_source_url` equals a curated rule's `source_url`. Do not pass them to the adjudicator, critic or guard. Emit a `system/state_watch` event.
  - Credit the CSV in `data/ATTRIBUTION.md`.

  Must NOT do: grade watch rows; invent sources.
  Parallelization: Wave 1 | Blocked by: — | Blocks: 3, 9
  References: `state_legislation.csv` (TX directive in force; AZ `az-hb-4168-2026` incentive-only; MD `md-hb1532-sb0841-2026` RELIEF Act); `app/seed.py`; `app/screen.py:58-82`; `app/layers.py`; `tests/test_layers.py`; `tests/test_data.py`
  Acceptance criteria:
  - The rule applies yes at ERCOT 300 MW, no at 70 MW, and is out of scope for PJM.
  - DuckDB `state_actions`: TX includes the directive, AZ includes `az-hb-4168-2026`, and there are no `failed_died` rows.
  - Orchestrator: `state_watch` is present and never in `findings`.
  - Live: the quote verifies.
  - Zetaris: `SELECT COUNT(*) FROM SITEWHY.state_legislation` returns 440.
  QA scenarios: failure — a Zetaris harness with a wrong URL falls back to DuckDB and traces `BLOCKED`. Evidence `task-2.txt`
  Commit: Y | feat(layers): Texas ERCOT audit directive rule and state watch list from Zetaris

- [x] 3. Explanation layer (`app/explain.py`), attached to runs and served samples
  What to do: create `enrich(report)`, pure and idempotent: deep-copy, no model calls, never change `verdict`. It adds `explanation` with the parts below.
  - `site` inputs: `as_of` from the `system/resolved` event or `report["site"]`; `incorporated` from `jurisdiction.place`; `mw` and `permits_submitted` from `project`. `Orchestrator.run` also stores `report["site"]` with lat/lon.
  - `decisive`: fatal or major with applies yes, fatal first, then layer order. Each entry has:
    - `rule_id`, `title`, `layer`, `grade`
    - `fact`: preference order is primary verified with a decision field → primary verified → curated verified → dataset
    - `more_sources`
    - `computation`: a human string, for example "in effect 2026-06-30 → 2027-06-30; as of 2026-10-25" or "estimated NOx 1,067 tpy ≥ 100 tpy", plus assumptions
    - `result`
  - `headline`: verdict plus `decisive[0]`. Fallbacks: the first open question, or "Go: no fatal or major rule applies to this site."
  - `flips` (`{rule_id, change, effect, estimated_verdict}`), only when `applies` changes:
    - Moratorium: re-run with
      - (i) `incorporated` toggled, when the scope is unincorporated
      - (ii) `permits_submitted=True`, when the exemption is true
      - (iii) `as_of` = expires
    - `mw_threshold` rules: the threshold-side MW.
    - Title V: the largest integer MW with applies no, by linear scan.
    - `estimated_verdict`: the worst remaining decisive grade (fatal → no-go, major → conditional, else go).
  - `sensitivity`: per conflict on moratorium decision fields, `{rule_id, field, readings:[{value, quote, url, applies}], holds}`. Skip non-decision fields and null-like values.
  - `catches`: `{round, actor, kind, text, outcome}` from:
    - verifier retries, with the outcome from the next `verified` event
    - real conflicts
    - critic objections ("re-investigated in round 2" or "left open for your team")
    - escalations
    - guard notes
    - model `escalated_from` rows
  - `layer_status` for federal, iso_rto, state, county and city:
    - lamp `fatal | major | minor | clear | unknown | not_modelled`
    - a one-line summary
  - `stats`:
    - model calls by `routed_model`, and receipts
    - data queries by backend
    - quotes verified/checked
    - Markovian chunks and tokens saved
    - run duration
  - Wiring:
    - `Orchestrator.run` returns and writes `enrich(report)`.
    - `GET /samples/{name}` returns `enrich(...)`.
    - `GET /samples` adds `lat`, `lon`, `headline` and `county`.

  Must NOT do: model calls; verdict changes; mutation; non-changing flips.
  Parallelization: Wave 1 | Blocked by: 1, 2 | Blocks: 5, 6, 8, 9
  References: `app/applicability.py`, `app/layers.py`, `app/orchestrator.py`, the 4 samples
  Acceptance criteria: `tests/test_explain.py` covers the following.
  - Washington:
    - headline starts with "No-go"
    - `decisive[0]` is the moratorium with a verified primary fact
    - the expiry flip estimates conditional
    - "None" pairs are excluded
    - County lamp is `fatal`
  - Tucson: the unincorporated flip changes the Pima `applies`; County lamp is `clear`.
  - Abilene: the SB 6 flip mentions 75 MW; the Title V flip `x` → no and `x+1` → yes.
  - Synthetic duration conflict: `holds` is true at 2026-10-25 and false at 2027-01-15.
  - Idempotent; the input is unmutated.
  - API: `/samples/<name>` has `explanation`; `/samples` rows have lat/lon.
  QA scenarios: curl a sample after restart; failure — zero findings gives empty lists and a fallback headline. Evidence `task-3.txt`
  Commit: Y | feat(explain): decisive chain, flips, conflict sensitivity, agent catches and layer status from run data

- [x] 4. Site context geo endpoint (TIGERweb boundaries, HIFLD transmission), cached
  What to do: create `app/sitecontext.py` with `SiteContext(client, cache_dir=ROOT/"data/geo/context")` and `context(lat, lon, county_fips)`. It returns:
  - (a) `county`: TIGERweb layer 82, `where=GEOID='<fips>'`, `outSR=4326`, `maxAllowableOffset=0.002`, `geometryPrecision=5`, `f=geojson`
  - (b) `place`: layer 28 point intersect, or `null`
  - (c) `transmission`: HIFLD envelope ±0.12°, `outFields=VOLTAGE,OWNER,STATUS`, `maxAllowableOffset=0.0005`, at most 300 features; `null` plus an `errors` entry on failure or after a 10 s timeout
  - (d) `sources` with attribution strings
  - (e) `google_maps_url`

  Caching and validation:
  - Cache each part keyed by a sha of the query, with lat/lon rounded to 4 decimals; the cache is read first and never expires. Parts fail independently.
  - Validate: lat in 18..72, lon in -180..-60 (US incl. AK/HI), FIPS exactly 5 digits; otherwise 422. Only these fixed hosts are called, so no user-controlled URL is possible.

  Endpoints:
  - `GET /context?lat=&lon=&county_fips=`
  - `GET /samples/{name}/context`
  - `GET /runs/{id}/context`

  All work in SAMPLE_MODE from the cache. Commit the cache for the 4 showcase samples, keeping the total under 2 MB.
  Must NOT do: browser calls to these services; distance in rule logic.
  Parallelization: Wave 2 | Blocked by: — | Blocks: 5
  References: `app/geo.py` (Census client and cache pattern); `tests/test_geo.py`
  Acceptance criteria:
  - `tests/test_sitecontext.py` (MockTransport):
    - assembled response
    - second call served from cache with zero transport calls
    - transmission 500 gives `null` plus an error while county is still present
    - no place gives `null`
    - out-of-range lat or bad FIPS gives 422
  - Live test: Tucson `place.properties.NAME == "Tucson city"`.
  QA scenarios: curl Tucson context (Pima + Tucson city) and Washington context (place null); record sizes. Evidence `task-4.txt`
  Commit: Y | feat(map): cached site context with county, city limits and transmission lines from public services

- [x] 5. Console shell: satellite map, status lamps, telemetry and portfolio (frontend-ui-ux build lane, redesign)
  What to do:
  - Restructure `web/` into `index.html`, `app.css` and `app.js` (vanilla).
  - Vendor Leaflet 1.9.4 into `web/vendor/leaflet/` (`leaflet.js`, `leaflet.css`, `images/`, `LICENSE` from `https://unpkg.com/leaflet@1.9.4/dist/`) and record the sha256.
  - Theme: dark console by default (ink #18272b ground, paper text, accent #c64d2e, mist #b7d8c7); light via `prefers-color-scheme` plus a toggle. System fonts only.

  Layout at ≥1180px, full viewport with no page scroll and each zone scrolling internally:
  - Left rail (about 280px):
    - "SiteWhy HQ" mark and the tagline "Can a data center be built here — and if not, why?"
    - form (address, IT load MW, permits submitted, Screen)
    - portfolio list from `/samples`: verdict lamp, short address, MW, county; selected row highlighted
    - coverage note
  - Center:
    - Map (about 60% of the height):
      - basemaps Esri World Imagery (default), Streets (OSM) and Dark (CARTO)
      - overlays from the context endpoint:
        - county outline (mist)
        - city limits (accent, dashed, labelled)
        - transmission lines (thin amber, voltage tooltip)
        - site pin with a verdict ring
        - portfolio dots that load their site on click
      - annotation chip from findings and `layer_status`, for example "Inside Tucson city limits — Pima County moratorium covers unincorporated areas only"
      - "Open in Google Maps" link and the attribution control
    - Status board under the map:
      - five lamps (Federal, Grid/ISO, State, County, City) from `layer_status`, with label, state word, and summary on hover/focus. Colors: fatal = red accent, major = amber, minor/clear = green, unknown = grey, not modelled = hollow.
      - telemetry tiles from `stats` (Nemotron calls with the Lightning/Ultra split, Nightshift receipts, Zetaris queries, quotes verified, run time)
  - Right zone (about 440px): a placeholder container for Todo 6.
  - Below 1180px, stack: form + portfolio (collapsible), map (50vh), lamps, report.
  - If tiles or Leaflet fail, the map zone shows the coordinates and the Google Maps link; the rest still works.

  Must NOT do: network fonts; other libraries; direct external service calls from the browser.
  Parallelization: Wave 2 | Blocked by: 3, 4 | Blocks: 6
  References:
  - current `web/index.html` (reuse `api()` and sample loading)
  - frontend-ui-ux skill dir `~/.litclaude/marketplaces/litclaude-ai/plugins/litclaude/skills/frontend-ui-ux/` (validator, `scripts/interface-probe.mjs`)
  - keep the earlier probe fixes (44px targets, 16px inputs, `.field{min-width:0}`)
  Acceptance criteria:
  - On each of the 4 samples, the map shows the pin and county outline and the lamps match `layer_status`.
  - Tucson shows city limits containing the pin, plus the annotation chip.
  - Washington's County lamp is red.
  - Tile-failure fallback works (override the tile URL to an invalid host in a JS check).
  - The interface probe has 0 HIGH findings.
  QA scenarios: claude-in-chrome — click each portfolio row and map dot; screenshots at 1440×900 and 390×844. Evidence `task-5/`
  Commit: Y | feat(ui): HQ console shell with satellite map, layer status lamps, telemetry and portfolio

- [x] 6. Report panel and live run feed
  What to do: fill the right zone with tabs (keyboard arrows, `role=tablist`, `aria-selected`).
  1. "Answer & why":
     - verdict banner with `headline`; project line (MW, address, county, ISO, as-of)
     - decisive cards: Source says (quote + link + verified/dataset chip) → Rule → Check → Result
     - adjudicator summary in smaller text, labelled with the synthesize-step model
     - open questions from `needs_confirmation`
  2. "What would change it": flips table (change / effect / estimated verdict chip labelled "estimate").
  3. "What the agents caught":
     - catches with actor badges
     - sensitivity rows ("Sources disagree on duration: 12 months (press release) vs 6 months (draft ordinance) — verdict holds under both")
  4. "All rules":
     - compact per-layer rows; evidence in `<details>` (3 shown plus "show N more")
     - plain field labels; `other` tags hidden
     - state watch list "(dataset, not verified)", hiding `covered_by_rule`
  5. "Under the hood": model trace, data trace with SQL, humanized timeline, Markovian runs, World Model stats, disclaimer.

  Live run:
  - POST `/runs`; the portfolio gets a "running" row with a pulsing lamp.
  - The map flies to the location when the `system/resolved` event arrives (lat/lon in the detail).
  - The right zone shows the humanized feed with elapsed time and "about 3–4 minutes".
  - Done → report. Error → inline message, with the form still usable.

  SAMPLE_MODE: disable Screen with the note "Live runs are off in sample mode — pick a site from the portfolio".
  Must NOT do: raw `key=value`; the LLM paragraph above the decisive cards.
  Parallelization: Wave 2 | Blocked by: 5 | Blocks: 7
  References: `app/main.py` (`/runs`, `/runs/{id}`, `/status`); Todo 3 explanation shape
  Acceptance criteria:
  - On all 4 samples, the visible text has no `undefined`, `[object Object]`, ` null` or `=digit` (JS check).
  - Washington: the quote link opens; the catches list a verifier rejection and the duration disagreement.
  - Tabs are keyboard operable.
  - SAMPLE_MODE disables Screen.
  - The interface probe has 0 HIGH findings.
  QA scenarios:
  - (a) Load each sample, visit every tab, screenshots.
  - (b) Live run "555 Walnut St, Abilene TX 79601" at 300 MW: the map flies on resolve, the feed updates, then the report renders.
  - (c) Failure: "zzzz nowhere" gives an inline error.
  - (d) Judge test at 1440×900: map, lamps, headline and the first decisive card are visible without scrolling.
  - Evidence `task-6/`
  Commit: Y | feat(ui): decision-first report panel with flips, agent catches and live run feed

- [x] 7. Integrated flow: one portfolio, map-click screening, deep links, guide and export
  What to do:
  - (a) Persistent portfolio. `GET /portfolio` merges:
    - showcase samples (`kind: "showcase"`)
    - completed live runs read from `runs/*/report.json` (`kind: "live"`, newest first), each enriched

    Each row has `id`, `kind`, `address`, `mw`, `verdict`, `headline`, `lat`, `lon`, `county` and `created`. `GET /runs/{id}` falls back to `runs/<id>/report.json` when the id is not in memory, so a restart keeps runs viewable. Validate `id` against `^[0-9TZ]+-[0-9a-f]{6}$`. The UI portfolio uses `/portfolio`, grouped as Showcase / Your screenings.
  - (b) Map-click screening:
    - `Resolver.resolve_point(lat, lon)` calls the Census coordinates endpoint (same `geographies` parsing as `resolve`, factored into one helper) and sets `matched_address` to "<lat>, <lon> (<County>, <ST>)".
    - `RunRequest` accepts either `address` or `lat`+`lon`, validated (exactly one form; ranges as in Todo 4).
    - In the UI, clicking the map opens a popup "Screen this location" with an MW field (default 300) and a button that starts the live run. In SAMPLE_MODE the popup says live runs are off.
  - (c) Deep links:
    - `#/site/<sample-name>` and `#/run/<run-id>`; selecting anything updates the hash
    - the hash is restored on load; back/forward work via `hashchange`
    - a "Copy link" button in the answer banner
  - (d) First-visit guide and glossary:
    - When nothing is selected, the right zone shows a 3-step guide: 1 Pick a site (portfolio, address, or click the map) → 2 Read the answer → 3 Check why (tabs). Include one-click "Try: Washington County, MD (No-go)".
    - A lamp legend under the status board.
    - Glossary tooltips, defined once in a JS object, on grade chips (fatal, major, minor, info), "Grid/ISO", "moratorium", "Title V", "SB 6" and "estimate".
    - Show a "?" button in the header that reopens the guide.
  - (e) Export:
    - "Download report (JSON)" saves the enriched report via a Blob.
    - A print stylesheet prints the answer, why, flips and catches as a clean brief: hide the map, rail and under-the-hood; add the site line and disclaimer.

  Must NOT do: auth; deleting or renaming portfolio entries; address autocomplete; storing anything in localStorage except the "guide dismissed" flag (wrapped in try/catch).
  Parallelization: Wave 2 | Blocked by: 6 | Blocks: 9, 11
  References:
  - `app/main.py` (`runs` dict line 40, `RunRequest`, `get_run`); `app/geo.py:18,122-129`
  - Census coordinates endpoint (Context section); `tests/test_geo.py` fixtures; `tests/test_api_runs.py`
  Acceptance criteria:
  - Tests:
    - `resolve_point` with a recorded Census coordinates fixture for Tucson gives Pima + Tucson city
    - `RunRequest` rejects both forms, neither form, and out-of-range values
    - `/portfolio` lists samples plus a fake `runs/<id>/report.json` (tmp dir)
    - `/runs/<id>` is served from disk after a new `create_app()`
    - a bad id gives 404
  - Browser:
    - (1) A fresh load with no hash shows the guide; clicking "Try" loads Washington.
    - (2) A deep link `#/site/az-tucson-pima` opened in a new tab restores Tucson; back returns to the previous site.
    - (3) Clicking the map near Abilene and screening at 300 MW produces a live run that appears under "Your screenings" and survives a server restart.
    - (4) Print preview (JS `window.matchMedia('print')` check plus a screenshot of the print-CSS state) hides the map and rail.
    - (5) The downloaded JSON parses and has `explanation`.
  - The interface probe has 0 HIGH findings.
  QA scenarios: (1)–(5) above with claude-in-chrome, plus a first-time-user walkthrough GIF via `gif_creator` (`sitewhy_first_use.gif`). Evidence `task-7/`
  Commit: Y | feat(app): persistent portfolio, click-to-screen on the map, shareable links, guide and export

- [x] 8. Out-of-coverage addresses: no crash, honest coverage
  What to do:
  - Write a FakeResolver test for Virginia (Loudoun, empty utilities) with ScriptedRouter.
  - The orchestrator completes, and the report has `coverage: {state_rules, county_sources}` from the `rules.yaml` scopes and `county_sources.yaml` keys.
  - Fix crashes (for example `iso_for([])`).
  - `enrich` defaults `coverage` for old samples; un-modelled layers get `not_modelled` lamps.
  - The map chip shows "State and grid rules are not modelled for <ST>; federal rule and county dataset only."

  Must NOT do: add VA data.
  Parallelization: Wave 3 | Blocked by: 2, 3 | Blocks: 9
  References: `app/geo.py:82`; `app/orchestrator.py` `run`; `data/layers/county_sources.yaml`
  Acceptance criteria: the new test passes; `coverage` is in every report.
  QA scenarios: curl `/resolve` for "1 Harrison St SE, Leesburg, VA 20175" (record 200 or 422); optional live run (cut item 5). Evidence `task-8.txt`
  Commit: Y | fix(orchestrator): report coverage and run cleanly outside modelled states

- [x] 9. Re-record the four showcase runs live
  What to do: add `scripts/record_samples.py` with the fixed inputs (300 MW, permits unknown):
  - `md-washington-county-unincorporated`: "13820 Pennsylvania Ave, Hagerstown MD 21742"
  - `tx-abilene-ercot`: "555 Walnut St, Abilene TX 79601"
  - `az-tucson-pima`: "255 W Alameda St, Tucson AZ 85701"
  - `md-hagerstown-city`: "100 W Washington St, Hagerstown MD 21740"

  The script:
  - runs a preflight: Nightshift `/v1/models` returns 200 and Zetaris `SELECT 1` succeeds, else stops with a named blocker
  - runs each site, or one named site
  - writes `samples/<name>.json` with a relative `worldmodel_log`, plus `samples/<name>/worldmodel.jsonl`
  - warms `data/geo/context`

  Diff verdict, decisive rules, conflicts and flips against the old samples in the evidence file. Expected:
  - TX gains the audit rule
  - Washington shows one real duration conflict with `holds: true`
  - Hagerstown city gains urls

  Branch:
  - A code-explained change is accepted.
  - Model variance gets one re-run; if the result still differs, keep it and tell the user.
  - If Nightshift or Zetaris is down, keep the old samples, mark BLOCKED, and continue.

  Must NOT do: hand-edit JSON; commit `runs/`.
  Parallelization: Wave 3 | Blocked by: 1–8 | Blocks: 10, 11
  References: `scripts/run_screen.py`, `app/factory.py`, `samples/`
  Acceptance criteria:
  - 4 regenerated samples, each with `site`, `coverage`, `state_watch`, `explanation`, evidence urls and lat/lon.
  - `uv run pytest -q` passes; sample tests assert structure only.
  QA scenarios: load each sample in the console; screenshots. Evidence `task-9.txt`
  Commit: Y | data(samples): re-record showcase runs with state layer, honest conflicts and site context

- [x] 10. Eval: showcase ground truth and critic seeded-fault catch rate (roadmap Todo 13)
  What to do:
  - (a) `data/eval/ground_truth.yaml`:
    - MD unincorporated: no-go; moratorium yes, fatal; Title V yes
    - TX Abilene: verdict in {conditional, needs_confirmation}, consistent with Todo 9 and justified by the audit rule; SB 6 yes; audit rule yes; Title V yes; no fatal
    - AZ Tucson: conditional; Pima moratorium no, with a city/unincorporated reason; Title V yes
  - (b) `scripts/eval.py` scores the samples, or `--live`, prints a table, and writes `data/eval/results.json`.
  - (c) `tests/test_eval.py::test_showcase_ground_truth` runs offline and asserts 3/3.
  - (d) `tests/test_critic_live.py` (`live`) gives the real Critic three seeded faults:
    1. Pima graded fatal though applies=no
    2. Title V reason altered to "below the 100 tpy major-source threshold" but graded major
    3. Washington with permits submitted and the exemption true, yet fatal (`missed_exemption`)

    A catch needs a matching `rule_id`; pass at ≥2/3, written to `results.json`.
  - Branch: below 2 caught, add one critic prompt sentence per missed type and re-run once (cut item 6). If it still fails, record the true rate and tell the user; never loosen the matcher.

  Must NOT do: tune ground truth to outputs without a cited reason.
  Parallelization: Wave 3 | Blocked by: 9 | Blocks: 12
  References: `app/agents.py` Critic objection types; `pyproject.toml` `live` marker
  Acceptance criteria: `uv run pytest -q tests/test_eval.py` passes; `uv run pytest -q -m live tests/test_critic_live.py` catches ≥2/3; `results.json` exists.
  QA scenarios: `uv run python -m scripts.eval` table; failure — an altered scratchpad copy reports a mismatch. Evidence `task-10.txt`
  Commit: Y | test(eval): showcase ground truth and critic seeded-fault catch rate

- [x] 11. SAMPLE_MODE clean clone (roadmap Todo 14)
  What to do:
  - `git clone` HEAD into `/private/tmp/sitewhy-clean`.
  - With `HOME` set to an empty temp dir and `HTTPS_PROXY=http://127.0.0.1:9` (so any external fetch fails), run `SAMPLE_MODE=true uv run uvicorn app.main:app --port 8010`. Run `uv sync` before setting the proxy.
  - Verify:
    - `/health` returns 200
    - `/status` shows sample_mode true and providers not configured
    - `/portfolio` lists 4 showcase rows with lat/lon
    - each `/samples/<name>` has `explanation`
    - each `/samples/<name>/context` is served from the cache
    - `POST /runs` returns 503
    - the UI loads a sample with overlays (tiles may fail behind the proxy; the fallback shows)
    - the guide is visible and Screen is disabled
  - Fix what breaks, with a regression test per fix. `.env.example` documents `SAMPLE_MODE`.

  Must NOT do: commit from the clone; leave :8010 running.
  Parallelization: Wave 4 | Blocked by: 7, 9 | Blocks: 12
  References: `app/config.py`, `app/main.py`, `.env.example`, `tests/test_api_runs.py`
  Acceptance criteria: all checks pass.
  QA scenarios: curl transcript plus a screenshot; cleanup receipt (PID killed, dirs removed). Evidence `task-11.txt`
  Commit: Y (only if fixes were needed) | fix(config): run from a clean clone in SAMPLE_MODE without keys

- [ ] 12. Bookkeeping: tick plans and record results
  What to do:
  - `plans/roadmap.md`:
    - tick M3 Todos 12, 13 and 14 with one-line results (eval 3/3, critic X/3, clean clone passes)
    - replace "No map" with "Map + HQ console + integrated flow (added 2026-10-26)"
    - list any cut items
  - `plans/dc-site-screener.md`: tick 12, 13 and 14, and add an "Explain-why upgrade and HQ console (2026-10-26)" Revisions line.
  - Restart :8000 with the final code.

  Must NOT do: start M4.
  Parallelization: Wave 4 | Blocked by: 10, 11 | Blocks: F1–F4
  References: `plans/roadmap.md`, `plans/dc-site-screener.md`
  Acceptance criteria: `grep -c "\[x\] Todo 1[234]" plans/roadmap.md` returns 3; `uv run pytest -q && uv run ruff check .` is green.
  QA scenarios: evidence `task-12.txt`
  Commit: Y | docs(plan): close M3 with eval, clean-clone and HQ console results

## Final verification wave
> Runs in parallel after ALL todos. ALL must APPROVE. Surface the results and wait for the user's explicit okay before declaring the work complete.
- [ ] F1. Plan compliance audit: acceptance criteria met with evidence files present (litclaude:lit-verifier).
- [x] F2. Code quality and security review of the diff since the plan start commit (litclaude:quality-reviewer):
  - `explain.py` purity
  - no added LLM calls
  - no keys
  - input validation on `/context`, `/runs` and `/portfolio` ids
  - sitecontext failure isolation
  - meaningful tests
- [ ] F3. Real Manual-QA:
  - first-time-user walkthrough (guide → Try → tabs → map click → live run → deep link → restart persistence)
  - 4 samples
  - interface probe 0 HIGH
  - judge test at 1440×900
- [ ] F4. Scope fidelity:
  - no M4 work; no new states; no key-requiring service
  - watch list never decisive; transmission never in rule logic
  - samples only from the script; cut items reported

## Commit strategy
One commit per todo, in todo order, on `master`, using the messages above. No AI attribution or Co-Authored-By; end each message with the session line from the active system reminder, if one is present. Never commit `runs/`, `data/llm_cache/`, `data/geo/cache/` or `.env*` (except `.env.example`). `data/geo/context/` is committed for the 4 showcase sites only. No push.

## Success criteria
- [ ] C001 | channel: browser | test: tests/test_explain.py::test_washington_decisive_chain | scenario: Washington shows the "No-go" headline, a red County lamp and a verified moratorium quote with a working link on the first screen
- [ ] C002 | channel: browser | test: tests/test_sitecontext.py::test_place_and_county_assembled | scenario: Tucson map shows the pin inside the Tucson city limits outline with the "unincorporated areas only" annotation
- [ ] C003 | channel: browser | test: tests/test_explain.py::test_flips | scenario: "What would change it" shows the Tucson unincorporated flip and the Abilene 75 MW SB 6 flip with estimated verdicts labelled as estimates
- [ ] C004 | channel: browser | test: tests/test_orchestrator.py::test_real_duration_conflict_only | scenario: Washington "What the agents caught" lists the 12 vs 6 month disagreement with "verdict holds under both" and no "None" conflicts
- [ ] C005 | channel: HTTP | test: tests/test_layers.py::test_tx_audit_rule_scope | scenario: TX report includes the ERCOT audit directive as a verified state-layer rule; state_watch SQL against Zetaris shows in the data trace
- [ ] C006 | channel: browser | test: tests/test_api_runs.py::test_portfolio_persists_runs | scenario: a first-time user follows the guide, screens a site by clicking the map, finds it under "Your screenings" after a server restart, and reopens it from a copied deep link
- [ ] C007 | channel: tmux | test: tests/test_eval.py::test_showcase_ground_truth | scenario: scripts/eval.py prints 3/3; live critic test catches ≥2 of 3 seeded faults
- [ ] C008 | channel: HTTP | test: tests/test_api_runs.py::test_sample_mode_disables_live_runs | scenario: clean clone with no keys and no external network serves all samples, explanations and cached overlays; Screen disabled with a visible note
- [ ] C009 | channel: browser | test: tests/test_orchestrator.py::test_out_of_coverage_site | scenario: a VA address completes or fails clearly, never crashes, and the coverage note appears
- [ ] C010 | channel: browser | test: interface-probe | scenario: 0 HIGH at 320/390/768/1440, dark mode, reduced motion and 200% zoom; tile failure falls back to coordinates and the Google Maps link
