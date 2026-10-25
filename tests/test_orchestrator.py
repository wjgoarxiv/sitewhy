import json
from dataclasses import replace
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
    "approval of applications, plans, or requests for data centers within Washington County. "
    "A six-month review was proposed. A thirty-day pause was also discussed."
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


WASHINGTON_UNINCORPORATED = replace(
    WASHINGTON,
    place=None,
    county_subdivision="District 27, Fountain Head",
    matched_address="13820 PENNSYLVANIA AVE, HAGERSTOWN, MD, 21742",
)


@pytest.fixture
def orchestrator_factory(tmp_path):
    def make(router, as_of=date(2026, 10, 25), jurisdiction=WASHINGTON):
        h = FallbackHarness(DuckDbHarness(), DuckDbHarness())
        register_seed(h.primary)
        fetcher = EvidenceFetcher(
            client=httpx.Client(transport=httpx.MockTransport(serve)), cache_dir=tmp_path / "src"
        )
        return Orchestrator(
            FakeResolver(jurisdiction), h, router, fetcher, runs_dir=tmp_path / "runs", as_of=as_of
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
    report = orchestrator_factory(router, jurisdiction=WASHINGTON_UNINCORPORATED).run(
        "addr", mw=300
    )
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
    report = orchestrator_factory(router, jurisdiction=WASHINGTON_UNINCORPORATED).run(
        "addr", mw=300
    )
    actions = [(e["role"], e["action"]) for e in report["events"]]
    assert ("evidence_verifier", "retry_requested") in actions
    second_prompt = [c for r, c in router.calls if r == "county_investigator"][1]
    assert "not found verbatim" in second_prompt
    assert report["verdict"] == "no-go"


def test_zero_fact_attempt_gets_format_aware_retry_feedback(orchestrator_factory):
    router = ScriptedRouter(
        planner=[PLAN],
        county_investigator=[
            "Relevant sentences noted. [STATE_CHECKPOINT]",
            "More notes, still no JSON. [STATE_CHECKPOINT]",
            "Yet more notes. [STATE_CHECKPOINT]",
            "Final notes, no JSON. [STATE_CHECKPOINT]",
            facts_reply(GOOD_FACTS),
        ],
        adjudicator=[DRAFT_NO_GO],
        critic=["[]"],
    )
    report = orchestrator_factory(router).run("addr", mw=300)
    retries = [e for e in report["events"] if e["action"] == "retry_requested"]
    assert retries and "no JSON array" in str(retries[0]["detail"])
    retry_prompts = [
        c for r, c in router.calls
        if r == "county_investigator" and "Verifier feedback" in c
    ]
    assert retry_prompts and "JSON array of facts FIRST" in retry_prompts[0]


def test_immaterial_source_conflict_does_not_block_no_go(orchestrator_factory):
    from app.explain import enrich

    six = {"field": "duration", "value": "six (6) months",
           "url": RELEASE_URL, "quote": "six-month review was proposed"}
    twelve = {"field": "duration_days", "value": "twelve (12) months",
              "url": RELEASE_URL,
              "quote": "a temporary, twelve (12) month moratorium on the acceptance"}
    scope = {"field": "scope", "value": "countywide",
             "url": RELEASE_URL, "quote": "requests for data centers within Washington County"}
    objection = {"rule_id": "md-washington-county-2026", "type": "source_conflict",
                 "text": "6 vs 12 months", "question": "Which duration is correct?"}
    router = ScriptedRouter(
        planner=[PLAN, "[]"],
        county_investigator=[facts_reply([six, twelve, scope])],
        adjudicator=[DRAFT_NO_GO, DRAFT_NO_GO],
        critic=[json.dumps([objection]), json.dumps([objection])],
    )
    report = orchestrator_factory(router, jurisdiction=WASHINGTON_UNINCORPORATED).run(
        "addr", mw=300
    )
    assert report["verdict"] == "no-go"
    assert any(e["action"] == "objection_resolved_by_code" for e in report["events"])
    entry = next(o for o in report["needs_confirmation"]
                 if o["rule_id"] == "md-washington-county-2026")
    assert entry["blocking"] is False
    assert "2026-12-29" in entry["question"] and "2027-06-30" in entry["question"]
    catches = enrich(report)["explanation"]["catches"]
    assert any(c["kind"] == "source_conflict" and "resolved by code" in c["outcome"]
               for c in catches)


def test_material_source_conflict_still_blocks(orchestrator_factory):
    thirty = {"field": "duration", "value": "thirty (30) days",
              "url": RELEASE_URL, "quote": "thirty-day pause was also discussed"}
    twelve = {"field": "duration_days", "value": "twelve (12) months",
              "url": RELEASE_URL,
              "quote": "a temporary, twelve (12) month moratorium on the acceptance"}
    scope = {"field": "scope", "value": "countywide",
             "url": RELEASE_URL, "quote": "requests for data centers within Washington County"}
    objection = {"rule_id": "md-washington-county-2026", "type": "source_conflict",
                 "text": "30 days vs 12 months", "question": "Which duration is correct?"}
    router = ScriptedRouter(
        planner=[PLAN, "[]"],
        county_investigator=[facts_reply([thirty, twelve, scope])],
        adjudicator=[DRAFT_NO_GO, DRAFT_NO_GO],
        critic=[json.dumps([objection]), json.dumps([objection])],
    )
    report = orchestrator_factory(router, jurisdiction=WASHINGTON_UNINCORPORATED).run(
        "addr", mw=300
    )
    assert report["verdict"] == "needs_confirmation"
    entry = next(o for o in report["needs_confirmation"]
                 if o["rule_id"] == "md-washington-county-2026")
    assert entry.get("blocking", True) is True
    assert not [e for e in report["events"] if e["action"] == "objection_resolved_by_code"]


def test_final_attempt_after_zero_facts_uses_ultra(orchestrator_factory):
    router = ScriptedRouter(
        planner=[PLAN],
        county_investigator=["Notes only, no JSON. [STATE_CHECKPOINT]"] * 12,
        adjudicator=[DRAFT_NO_GO],
        critic=["[]"],
    )
    report = orchestrator_factory(router).run("addr", mw=300)
    steps = [t["step"] for t in router.trace if t["role"] == "county_investigator"]
    assert steps[-4:] == ["plan"] * 4 and set(steps[:-4]) == {"extract"}
    assert any(
        e["action"] == "ultra_reextract" for e in report["events"]
    )


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
    report = orchestrator_factory(router, jurisdiction=WASHINGTON_UNINCORPORATED).run(
        "addr", mw=300
    )
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
    shifted = [{**GOOD_FACTS[1], "value": "six (6) months",
                "quote": "six-month review was proposed"}]
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
    report = orchestrator_factory(router, jurisdiction=WASHINGTON_UNINCORPORATED).run(
        "addr", mw=300
    )
    assert report["verdict"] == "no-go"


def test_two_primary_sources_that_disagree_create_a_conflict(orchestrator_factory):
    six = {**GOOD_FACTS[1], "value": "6 months", "quote": "six-month review was proposed"}
    router = ScriptedRouter(
        planner=[PLAN],
        county_investigator=[facts_reply([GOOD_FACTS[1], six])],
        adjudicator=[DRAFT_NO_GO],
        critic=["[]"],
    )
    report = orchestrator_factory(router).run("addr", mw=300)
    conflict = [e for e in report["events"] if e["action"] == "conflict"]
    assert any("other_primary" in e["detail"] for e in conflict)


def test_quote_attributed_to_wrong_source_is_verified_against_the_rule_sources(
    orchestrator_factory,
):
    misattributed = [{**GOOD_FACTS[0], "url": PDF_URL}]
    router = ScriptedRouter(
        planner=[PLAN],
        county_investigator=[facts_reply(misattributed + GOOD_FACTS[1:])],
        adjudicator=[DRAFT_NO_GO],
        critic=["[]"],
    )
    report = orchestrator_factory(router).run("addr", mw=300)
    wash = next(f for f in report["findings"] if f["rule_id"] == "md-washington-county-2026")
    eff = [
        e for e in wash["evidence"] if e["field"] == "effective" and e["provenance"] == "primary"
    ]
    assert eff and eff[0]["verification"] == "verified"


def test_scope_parsing_is_explicit():
    from app.orchestrator import parse_fact

    assert parse_fact("scope", "unincorporated Pima County") == "unincorporated"
    assert parse_fact("scope", "countywide") == "countywide"
    assert parse_fact("scope", "Pima County") is None


def test_real_duration_conflict_only(orchestrator_factory):
    """(a) duration_draft_ordinance + duration canonicalize to one duration_days conflict."""
    from app.worldmodel import WorldModel

    # Empty seed so only the primary-primary disagreement counts
    # (Washington's dataset seed would add a second event).
    orch = orchestrator_factory(ScriptedRouter())
    orch.world = WorldModel()
    orch.events = []
    orch.on_event = None
    src = orch._src("system", 0)
    entity = orch.world.upsert_entity(type="rule", name="test-rule", source=src)
    rule = {"id": "test-rule", "layer": "county", "title": "t",
            "entity": entity, "facts": {}, "seed": {}}
    f1 = {"field": "duration_draft_ordinance", "value": "six (6) months",
          "url": "https://example.com/draft", "quote": "for a period of six (6) months"}
    f2 = {"field": "duration", "value": "twelve (12) months",
          "url": "https://example.com/release", "quote": "for twelve (12) months"}
    orch._record_fact(rule, f1, {"status": "verified"}, 1)
    orch._record_fact(rule, f2, {"status": "verified"}, 1)
    conflicts = [e for e in orch.events if e["action"] == "conflict"]
    assert len(conflicts) == 1
    detail = conflicts[0]["detail"]
    assert detail["field"] == "duration_days"
    assert sorted([detail["value"], detail["other_primary"]]) == [182, 365]
    assert detail["quote"] and detail["url"] and detail["other_quote"] and detail["other_url"]


def test_none_value_gives_zero_conflicts(orchestrator_factory):
    long_quote = "a temporary, twelve (12) month moratorium on the acceptance"
    facts = [
        {"field": "duration", "value": "None", "url": RELEASE_URL, "quote": long_quote},
        {"field": "duration", "value": "twelve (12) months",
         "url": RELEASE_URL, "quote": "temporary, twelve (12) month"},
    ]
    router = ScriptedRouter(
        planner=[PLAN],
        county_investigator=[facts_reply(facts)],
        adjudicator=[DRAFT_NO_GO],
        critic=["[]"],
    )
    report = orchestrator_factory(router).run("addr", mw=300)
    assert [e for e in report["events"] if e["action"] == "conflict"] == []


def test_state_watch_present_and_never_in_findings(orchestrator_factory):
    router = ScriptedRouter(
        planner=[PLAN],
        county_investigator=[facts_reply(GOOD_FACTS)],
        adjudicator=[DRAFT_NO_GO],
        critic=["[]"],
    )
    report = orchestrator_factory(router).run("addr", mw=300)
    assert "state_watch" in report and report["state_watch"]
    watch_ids = {r["policy_action_id"] for r in report["state_watch"]}
    assert watch_ids.isdisjoint({f["rule_id"] for f in report["findings"]})
    for row in report["state_watch"]:
        assert row["provenance"] == "dataset"
    assert any(
        e["action"] == "state_watch" and e["role"] == "system" for e in report["events"]
    )


def test_out_of_coverage_site_completes_with_coverage(tmp_path):
    from app.data import DuckDbHarness, FallbackHarness
    from app.evidence import EvidenceFetcher
    from app.geo import Jurisdiction
    from app.seed import register_seed

    loudoun = Jurisdiction(
        matched_address="1 HARRISON ST SE, LEESBURG, VA, 20175",
        lat=39.11,
        lon=-77.55,
        state="VA",
        state_fips="51",
        county_name="Loudoun County",
        county_fips="51107",
        place=None,
        county_subdivision=None,
        utilities=[],
        nerc_regions=[],
        iso="unknown",
        iso_candidates=[],
    )
    draft = json.dumps(
        {
            "verdict": "conditional",
            "why": "Title V applies.",
            "grades": {"federal-title-v-major-source": "major"},
        }
    )
    router = ScriptedRouter(adjudicator=[draft], critic=["[]"])
    harness = FallbackHarness(DuckDbHarness(), DuckDbHarness())
    register_seed(harness.primary)
    fetcher = EvidenceFetcher(
        client=httpx.Client(transport=httpx.MockTransport(serve)),
        cache_dir=tmp_path / "src",
    )
    orch = Orchestrator(
        FakeResolver(loudoun), harness, router, fetcher,
        runs_dir=tmp_path / "runs", as_of=date(2026, 10, 25),
    )
    report = orch.run("1 Harrison St SE, Leesburg, VA 20175", mw=300)
    assert report["coverage"] == {"state_rules": [], "county_sources": []}
    assert report["explanation"]["coverage_note"] == (
        "State and grid rules are not modelled for VA; "
        "federal rule and county dataset only."
    )
    lamps = report["explanation"]["layer_status"]
    # Loudoun County has a dataset moratorium row but no verified facts, so the
    # county finding is honestly unknown; state and grid layers are un-modelled.
    assert lamps["county"]["lamp"] == "unknown"
    assert lamps["state"]["lamp"] == "not_modelled"
    assert lamps["iso_rto"]["lamp"] == "not_modelled"


def test_case_only_other_differences_give_zero_conflicts(orchestrator_factory):
    long_quote = "a temporary, twelve (12) month moratorium on the acceptance"
    facts = [
        {"field": "other", "value": "Acceptance", "url": RELEASE_URL, "quote": long_quote},
        {"field": "other", "value": "acceptance",
         "url": RELEASE_URL, "quote": "temporary, twelve (12) month"},
    ]
    router = ScriptedRouter(
        planner=[PLAN],
        county_investigator=[facts_reply(facts)],
        adjudicator=[DRAFT_NO_GO],
        critic=["[]"],
    )
    report = orchestrator_factory(router).run("addr", mw=300)
    assert [e for e in report["events"] if e["action"] == "conflict"] == []


def test_quote_recompute_corrects_model_duration(orchestrator_factory):
    """(A) RED: model writes duration '12' but the verified quote says 12 months."""
    from app.explain import enrich

    fact = {
        "field": "duration",
        "value": "12",
        "url": RELEASE_URL,
        "quote": (
            "On June 30, 2026, the Washington County Board of County Commissioners "
            "approved a temporary, twelve (12) month moratorium on the acceptance"
        ),
    }
    router = ScriptedRouter(
        planner=[PLAN],
        county_investigator=[facts_reply([fact, GOOD_FACTS[2]])],
        adjudicator=[DRAFT_NO_GO],
        critic=["[]"],
    )
    report = orchestrator_factory(router).run("addr", mw=300)
    finding = next(f for f in report["findings"] if f["rule_id"] == "md-washington-county-2026")
    assert finding["parameters"]["duration_days"] == 365
    assert finding["computed"]["expires"] == "2027-06-30"
    events = [e for e in report["events"] if e["action"] == "value_corrected_from_quote"]
    assert len(events) == 1
    assert events[0]["detail"]["model_value"] == 12
    assert events[0]["detail"]["quote_value"] == 365
    catches = enrich(report)["explanation"]["catches"]
    assert "Verifier recomputed duration from the quoted text: 12 → 365 days" in [
        c["text"] for c in catches
    ]


def test_quote_recompute_leaves_matching_values_alone(orchestrator_factory):
    """(A) companion: values that agree with their quotes emit no correction."""
    router = ScriptedRouter(
        planner=[PLAN],
        county_investigator=[facts_reply(GOOD_FACTS)],
        adjudicator=[DRAFT_NO_GO],
        critic=["[]"],
    )
    report = orchestrator_factory(router, jurisdiction=WASHINGTON_UNINCORPORATED).run(
        "addr", mw=300
    )
    assert report["verdict"] == "no-go"
    assert [e for e in report["events"] if e["action"] == "value_corrected_from_quote"] == []


def test_county_countywide_unknown_inside_city(orchestrator_factory):
    """(B) RED: a countywide county pause must not silently reach an incorporated city."""
    router = ScriptedRouter(
        planner=[PLAN],
        county_investigator=[facts_reply(GOOD_FACTS)],
        adjudicator=[DRAFT_NO_GO],
        critic=["[]"],
    )
    report = orchestrator_factory(router).run("addr", mw=300)
    finding = next(f for f in report["findings"] if f["rule_id"] == "md-washington-county-2026")
    assert finding["applies"] == "unknown"
    assert "Hagerstown city" in finding["reason"]


def test_countywide_applies_unincorporated_site(orchestrator_factory):
    """(B) Washington unincorporated: the county pause still applies."""
    router = ScriptedRouter(
        planner=[PLAN],
        county_investigator=[facts_reply(GOOD_FACTS)],
        adjudicator=[DRAFT_NO_GO],
        critic=["[]"],
    )
    report = orchestrator_factory(router, jurisdiction=WASHINGTON_UNINCORPORATED).run(
        "addr", mw=300
    )
    finding = next(f for f in report["findings"] if f["rule_id"] == "md-washington-county-2026")
    assert finding["applies"] == "yes"
    assert report["verdict"] == "no-go"


def test_parse_fact_scope_all_jurisdictions():
    """(B) RED: scope text naming municipalities parses to all_jurisdictions."""
    from app.orchestrator import parse_fact

    assert parse_fact("scope", "the pause applies to all areas including municipalities") == (
        "all_jurisdictions"
    )
    assert parse_fact("scope", "applies in incorporated towns") == "all_jurisdictions"
    assert parse_fact("scope", "all jurisdictions within the county") == "all_jurisdictions"
    assert parse_fact("scope", "countywide") == "countywide"


def test_all_jurisdictions_reaches_city_but_countywide_does_not():
    """(B) RED: unit-level county-vs-city scope semantics."""
    from app.applicability import Project, moratorium_applies

    as_of = date(2026, 10, 25)
    base = {"effective": "2026-06-30", "duration_days": 365}
    city = Project(mw=300, as_of=as_of, incorporated=True)
    county_layer = "county"
    assert (
        moratorium_applies(city, {**base, "scope": "all_jurisdictions"}, layer=county_layer)[
            "applies"
        ]
        == "yes"
    )
    assert (
        moratorium_applies(city, {**base, "scope": "countywide"}, layer=county_layer)["applies"]
        == "unknown"
    )
    rural = Project(mw=300, as_of=as_of, incorporated=False)
    assert (
        moratorium_applies(rural, {**base, "scope": "countywide"}, layer=county_layer)["applies"]
        == "yes"
    )
    unknown_place = Project(mw=300, as_of=as_of, incorporated=None)
    assert (
        moratorium_applies(
            unknown_place, {**base, "scope": "countywide"}, layer=county_layer
        )["applies"]
        == "unknown"
    )
