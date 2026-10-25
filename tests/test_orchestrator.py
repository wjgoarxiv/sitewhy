import json
from datetime import date

import httpx
import pytest

from app.data import DuckDbHarness, FallbackHarness
from app.evidence import EvidenceFetcher
from app.layers import load_county_sources, load_rules
from app.llm import Completion
from app.orchestrator import Orchestrator, parse_date, parse_days
from app.seed import register_seed
from app.worldmodel import WorldModel
from tests.test_screen import WASHINGTON, FakeResolver

RELEASE_URL = load_county_sources()["md-washington-county-2026"][0]["url"]
PDF_URL = load_county_sources()["md-washington-county-2026"][1]["url"]
TITLE_V = next(r for r in load_rules() if r["id"] == "federal-title-v-major-source")
RELEASE = (
    "On June 30, 2026, the Washington County Board of County Commissioners approved a "
    "temporary, twelve (12) month moratorium on the acceptance, processing, reviewing and "
    "approval of applications, plans, or requests for data centers within Washington County."
)
GOOD_FACTS = [
    {
        "field": "effective",
        "value": "2026-06-30",
        "url": RELEASE_URL,
        "quote": "On June 30, 2026, the Washington County Board of County Commissioners approved",
    },
    {
        "field": "duration_days",
        "value": "twelve (12) month",
        "url": RELEASE_URL,
        "quote": "a temporary, twelve (12) month moratorium on the acceptance",
    },
    {
        "field": "scope",
        "value": "countywide",
        "url": RELEASE_URL,
        "quote": "requests for data centers within Washington County",
    },
]


def serve(request):
    url = str(request.url)
    if url.endswith("robots.txt"):
        return httpx.Response(404)
    if url == RELEASE_URL:
        return httpx.Response(200, text=f"<p>{RELEASE}</p>", headers={"content-type": "text/html"})
    if url == TITLE_V["source_url"]:
        return httpx.Response(200, text=f"<p>... {TITLE_V['quote']} ...</p>")
    return httpx.Response(404)


class ScriptedRouter:
    """Answers each role from its own queue and records a trace like ModelRouter."""

    def __init__(self, **queues):
        self.queues = {k: list(v) for k, v in queues.items()}
        self.trace, self.calls = [], []

    def generate(self, step, messages, role=None, **kw):
        self.calls.append((role, messages[-1]["content"]))
        queue = self.queues.get(role, [])
        text = queue.pop(0) if queue else "[]"
        self.trace.append({"step": step, "role": role, "model": "nvidia/fake", "receipt_id": "r"})
        return Completion(text, "nvidia/fake", "r", False)


def facts_reply(facts):
    return "Reading done.\n" + json.dumps(facts) + "\n[TASK_COMPLETE]"


DRAFT_NO_GO = json.dumps(
    {
        "verdict": "no-go",
        "why": "A countywide 12-month moratorium blocks approvals.",
        "grades": {"md-washington-county-2026": "fatal", "federal-title-v-major-source": "major"},
    }
)
PLAN = json.dumps([{"rule_id": "md-washington-county-2026", "questions": ["When effective?"]}])


@pytest.fixture
def orchestrator_factory(tmp_path):
    def make(router, as_of=date(2026, 10, 25)):
        h = FallbackHarness(DuckDbHarness(), DuckDbHarness())
        register_seed(h.primary)
        fetcher = EvidenceFetcher(
            client=httpx.Client(transport=httpx.MockTransport(serve)), cache_dir=tmp_path / "src"
        )
        return Orchestrator(
            FakeResolver(WASHINGTON), h, router, fetcher, runs_dir=tmp_path / "runs", as_of=as_of
        )

    return make


def test_parse_days_and_dates():
    assert parse_days("twelve (12) month") == 365
    assert parse_days("120 days") == 120 and parse_days("12 months") == 365
    assert parse_days("1 year") == 365 and parse_days("six months") == 182
    assert parse_days("soon") is None
    assert parse_date("adopted 2026-06-30") == "2026-06-30" and parse_date("June") is None


def test_happy_path_no_go_with_verified_primary_quotes(orchestrator_factory):
    router = ScriptedRouter(
        planner=[PLAN],
        county_investigator=[facts_reply(GOOD_FACTS)],
        adjudicator=[DRAFT_NO_GO],
        critic=["[]"],
    )
    report = orchestrator_factory(router).run("addr", mw=300)
    assert report["verdict"] == "no-go" and report["needs_confirmation"] == []
    wash = next(f for f in report["findings"] if f["rule_id"] == "md-washington-county-2026")
    assert wash["applies"] == "yes" and wash["grade"] == "fatal"
    assert wash["parameters"] == {
        "effective": "2026-06-30",
        "duration_days": 365,
        "scope": "countywide",
    }
    assert {e["provenance"] for e in wash["evidence"]} == {"primary", "dataset"}
    tv = next(f for f in report["findings"] if f["rule_id"] == "federal-title-v-major-source")
    assert tv["applies"] == "yes" and tv["evidence"][0]["verification"] == "verified"
    roles = [e["role"] for e in report["events"]]
    for role in ("planner", "county_investigator", "evidence_verifier", "adjudicator", "critic"):
        assert role in roles
    replayed = WorldModel.replay(report["worldmodel_log"])
    assert len(replayed.claims_for("county")) >= 5
    assert report["markovian_runs"][0]["status"] == "completed"


