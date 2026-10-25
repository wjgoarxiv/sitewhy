# SiteWhy roadmap (thin slice → widen)

Chosen 2026-10-25 (strategy 1 in `.litclaude/brainstorm/build-strategy.md`). Todo numbers refer to `plans/dc-site-screener.md`.
Deadline: **10/28 08:45 KST** (hard). Internal submit target: **10/27 22:00 KST**.

## Scope cuts (baseline from now on)
- States: **3** (TX, MD, AZ), matching the 3 showcase sites: ERCOT TX site, Washington County MD (PJM, 2026 moratorium), Pima County AZ (water stress). Todo 9 shrinks to these 3.
- County investigation: seeded counties only. The Markovian loop (todo 10) still runs, over seeded sources.
- Source discovery (todo 7): seeded links only. Live discovery is a stretch goal.
- UI (todo 12): simple HTML report (layers, why-chain, evidence, model trace). No map. Portfolio table is a stretch goal.
- Eval (todo 13): 3 showcase ground truths + seeded-fault critic test (catch ≥2 of 3).
- Kept in full: Nightshift as provider, Zetaris data layer, World Model + Markovian engines, multi-agent loop with critic.

## Milestones

### M0. Unblocked (now → 10/25 midday)
- [x] User: install Nightshift (free Mac M1+ edition), put the NVIDIA key in its Providers tab, confirm a Nemotron model is listed (verified 10/25: 8088 /v1/models 200, wrong token 401; chat OK on nvidia/nemotron-3.5-lightning-30b-a3b (~4 s) and nvidia/nemotron-3-ultra-550b-a55b (content includes <think>…</think>, strip it); nemotron-3-super-120b = 404 for this account, llama-3.3-nemotron-super-49b = 410 gone; 3.5-super-vl not listed. Token file: ~/Library/Application Support/ai.meterless.nightshift.m1m4/runtime-token)
- [x] User: Zetaris API key from the local UI (REST verified 10/25: SELECT 1 and SHOW LIGHTNING DATABASES → NY_TAXI, TPCDS_DB; endpoint POST /api/proxy/sql-editor/sqls/run-query with Bearer + X-Org-ID + X-Request-ID) (platform installed + verify.sh 9/9 PASS on 10/25) into `~/.hackathon-keys.env` (Meterless token: the app reads Nightshift's runtime-token file directly, no copy needed)
- [x] ~~User: open Ollama~~ skipped: Nightshift serves Lightning from the cloud
- [x] ~~User: post the Nightshift question in HackOS "Help Meterless"~~ not needed: free edition works as provider
- [ ] Agent: plan update (Nightshift router, Cursor optional, scope cuts above), `.gitignore`, first commit (with approval)
- Done when: preflight READY, `/v1/models` on Nightshift returns 200, a Zetaris SQL query returns rows

### M1. Walking skeleton (10/25)
- [x] Todo 1 skeleton (uv, FastAPI, pytest, ruff, config, `SAMPLE_MODE`)
- [x] Todo 2 model client through Nightshift (+ Ollama fallback, per-request model trace)
- [x] Todo 3 Zetaris adapter (+ DuckDB/sample fallback)
- [x] Todo 4 resolver (address → state, county)
- [x] Todo 5 minimal seed (moratoria only; federal/state layers move to M2): federal + 3 states + 3 counties
- Done when: `curl` on one Washington County MD address returns a JSON verdict with ≥1 rule, a quoted source, and the model name that answered

### M2. Agent core (10/26)
- [x] Todo 6 quote verifier
- [x] Todo 8 applicability engine
- [x] Todo 16 World Model engine (shared evidence graph) + conformance test
- [x] Todo 10 county investigator on the Markovian loop + test
- [x] Todo 11 adjudicator (why-chain)
- [x] Todo 17 orchestrator: verifier retries, critic loop (≤2 rounds), escalation
- Done when: all 3 showcase sites run end-to-end through the loop, and the trace shows a critic objection that triggered a re-investigation

### M3. Product surface (10/27 until ~16:00)
- [ ] Todo 12 HTML report UI
- [ ] Todo 14 replay / `SAMPLE_MODE`
- [ ] Todo 13 eval (3 ground truths + critic catch-rate)
- Done when: a clean clone runs in `SAMPLE_MODE=true` with no keys, and the UI shows the full report for all 3 sites

### M4. Submitted (10/27 by 22:00)
- [ ] Todo 15: README (HackOS template), `metadata.json`, `.env.example`, ≥3 sample I/O, deck, 1–4 min demo video, sponsor write-up
- [ ] Public GitHub repo (approval needed) and HackOS submission
- Buffer until 10/28 08:45 for fixes only. No new features after 22:00.

## Stretch (only if a milestone finishes early)
Live source discovery (todo 7), more states, portfolio table, map.
