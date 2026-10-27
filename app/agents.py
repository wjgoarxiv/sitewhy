"""Agent roles. Models extract, explain and object; code verifies and computes.

Each role is a thin prompt + parser around ModelRouter.generate. The orchestrator
decides who runs when; nothing here calls another role directly.
"""

import json
import re

from app.markovian import Markovian
from app.screen import parse_json_object

FIELDS = ("effective", "duration_days", "scope", "exempt_if_permits_submitted")
OBJECTION_TYPES = (
    "unsupported_link",
    "missed_exemption",
    "source_conflict",
    "threshold_misread",
    "unknown_input",
)


def parse_json_list(text: str) -> list:
    """Last JSON array of objects in the text; ignores bracketed markers like [STATE]."""
    decoder, found = json.JSONDecoder(), []
    for m in re.finditer(r"\[\s*(\{|\])", text):
        try:
            value, _ = decoder.raw_decode(text[m.start() :])
        except json.JSONDecodeError:
            continue
        if isinstance(value, list):
            found = value
    return found


def _chat(system: str, user: str) -> list[dict]:
    return [{"role": "system", "content": system}, {"role": "user", "content": user}]


class Planner:
    SYSTEM = (
        "You are the planner of a data center site screening team. For each local rule "
        "listed, write the questions an investigator must answer from the primary sources to "
        "decide whether it applies: effective date, duration, geographic scope (countywide or "
        "unincorporated only), and exemptions. Reply with a JSON list: "
        '[{"rule_id": "...", "questions": ["..."]}]. Only use rule ids from the list.'
    )

    def __init__(self, router):
        self.router = router

    def plan(self, site: dict, rules: list[dict], focus: list[str] | None = None) -> list[dict]:
        user = f"Site: {json.dumps(site)}\nLocal rules: {json.dumps(rules)}"
        if focus:
            user += "\nRe-plan ONLY to resolve these critic objections:\n" + "\n".join(focus)
        out = self.router.generate("plan", _chat(self.SYSTEM, user), role="planner")
        ids = {r["id"] for r in rules}
        tasks = [
            {"rule_id": t["rule_id"], "questions": [str(q) for q in t.get("questions", [])][:6]}
            for t in parse_json_list(out.text)
            if isinstance(t, dict) and t.get("rule_id") in ids
        ]
        planned = {t["rule_id"] for t in tasks}
        default_q = [f"What is the {f.replace('_', ' ')}?" for f in FIELDS]
        tasks += [{"rule_id": i, "questions": default_q} for i in sorted(ids - planned)]
        return tasks


class CountyInvestigator:
    """Reads primary sources through a Markovian chunk chain and returns facts with quotes."""

    SYSTEM = (
        "You are a county land-use investigator. Work only from the SOURCES text. For every "
        "fact, copy the supporting sentence exactly as written (verbatim, no paraphrase)."
    )

    def __init__(self, router, chunk_config: dict | None = None):
        self.router = router
        self.engine = Markovian(
            chunk_config=chunk_config or {"chunkSize": 8000, "carryoverTokens": 768, "maxChunks": 4}
        )
        self.runs: list = []
        self._step = "extract"

    def _generate(self, prompt: str, system: str | None = None) -> dict:
        out = self.router.generate(
            self._step, _chat(system or self.SYSTEM, prompt), role="county_investigator"
        )
        self._raw.append(out.text)
        return {"text": out.text}

    def start_run(self) -> None:
        """A new screening run: drop the previous run's Markovian runs."""
        self.runs = []

    def investigate(
        self,
        rule: dict,
        questions: list[str],
        sources: list[dict],
        feedback: str = "",
        step: str = "extract",
    ) -> list[dict]:
        self._step = step
        memory = "\n\n".join(
            f"SOURCE {i + 1} (url: {s['url']}):\n{s['text'][:7000]}" for i, s in enumerate(sources)
        )
        goal = (
            f"Rule: {rule['title']}.\nQuestions:\n- " + "\n- ".join(questions) + "\n\n"
            "If the sources are short enough, answer in this first reply. Otherwise note the "
            "relevant sentences first and answer in a later chunk. The answer is a "
            "JSON list of facts, one per answered question: "
            '[{"field": "effective|duration_days|scope|exempt_if_permits_submitted|other", '
            '"value": "<ISO date, number of days, countywide|unincorporated, true|false, '
            'or text>", '
            '"quote": "<exact sentence from a source>", "url": "<that source url>"}]. '
            "field must be exactly one of effective, duration_days, scope, "
            "exempt_if_permits_submitted, other. "
            "Use field other for anything else. Omit facts the sources do not state. "
            "Write your notes or the JSON first; the [STATE_CHECKPOINT] block always goes LAST."
        )
        if feedback:
            goal += f"\n\nVerifier feedback from the previous attempt: {feedback}"
        self._raw: list[str] = []
        run = self.engine.run(
            goal=goal,
            generator=self._generate,
            memory_context=memory,
            system=self.SYSTEM,
            reflect=False,
        )
        self.runs.append(run)
        facts = next((f for f in map(parse_json_list, reversed(self._raw)) if f), [])
        return [
            f
            for f in facts
            if isinstance(f, dict) and f.get("quote") and f.get("url") and f.get("field")
        ]