def test_unverifiable_quote_triggers_retry_with_feedback(orchestrator_factory):
    bad = [{**GOOD_FACTS[0], "quote": "The county banned data centers forever and ever."}]
    router = ScriptedRouter(
        planner=[PLAN],
        county_investigator=[facts_reply(bad), facts_reply(GOOD_FACTS)],
        adjudicator=[DRAFT_NO_GO],
        critic=["[]"],
    )
    report = orchestrator_factory(router).run("addr", mw=300)
    actions = [(e["role"], e["action"]) for e in report["events"]]
    assert ("evidence_verifier", "retry_requested") in actions
    second_prompt = [c for r, c in router.calls if r == "county_investigator"][1]
    assert "not found verbatim" in second_prompt
    assert report["verdict"] == "no-go"


def test_critic_objection_drives_targeted_second_round(orchestrator_factory):
    objection = json.dumps(
        [
            {
                "rule_id": "md-washington-county-2026",
                "type": "missed_exemption",
                "text": "Does it exempt pending applications?",
                "question": "Check for exemptions",
            }
        ]
    )
    router = ScriptedRouter(
        planner=[PLAN, PLAN],
        county_investigator=[facts_reply(GOOD_FACTS), facts_reply(GOOD_FACTS)],
        adjudicator=[DRAFT_NO_GO, DRAFT_NO_GO],
        critic=[objection, "[]"],
    )
    report = orchestrator_factory(router).run("addr", mw=300)
    rounds = {e["round"] for e in report["events"] if e["role"] == "county_investigator"}
    assert rounds == {1, 2}
    assert any(e["action"] == "targeted_tasks" for e in report["events"])
    assert report["verdict"] == "no-go" and report["needs_confirmation"] == []
    assert "Check for exemptions" in [c for r, c in router.calls if r == "planner"][1]


def test_unresolved_objection_escalates_to_needs_confirmation(orchestrator_factory):
    unknown = json.dumps(
        [
            {
                "rule_id": "md-washington-county-2026",
                "type": "unknown_input",
                "text": "Permit status unknown",
                "question": "Ask the developer",
            }
        ]
    )
    router = ScriptedRouter(
        planner=[PLAN],
        county_investigator=[facts_reply(GOOD_FACTS)],
        adjudicator=[DRAFT_NO_GO],
        critic=[unknown],
    )
    report = orchestrator_factory(router).run("addr", mw=300)
    assert report["verdict"] == "needs_confirmation"
    assert report["needs_confirmation"][0]["type"] == "unknown_input"
    assert any(e["action"] == "escalated" for e in report["events"])


def test_fatal_grade_without_verified_quote_is_downgraded(orchestrator_factory):
    router = ScriptedRouter(
        planner=[PLAN],
        county_investigator=[facts_reply([]), facts_reply([]), facts_reply([])],
        adjudicator=[DRAFT_NO_GO],
        critic=["[]"],
    )
    report = orchestrator_factory(router).run("addr", mw=300)
    wash = next(f for f in report["findings"] if f["rule_id"] == "md-washington-county-2026")
    assert wash["grade"] == "major"
    assert report["verdict"] == "needs_confirmation"
    assert any("fatal needs a verified quote" in n for n in report["guard_notes"])


def test_primary_source_disagreeing_with_dataset_creates_conflict(orchestrator_factory):
    shifted = [{**GOOD_FACTS[1], "value": "18 months"}]
    router = ScriptedRouter(
        planner=[PLAN],
        county_investigator=[facts_reply(shifted)],
        adjudicator=[DRAFT_NO_GO],
        critic=["[]"],
    )
    report = orchestrator_factory(router).run("addr", mw=300)
    assert report["conflicts"]
    assert any(e["action"] == "conflict" for e in report["events"])


def test_parse_json_list_skips_markers_and_takes_last_array():
    from app.agents import parse_json_list

    text = '[STATE_CHECKPOINT]\nCOMPLETED: x\n[{"a": 1}] then [{"b": 2}]\n[TASK_COMPLETE]'
    assert parse_json_list(text) == [{"b": 2}]
    assert parse_json_list("[STATE] nothing") == []
    assert parse_json_list("facts: []") == []


def test_facts_found_even_when_state_marker_comes_first(orchestrator_factory):
    leading = (
        "[STATE_CHECKPOINT]\nCOMPLETED: read\n\n" + json.dumps(GOOD_FACTS) + "\n[TASK_COMPLETE]"
    )
    router = ScriptedRouter(
        planner=[PLAN],
        county_investigator=[leading],
        adjudicator=[DRAFT_NO_GO],
        critic=["[]"],
    )
    report = orchestrator_factory(router).run("addr", mw=300)
    assert report["verdict"] == "no-go"


def test_two_primary_sources_that_disagree_create_a_conflict(orchestrator_factory):
    six = {**GOOD_FACTS[1], "value": "6 months", "quote": "approved a temporary, twelve (12) month"}
    router = ScriptedRouter(
        planner=[PLAN],
        county_investigator=[facts_reply([GOOD_FACTS[1], six])],
        adjudicator=[DRAFT_NO_GO],
        critic=["[]"],
    )
    report = orchestrator_factory(router).run("addr", mw=300)
    conflict = [e for e in report["events"] if e["action"] == "conflict"]
    assert any("other_primary" in e["detail"] for e in conflict)
