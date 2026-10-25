"""Multi-agent screening loop with verification retries, a critic, and escalation.

plan -> investigate (Markovian) -> verify (code, retry <= 2) -> applicability (code)
-> adjudicate -> critique -> targeted re-plan and re-investigation (<= 2 rounds)
-> unresolved objections escalate to needs_confirmation.

Every step writes to a per-run Meterless World Model whose JSONL log is the trace.
"""

import json
import re
import uuid
from dataclasses import asdict
from datetime import UTC, date, datetime
from pathlib import Path

from app.agents import Adjudicator, CountyInvestigator, Critic, Planner
from app.applicability import Project, moratorium_applies
from app.layers import evaluate_rule, load_county_sources, load_rules
from app.screen import DISCLAIMER, VERDICTS, Screener
from app.worldmodel import WorldModel

ROOT = Path(__file__).resolve().parent.parent
RUNS_DIR = ROOT / "runs"
GRADES = {"fatal", "major", "minor", "info"}
WORDS = {
    "one": 1,
    "two": 2,
    "three": 3,
    "four": 4,
    "six": 6,
    "nine": 9,
    "twelve": 12,
    "eighteen": 18,
    "twenty-four": 24,
}


def parse_days(value) -> int | None:
    text = str(value).lower()
    m = re.search(r"(\d+(?:\.\d+)?)\s*(day|month|year)?", text)
    if m:
        n = float(m.group(1))
    else:
        word = next((w for w in WORDS if w in text), None)
        if not word:
            return None
        n = WORDS[word]
        m = re.search(r"(day|month|year)", text)
    unit = (m.group(2) if m and m.lastindex and m.lastindex >= 2 else None) or (
        "month" if "month" in text else "year" if "year" in text else "day"
    )
    return round(n * {"day": 1, "month": 365 / 12, "year": 365}[unit])


def parse_date(value) -> str | None:
    m = re.search(r"\d{4}-\d{2}-\d{2}", str(value))
    if not m:
        return None
    try:
        return date.fromisoformat(m.group(0)).isoformat()
    except ValueError:
        return None


def parse_fact(field: str, value):
    if field == "effective":
        return parse_date(value)
    if field == "duration_days":
        return parse_days(value)
    if field == "scope":
        text = str(value).lower()
        if "unincorporated" in text:
            return "unincorporated"
        if any(
            k in text for k in ("countywide", "county-wide", "entire county", "all of the county")
        ):
            return "countywide"
        return None
    if field == "exempt_if_permits_submitted":
        return str(value).strip().lower() in {"true", "yes", "1"}
    return str(value)


def new_run_id() -> str:
    return datetime.now(UTC).strftime("%Y%m%dT%H%M%SZ") + "-" + uuid.uuid4().hex[:6]


