"""Single-pass screener (M1 walking skeleton): resolve the site, pull local
moratoria from the data layer, and let the adjudicator model explain which ones
apply. Findings may only cite evidence ids that the data layer returned.
"""

import json
import re

from app.seed import MORATORIA_SOURCE

VERDICTS = {"go", "conditional", "no-go", "needs_confirmation"}
DISCLAIMER = "Screening aid, not legal advice. Confirm every finding with the cited source."

SYSTEM = (
    "You are the adjudicator in a US data center site screening team. Decide whether "
    "the listed local rules block or constrain the proposed project. Use ONLY the "
    "evidence provided; never invent rules, dates, or citations. Reply with one JSON "
    'object: {"verdict": "go|conditional|no-go|needs_confirmation", "why": "<2-4 '
    'sentences linking the decisive facts>", "findings": [{"evidence_id": "<id from '
    'the list>", "grade": "fatal|major|minor|info", "applies": "yes|no|unknown", '
    '"reasoning": "<why it does or does not apply to this project>"}]}.'
)


def parse_json_object(text: str) -> dict | None:
    start = text.find("{")
    while start != -1:
        depth = 0
        for i in range(start, len(text)):
            depth += {"{": 1, "}": -1}.get(text[i], 0)
            if depth == 0:
                try:
                    obj = json.loads(text[start : i + 1])
                except json.JSONDecodeError:
                    break
                return obj if isinstance(obj, dict) else None
        start = text.find("{", start + 1)
    return None


def _sql_str(value: str) -> str:
    return "'" + value.replace("'", "''") + "'"


def _local_names(j) -> list[str]:
    names = [j.county_name]
    if j.place:
        names.append(re.sub(r" (city|town|village|borough)$", "", j.place))
    return names


class Screener:
    def __init__(self, resolver, harness, router):
        self.resolver = resolver
        self.harness = harness
        self.router = router

    def state_actions(self, j) -> list[dict]:
        rows = self.harness.query(
            "SELECT policy_action_id, bill, status, key_provisions, policy_mechanism, "
            "scope_of_action, legal_effect_status, bill_status_category, "
            "last_action_date_iso, primary_source_url FROM SITEWHY.state_legislation "
            f"WHERE state_abbrev = {_sql_str(j.state)} "
            "AND (bill_status_category = 'enacted' OR legal_effect_status = 'in_force') "
            "ORDER BY last_action_date_iso DESC"
        )
        return rows

    def local_evidence(self, j) -> list[dict]:
        names = ", ".join(_sql_str(n) for n in _local_names(j))
        rows = self.harness.query(
            "SELECT moratorium_id, jurisdiction, jurisdiction_type, date_enacted_iso, duration, "
            "legal_basis, trigger, outcome, current_status, enacted_status "
            "FROM SITEWHY.moratoria "
            f"WHERE state_abbrev = {_sql_str(j.state)} AND jurisdiction IN ({names}) "
            "AND sectors LIKE '%data_center%' ORDER BY moratorium_id"
        )
        return [
            {
                "id": r["moratorium_id"],
                "layer": "county" if r["jurisdiction_type"] == "County" else "city",
                "title": f"{r['jurisdiction']} data center moratorium",
                "status": r["enacted_status"],
                "enacted": r["date_enacted_iso"],
                "duration": r["duration"],
                "legal_basis": r["legal_basis"],
                "summary": r["trigger"],
                "quote": r["outcome"] or r["legal_basis"] or r["trigger"],
                "current_status": r["current_status"],
                "source": MORATORIA_SOURCE,
            }
            for r in rows
        ]

    def screen(self, address: str, mw: float) -> dict:
        model_start = len(self.router.trace)
        data_start = len(self.harness.trace)
        j = self.resolver.resolve(address)
        evidence = self.local_evidence(j)
        facts = {
            "project_mw": mw,
            "address": j.matched_address,
            "state": j.state,
            "county": j.county_name,
            "place": j.place,
            "iso_rto": j.iso,
            "utilities": [u["name"] for u in j.utilities],
        }
        prompt = (
            f"Project and site facts:\n{json.dumps(facts, indent=1)}\n\n"
            f"Evidence (local moratoria in this county or city):\n{json.dumps(evidence, indent=1)}"
            "\n\nIf the evidence list is empty, say no local moratorium was found in the data "
            "and that other layers are not yet assessed."
        )
        out = self.router.generate(
            "synthesize",
            [{"role": "system", "content": SYSTEM}, {"role": "user", "content": prompt}],
            role="adjudicator",
        )
        decision = parse_json_object(out.text) or {}
        by_id = {e["id"]: e for e in evidence}
        findings, dropped = [], []
        for f in decision.get("findings") or []:
            if f.get("evidence_id") in by_id:
                findings.append({**f, "evidence": by_id[f["evidence_id"]]})
            else:
                dropped.append(f.get("evidence_id"))
        verdict = decision.get("verdict")
        return {
            "project": {"address": address, "mw": mw},
            "jurisdiction": j.to_dict(),
            "verdict": verdict if verdict in VERDICTS else "needs_confirmation",
            "why": decision.get("why", ""),
            "findings": findings,
            "dropped_findings": dropped,
            "evidence": evidence,
            "model_trace": self.router.trace[model_start:],
            "data_trace": self.harness.trace[data_start:],
            "disclaimer": DISCLAIMER,
        }
