# SiteWhy — HackOS submission sheet

Copy each answer into the HackOS submission form. Deadline: **27 October 2026, 23:45 UTC (28 October, 08:45 KST)**. Submit with hours to spare; the form can be updated until the deadline. The team roster locks when the first submission is created.

## 1. Project name and description

**Name:** SiteWhy

**One sentence:** SiteWhy tells a data center developer whether a US site is blocked by the rules that can stop it, and proves why with the verified rule text, the applicability math and what would change the answer.

**Short paragraph:** Site selectors and developers triage greenfield data center sites before spending on legal review and interconnection queues, while moratoria spread across 32 states. SiteWhy takes an address and an IT load in megawatts and runs a team of agents on NVIDIA Nemotron through Meterless Nightshift: a planner assigns investigations, a county investigator extracts candidate rules with verbatim quotes from county sources using the Meterless Markovian engine, an evidence verifier checks every quote against the source text and asks for retries, deterministic Python decides whether each rule (curated federal, state and grid rules plus the extracted county rules) applies, an adjudicator drafts the verdict and a critic sends unsupported links back for a second investigation round. The output is a go / conditional / no-go verdict with the decisive rule, the verified quote, the threshold math, the flips that would change the verdict, open questions, and a full per-request model trace. Reference data comes from Zetaris (moratorium and state legislation tables queried at run time). It is a screening tool, not legal advice.

## 2. Track

The Agent That Can Explain Why

## 3. Team members

| Field | Value |
| --- | --- |
| Full name | <your full name> |
| HackOS account email | <your HackOS email> |
| GitHub username | wjgoarxiv |
| Role | Solo builder: agent orchestration, Zetaris and Nightshift integration, UI |
| Primary contact | Yes |

## 4. GitHub repository URL

https://github.com/wjgoarxiv/sitewhy

## 5. Demo video (1–4 minutes)

https://github.com/wjgoarxiv/sitewhy/blob/master/submission/video/OAH2026-SiteWhy-ExplainWhy-Demo.mp4 (3:27, 1080p, with narration; the file is committed in the public repository and linked from the README). Test the link in a private browser window before submitting.

## 6. Slide deck

`submission/deck/sitewhy-deck.pdf` (also `.pptx`) — covers problem and users, solution, agent workflow, technical stack, Zetaris and Meterless use, what was unique, product visuals, future enhancements.

## 7. Sponsor technology explanation

**Zetaris (data layer):** SiteWhy's reference data lives in Zetaris. `scripts/zetaris_usl.py` registers four sources — the Moratorium Nation inventory (1,291 rows), state data center legislation (440 rows), the curated rule set and the verified county sources — runs exploratory queries on each, and builds a unified semantic layer that joins jurisdiction, moratoria, state bills and curated rules (`zetaris/usl.sql`, 1,291-row materialized table), with a data-quality rule (`null_join_keys`, 0 violations). At run time the orchestrator queries the Zetaris moratorium and legislation tables for evidence; every query is logged in the report's `data_trace`, and DuckDB serves the same SQL only when Zetaris is unreachable. The semantic layer is a separate, scripted artifact today; routing the agents' lookups through it is the next step. Reflection on time saved and a product requirement for Zetaris: `zetaris/REFLECTION.md`.

**Meterless:** Nightshift is the app's only AI provider — every model call goes to the local Nightshift endpoint with the `meterless-app` / `meterless-scope` headers, and each response's receipt id is stored per request. Two Meterless engines run inside the agent loop, each with conformance tests: the **World Model** engine is the shared, append-only, provenance-stamped evidence graph every agent writes to (claims, citations, contradictions, objections; replayable JSONL log per run), and the **Markovian** engine drives the county investigator's chunked reasoning over long ordinance documents with carry-over state.

**NVIDIA:** Nemotron does all the reasoning, routed through Nightshift: Nemotron 3.5 Lightning (30B) extracts candidate rules and quotes from county sources; Nemotron 3 Ultra (550B) plans, adjudicates and critiques. The UI's "Who did the work" lanes and every report's `model_trace` show which Nemotron model handled each request, with its Nightshift receipt, tokens and latency.

**Cursor:** The `Dockerfile` and `.dockerignore` were written in a Cursor Agent CLI session (commit 30d5b90; a judge can run `docker build -t sitewhy . && docker run -p 8000:8000 sitewhy` for sample mode). Verification and the rest of the build used Claude Code.

**What was unique:** models propose and deterministic code disposes. Nemotron agents find and argue about the rules, but whether a rule applies, the threshold math and the "what would change it" flips are computed in code from verified quotes, so every verdict traces to a quote plus arithmetic. The World Model makes every claim auditable back to the agent, model and round that wrote it, and the critic's objections visibly send work back for a second round.

## 8. Pre-existing components

No product code was written before 22 October 2026, 00:00 UTC (first commit 25 October 2026). Pre-existing third-party material used: the Moratorium Nation dataset by Michael Bommarito (moratorium inventory and state legislation tables, CC BY 4.0, refreshed 23 September 2026), EIA Form 861 utility service territories, US Census geocoder and TIGERweb boundaries, HIFLD transmission lines, and the open Meterless engine specifications (World Model, Markovian; Apache-2.0), which were re-implemented in Python during the build window. Open-source libraries are listed in `pyproject.toml`.

## 9. Colab links

Not used.

## Remaining steps (user)

1. Done 2026-10-27: repository public at https://github.com/wjgoarxiv/sitewhy (master = 2b2cda0). Open it once in a logged-out window.
2. The mp4 is committed in the repository and linked from the README "Demo video" section. Open the link in a private window and confirm it plays with audio; keep the local copy as a backup.
3. Fill in the team fields, paste sections 1–9, attach or link the deck, submit, and save the confirmation.