class Adjudicator:
    SYSTEM = (
        "You are the adjudicator. The applicability results were computed by code; do not "
        "change them. Grade each rule (fatal: blocks the project now; major: costly or slow; "
        "minor; info: does not apply) and write a cross-layer why-chain that links power, "
        "permits, air and local politics to one verdict. Every sentence must rest on a "
        "finding's quote, reason or computed values; never add timelines, costs, motives or "
        "exemptions that the findings do not state. Name assumptions as assumptions. "
        "Reply with JSON: "
        '{"verdict": "go|conditional|no-go|needs_confirmation", "why": "<3-5 sentences>", '
        '"grades": {"<rule_id>": "fatal|major|minor|info"}}.'
    )

    def __init__(self, router):
        self.router = router

    def adjudicate(self, site: dict, findings: list[dict], objections: list[dict]) -> dict:
        user = (
            f"Site and project: {json.dumps(site)}\nFindings: {json.dumps(findings)}\n"
            f"Open objections from the critic: {json.dumps(objections)}"
        )
        out = self.router.generate("synthesize", _chat(self.SYSTEM, user), role="adjudicator")
        return parse_json_object(out.text) or {}


class Critic:
    SYSTEM = (
        "You are a red-team reviewer. Attack the draft verdict. Object only where the "
        "evidence shows a real problem: a why-chain link with no verified quote "
        "(unsupported_link), an exemption the draft ignored (missed_exemption), two sources "
        "that disagree (source_conflict), a threshold applied wrongly (threshold_misread), or a "
        "project fact the decision depends on that nobody knows (unknown_input). Assumptions "
        "already listed in a finding's computed values are disclosed by design; object to one "
        "only if a plausible alternative would flip that finding. Reply with a "
        'JSON list: [{"rule_id": "...", "type": "<one of the types>", "text": "<objection>", '
        '"question": "<what would resolve it>"}]. Reply [] if the draft holds.'
    )

    def __init__(self, router):
        self.router = router

    def review(self, site: dict, draft: dict, findings: list[dict], conflicts: list) -> list[dict]:
        user = (
            f"Site and project: {json.dumps(site)}\nDraft: {json.dumps(draft)}\n"
            f"Findings with verification status: {json.dumps(findings)}\n"
            f"Source conflicts in the evidence graph: {json.dumps(conflicts)}"
        )
        out = self.router.generate("critique", _chat(self.SYSTEM, user), role="critic")
        ids = {f["rule_id"] for f in findings}
        return [
            o
            for o in parse_json_list(out.text)
            if isinstance(o, dict) and o.get("type") in OBJECTION_TYPES and o.get("rule_id") in ids
        ]
