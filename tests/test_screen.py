import json
from pathlib import Path

import pytest

from app.data import DuckDbHarness, FallbackHarness
from app.geo import Jurisdiction
from app.llm import Completion
from app.screen import Screener, parse_json_object
from app.seed import MORATORIA_CSV, register_seed

WASHINGTON = Jurisdiction(
    matched_address="100 W WASHINGTON ST, HAGERSTOWN, MD, 21740",
    lat=39.64,
    lon=-77.72,
    state="MD",
    state_fips="24",
    county_name="Washington County",
    county_fips="24043",
    place="Hagerstown city",
    county_subdivision=None,
    utilities=[{"name": "The Potomac Edison Company", "nerc_region": "RFC", "rtos": "PJM"}],
    nerc_regions=["RFC"],
    iso="PJM",
    iso_candidates=["PJM"],
)
TAYLOR = Jurisdiction(
    matched_address="555 WALNUT ST, ABILENE, TX, 79601",
    lat=32.45,
    lon=-99.73,
    state="TX",
    state_fips="48",
    county_name="Taylor County",
    county_fips="48441",
    place="Abilene city",
    county_subdivision=None,
    iso="ERCOT",
)


class FakeResolver:
    def __init__(self, j):
        self.j = j

    def resolve(self, address):
        return self.j


class FakeRouter:
    def __init__(self, text):
        self.text = text
        self.calls = []
        self.trace = []

    def generate(self, step, messages, role=None, **kw):
        self.calls.append((step, role, messages))
        self.trace.append({"step": step, "role": role, "model": "nvidia/x", "receipt_id": "r1"})
        return Completion(self.text, "nvidia/x", "r1", False)


@pytest.fixture
def harness():
    h = FallbackHarness(DuckDbHarness(), DuckDbHarness())
    register_seed(h.primary)
    return h


def verdict_json(verdict="no-go"):
    return json.dumps(
        {
            "verdict": verdict,
            "why": "An active county moratorium pauses data center approvals.",
            "findings": [
                {
                    "evidence_id": "md-washington-county-2026",
                    "grade": "fatal",
                    "applies": "yes",
                    "reasoning": "The site is in Washington County, where approvals are paused.",
                }
            ],
        }
    )


def test_seed_registers_moratoria_with_expected_counts(harness):
    rows = harness.query(
        "SELECT state_abbrev, count(*) AS n FROM SITEWHY.moratoria "
        "WHERE state_abbrev IN ('MD','TX','AZ') GROUP BY 1 ORDER BY 1"
    )
    assert rows == [
        {"state_abbrev": "AZ", "n": "1"},
        {"state_abbrev": "MD", "n": "24"},
        {"state_abbrev": "TX", "n": "11"},
    ]
    assert MORATORIA_CSV.is_file()


def test_screen_finds_county_moratorium_and_cites_dataset(harness):
    router = FakeRouter(verdict_json())
    report = Screener(FakeResolver(WASHINGTON), harness, router).screen("addr", mw=300)
    ev = report["evidence"]
    assert [e["id"] for e in ev] == ["md-washington-county-2026"]
    assert ev[0]["layer"] == "county" and "ORD-2026-12" in ev[0]["quote"]
    assert ev[0]["source"].startswith("Moratorium Nation")
    assert report["verdict"] == "no-go"
    assert report["findings"][0]["evidence"]["id"] == "md-washington-county-2026"
    assert report["model_trace"][0]["model"] == "nvidia/x"
    assert report["data_trace"][0]["backend"] == "duckdb"
    step, role, messages = router.calls[0]
    assert step == "synthesize" and role == "adjudicator"
    assert (
        "300" in messages[-1]["content"] and "md-washington-county-2026" in messages[-1]["content"]
    )


def test_screen_with_no_local_evidence_still_returns_report(harness):
    router = FakeRouter(
        json.dumps({"verdict": "go", "why": "No local pause found.", "findings": []})
    )
    report = Screener(FakeResolver(TAYLOR), harness, router).screen("addr", mw=200)
    assert report["evidence"] == [] and report["verdict"] == "go"


def test_findings_citing_unknown_evidence_are_dropped(harness):
    bad = json.loads(verdict_json())
    bad["findings"][0]["evidence_id"] = "made-up-id"
    report = Screener(FakeResolver(WASHINGTON), harness, FakeRouter(json.dumps(bad))).screen(
        "addr", mw=300
    )
    assert report["findings"] == []
    assert report["dropped_findings"] == ["made-up-id"]


def test_unparseable_model_output_becomes_needs_confirmation(harness):
    report = Screener(FakeResolver(WASHINGTON), harness, FakeRouter("not json")).screen(
        "addr", mw=300
    )
    assert report["verdict"] == "needs_confirmation"


def test_parse_json_object_tolerates_fences_and_prose():
    assert parse_json_object('```json\n{"a": 1}\n```') == {"a": 1}
    assert parse_json_object('Here you go: {"a": {"b": 2}} done') == {"a": {"b": 2}}
    assert parse_json_object("nope") is None


@pytest.mark.live
def test_live_screen_washington_county():
    from app.config import load_settings
    from app.data import ZetarisHarness
    from app.geo import Resolver
    from app.llm import ModelRouter

    s = load_settings()
    h = FallbackHarness(ZetarisHarness(s), DuckDbHarness())
    register_seed(h.primary)
    register_seed(h.fallback)
    router = ModelRouter(s, cache_dir=Path("data/llm_cache"))
    report = Screener(Resolver(), h, router).screen(
        "100 W Washington St, Hagerstown, MD 21740", mw=300
    )
    assert report["jurisdiction"]["county_fips"] == "24043"
    assert report["data_trace"][0]["backend"] == "zetaris"
    assert any(f["evidence"]["id"] == "md-washington-county-2026" for f in report["findings"])
    assert report["model_trace"][0]["model"].startswith("nvidia/nemotron")


def test_screen_endpoint_validates_and_returns_report(harness):
    from fastapi.testclient import TestClient

    from app.config import Settings
    from app.main import create_app

    screener = Screener(FakeResolver(WASHINGTON), harness, FakeRouter(verdict_json()))
    client = TestClient(
        create_app(Settings(), resolver=FakeResolver(WASHINGTON), screener=screener)
    )
    ok = client.post("/screen", json={"address": "x", "mw": 300})
    assert ok.status_code == 200 and ok.json()["verdict"] == "no-go"
    assert client.post("/screen", json={"address": "x", "mw": -5}).status_code == 422