class Orchestrator:
    def __init__(
        self,
        resolver,
        harness,
        router,
        fetcher,
        runs_dir: Path = RUNS_DIR,
        max_rounds: int = 2,
        max_retries: int = 2,
        as_of: date | None = None,
    ):
        self.resolver = resolver
        self.harness = harness
        self.router = router
        self.fetcher = fetcher
        self.runs_dir = Path(runs_dir)
        self.max_rounds = max_rounds
        self.max_retries = max_retries
        self.as_of = as_of
        self.planner = Planner(router)
        self.investigator = CountyInvestigator(router)
        self.adjudicator = Adjudicator(router)
        self.critic = Critic(router)
        self.county_sources = load_county_sources()

    def _src(self, role: str, round_: int, **extra) -> dict:
        model = self.router.trace[-1]["model"] if self.router.trace else None
        return {
            "kind": "agent",
            "at": datetime.now(UTC).isoformat(),
            "role": role,
            "model": model,
            "round": round_,
            **extra,
        }

    def _event(self, round_: int, role: str, action: str, detail) -> None:
        event = {"round": round_, "role": role, "action": action, "detail": detail,
                 "at": datetime.now(UTC).isoformat()}  # fmt: skip
        self.events.append(event)
        if self.on_event:
            self.on_event(event)

    # -- investigation ---------------------------------------------------

    def _sources_for(self, rule_id: str) -> list[dict]:
        docs = []
        for s in self.county_sources.get(rule_id, []):
            doc = self.fetcher.fetch(s["url"])
            if "text" in doc:
                docs.append({**s, "text": doc["text"]})
            else:
                self._event(0, "evidence_verifier", "fetch_failed", f"{s['url']}: {doc['error']}")
        return docs

    def _investigate(self, rule: dict, questions: list[str], round_: int) -> None:
        sources = self._sources_for(rule["id"])
        if not sources:
            self._event(round_, "county_investigator", "skipped", f"{rule['id']}: no sources")
            return
        feedback = ""
        for attempt in range(1, self.max_retries + 2):
            facts = self.investigator.investigate(rule, questions, sources, feedback)
            run = self.investigator.runs[-1]
            self._event(
                round_,
                "county_investigator",
                "markovian_run",
                {
                    "rule": rule["id"],
                    "attempt": attempt,
                    "chunks": len(run.chunks),
                    "status": run.status,
                    "tokens_saved": run.total_tokens_saved,
                    "token_label": run.token_label,
                    "facts": len(facts),
                },
            )
            failed = []
            for f in facts:
                check = self.fetcher.verify(f["quote"], f["url"])
                # Models often mislabel which source a sentence came from; try the rule's
                # other sources, still verbatim, and record the one that matched.
                for other in (s["url"] for s in sources if s["url"] != f["url"]):
                    if check["status"] == "verified":
                        break
                    alt = self.fetcher.verify(f["quote"], other)
                    if alt["status"] == "verified":
                        check, f = alt, {**f, "url": other}
                self._record_fact(rule, f, check, round_)
                if check["status"] != "verified":
                    failed.append(f["quote"][:120])
            self._event(
                round_,
                "evidence_verifier",
                "verified",
                {
                    "rule": rule["id"],
                    "attempt": attempt,
                    "checked": len(facts),
                    "failed": len(failed),
                },
            )
            if facts and not failed:
                return
            if attempt <= self.max_retries:
                feedback = (
                    (
                        "These quotes were not found verbatim, copy exact sentences: "
                        + " | ".join(failed)
                    )
                    if failed
                    else "No facts returned; answer "
                )
                feedback += "" if failed else "every question you can from the sources."
                self._event(round_, "evidence_verifier", "retry_requested", feedback[:300])

    def _record_fact(self, rule: dict, fact: dict, check: dict, round_: int) -> None:
        wm, src = self.world, self._src("county_investigator", round_)
        doc = wm.upsert_entity(
            type="source_document", name=fact["url"], attrs={"url": fact["url"]}, source=src
        )
        value = parse_fact(fact["field"], fact.get("value"))
        claim = wm.add_claim(
            layer=rule["layer"],
            text=f"{fact['field']} = {value}",
            quote=fact["quote"],
            rule_id=rule["entity"],
            source_id=doc,
            source=src,
            attrs={
                "field": fact["field"],
                "value": value,
                "verification": check["status"],
                "provenance": "primary",
                "rule": rule["id"],
            },
        )
        if check["status"] != "verified" or value is None:
            return
        prior = rule["facts"].setdefault(fact["field"], [])
        others = [("primary", p) for p in prior if p["claim"] != claim]
        if fact["field"] in rule["seed"]:
            others.append(("dataset", rule["seed"][fact["field"]]))
        for kind, other in others:
            if other["value"] == value:
                continue
            wm.relate(claim, "contradicts", other["claim"], source=src, exclusive=False)
            self._event(round_, "evidence_verifier", "conflict",
                        {"rule": rule["id"], "field": fact["field"], "value": value,
                         f"other_{kind}": other["value"]})  # fmt: skip
        if all(p["claim"] != claim for p in prior):
            prior.append({"value": value, "claim": claim})

    # -- assessment ------------------------------------------------------

    def _params(self, rule: dict) -> dict:
        params = {}
        for field in ("effective", "duration_days", "scope", "exempt_if_permits_submitted"):
            live = rule["facts"].get(field)
            seeded = rule["seed"].get(field)
            values = [f["value"] for f in live or []] + ([seeded["value"]] if seeded else [])
            if field == "scope" and "unincorporated" in values:
                # A verified narrower scope beats a broader reading of the same rule.
                params[field] = "unincorporated"
            elif live:
                params[field] = live[-1]["value"]
            elif field in rule["seed"]:
                params[field] = rule["seed"][field]["value"]
        return params

    def _findings(self, local: list[dict], curated: list[dict], project: Project, site) -> list:
        out = []
        for rule in local:
            params = self._params(rule)
            claims = [
                c
                for c in self.world.claims_for(rule["layer"])
                if c["attrs"].get("rule") == rule["id"]
            ]
            out.append(
                {
                    "rule_id": rule["id"],
                    "layer": rule["layer"],
                    "title": rule["title"],
                    **moratorium_applies(project, params),
                    "parameters": params,
                    "evidence": [
                        {
                            "field": c["attrs"]["field"],
                            "quote": c["attrs"]["quote"],
                            "verification": c["attrs"]["verification"],
                            "provenance": c["attrs"]["provenance"],
                            "url": self.world.evidence_path(c["id"])[1]["attrs"].get("url"),
                        }
                        for c in claims
                    ],
                }
            )
        for rule in curated:
            result = evaluate_rule(rule, project, site)
            if result is None:
                continue
            out.append(
                {
                    "rule_id": rule["id"],
                    "layer": rule["layer"],
                    "title": rule["title"],
                    **result,
                    "evidence": [
                        {
                            "quote": rule["quote"],
                            "url": rule["source_url"],
                            "verification": rule["verification"],
                            "provenance": "curated",
                        }
                    ],
                }
            )
        return out

    def _guard(self, draft: dict, findings: list[dict], open_objections: list[dict]) -> dict:
        grades = {k: v for k, v in (draft.get("grades") or {}).items() if v in GRADES}
        notes = []
        for f in findings:
            verified = any(e["verification"] == "verified" for e in f["evidence"])
            grade = grades.get(f["rule_id"], "info" if f["applies"] == "no" else "major")
            if grade == "fatal" and not verified:
                grade = "major"
                notes.append(f"{f['rule_id']}: fatal needs a verified quote; downgraded")
            if f["applies"] == "no" and grade in {"fatal", "major"}:
                grade = "info"
                notes.append(f"{f['rule_id']}: code says it does not apply; graded info")
            f["grade"] = grade
        verdict = draft.get("verdict") if draft.get("verdict") in VERDICTS else "needs_confirmation"
        fatal = [f for f in findings if f["grade"] == "fatal" and f["applies"] == "yes"]
        if verdict == "no-go" and not fatal:
            verdict = "needs_confirmation"
            notes.append("no-go without a verified fatal rule")
        blocking = {o["rule_id"] for o in open_objections}
        if any(f["rule_id"] in blocking and f["grade"] == "fatal" for f in findings):
            verdict = "needs_confirmation"
            notes.append("unresolved critic objections on decisive rules")
        if any(f["applies"] == "unknown" and f["layer"] in {"county", "city"} for f in findings):
            verdict = "needs_confirmation" if verdict == "go" else verdict
        return {"verdict": verdict, "why": draft.get("why", ""), "guard_notes": notes}

    # -- main loop -------------------------------------------------------

    def run(
        self,
        address: str,
        mw: float,
        permits_submitted: bool | None = None,
        run_id: str | None = None,
        on_event=None,
    ) -> dict:
        run_id = run_id or new_run_id()
        self.on_event = on_event
        run_dir = self.runs_dir / run_id
        self.world = WorldModel(log_path=run_dir / "worldmodel.jsonl")
        self.events: list[dict] = []
        model_start, data_start = len(self.router.trace), len(self.harness.trace)

        j = self.resolver.resolve(address)
        project = Project(
            mw=mw,
            as_of=self.as_of or date.today(),
            incorporated=j.place is not None,
            permits_submitted=permits_submitted,
        )
        site = {
            "address": j.matched_address,
            "state": j.state,
            "county": j.county_name,
            "place": j.place,
            "iso": j.iso,
            "mw": mw,
            "as_of": project.as_of.isoformat(),
            "incorporated": project.incorporated,
            "permits_submitted": permits_submitted,
            "utilities": [u["name"] for u in j.utilities],
        }
        sys_src = self._src("system", 0)
        self.world.upsert_entity(
            type="jurisdiction",
            name=j.county_fips,
            attrs={k: site[k] for k in ("state", "county", "place", "iso")},
            source=sys_src,
        )
        self._event(0, "system", "resolved", site)

        local = []
        for ev in Screener(None, self.harness, None).local_evidence(j):
            entity = self.world.upsert_entity(
                type="rule",
                name=ev["id"],
                attrs={"layer": ev["layer"], "title": ev["title"]},
                source=sys_src,
            )
            rule = {
                "id": ev["id"],
                "layer": ev["layer"],
                "title": ev["title"],
                "entity": entity,
                "facts": {},
                "seed": {},
            }
            row = self.harness.query(
                "SELECT date_enacted_iso, duration_days FROM SITEWHY.moratoria "
                f"WHERE moratorium_id = '{ev['id'].replace("'", "''")}'"
            )[0]
            doc = self.world.upsert_entity(
                type="source_document",
                name=ev["source"],
                attrs={"url": ev["source"]},
                source=sys_src,
            )
            seeds = [
                ("effective", row["date_enacted_iso"], ev["quote"]),
                ("duration_days", row["duration_days"], ev["quote"]),
            ]
            scope_text = next(
                (t for t in (ev["summary"], ev["current_status"], ev["quote"])
                 if t and "unincorporated" in t.lower()),
                None,
            )  # fmt: skip
            if scope_text:
                seeds.append(("scope", "unincorporated", scope_text))
            for field, raw, quote in seeds:
                value = parse_fact(field, raw) if raw else None
                if value is None:
                    continue
                claim = self.world.add_claim(
                    layer=ev["layer"],
                    text=f"{field} = {value}",
                    quote=quote,
                    rule_id=entity,
                    source_id=doc,
                    source=sys_src,
                    attrs={
                        "field": field,
                        "value": value,
                        "verification": "dataset",
                        "provenance": "dataset",
                        "rule": ev["id"],
                    },
                )
                rule["seed"][field] = {"value": value, "claim": claim}
            local.append(rule)
        curated = []
        for rule in load_rules():
            if evaluate_rule(rule, project, site) is None:
                continue
            rule = {
                **rule,
                "verification": self.fetcher.verify(rule["quote"], rule["source_url"])["status"],
            }
            curated.append(rule)
        self._event(
            0,
            "system",
            "seeded",
            {"local": [r["id"] for r in local], "curated": [r["id"] for r in curated]},
        )

        rule_briefs = [{"id": r["id"], "title": r["title"], "layer": r["layer"]} for r in local]
        tasks = self.planner.plan(site, rule_briefs) if local else []
        self._event(1, "planner", "tasks", tasks)
        by_id = {r["id"]: r for r in local}
        objections: list[dict] = []
        draft, findings = {}, []
        for round_ in range(1, self.max_rounds + 1):
            for t in tasks:
                self._investigate(by_id[t["rule_id"]], t["questions"], round_)
            findings = self._findings(local, curated, project, site)
            self._event(
                round_,
                "applicability",
                "computed",
                [{k: f[k] for k in ("rule_id", "applies", "reason")} for f in findings],
            )
            draft = self.adjudicator.adjudicate(site, findings, objections)
            self._event(
                round_,
                "adjudicator",
                "draft",
                {"verdict": draft.get("verdict"), "grades": draft.get("grades")},
            )
            for o in self.world.open_objections():
                self.world.resolve_objection(
                    o["id"], f"re-examined in round {round_}", self._src("critic", round_)
                )
            objections = self.critic.review(site, draft, findings, self.world.conflicts())
            for o in objections:
                target = by_id[o["rule_id"]]["entity"] if o["rule_id"] in by_id else None
                if target is None:
                    target = self.world.upsert_entity(
                        type="rule", name=o["rule_id"], source=self._src("critic", round_)
                    )
                o["id"] = self.world.add_objection(
                    target, f"{o['type']}: {o['text']}", round_, self._src("critic", round_)
                )
            self._event(round_, "critic", "objections", objections)
            if not objections or round_ == self.max_rounds:
                break
            focus = [
                f"{o['rule_id']}: {o['text']} -> {o.get('question', '')}"
                for o in objections
                if o["rule_id"] in by_id and o["type"] != "unknown_input"
            ]
            if not focus:
                break
            tasks = self.planner.plan(site, rule_briefs, focus=focus)
            tasks = [t for t in tasks if any(t["rule_id"] in f for f in focus)]
            self._event(round_ + 1, "planner", "targeted_tasks", tasks)

        open_objections = [o for o in objections if o.get("id")]
        result = self._guard(draft, findings, open_objections)
        if open_objections:
            self._event(
                self.max_rounds,
                "system",
                "escalated",
                [f"{o['rule_id']}: {o['text']}" for o in open_objections],
            )
        report = {
            "run_id": run_id,
            "project": {"address": address, "mw": mw, "permits_submitted": permits_submitted},
            "jurisdiction": j.to_dict(),
            **result,
            "findings": findings,
            "needs_confirmation": [
                {
                    "rule_id": o["rule_id"],
                    "type": o["type"],
                    "text": o["text"],
                    "question": o.get("question"),
                }
                for o in open_objections
            ],
            "conflicts": self.world.conflicts(),
            "events": self.events,
            "model_trace": self.router.trace[model_start:],
            "data_trace": self.harness.trace[data_start:],
            "markovian_runs": [
                {k: v for k, v in asdict(r).items() if k not in {"chunks", "output"}}
                for r in self.investigator.runs
            ],
            "worldmodel_log": str(run_dir / "worldmodel.jsonl"),
            "disclaimer": DISCLAIMER,
        }
        (run_dir / "report.json").write_text(json.dumps(report, indent=1, default=str))
        return report
