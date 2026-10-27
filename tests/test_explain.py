import copy
import json
from pathlib import Path

from fastapi.testclient import TestClient

from app.config import Settings
from app.explain import enrich
from app.main import create_app

SAMPLES = Path(__file__).resolve().parent.parent / "samples"


def load(name):
    return json.loads((SAMPLES / f"{name}.json").read_text())


def test_washington_sample_structure():
    # Live re-records vary by model; samples assert structure only.
    out = enrich(load("md-washington-county-unincorporated"))
    assert out["verdict"] in {"go", "conditional", "no-go", "needs_confirmation"}
    for key in ("site", "coverage", "state_watch", "explanation"):
        assert key in out
    assert out["jurisdiction"]["lat"] and out["jurisdiction"]["lon"]
    explanation = out["explanation"]
    for key in ("headline", "decisive", "flips", "sensitivity", "catches",
                "layer_status", "stats", "coverage_note"):
        assert key in explanation
    assert explanation["headline"]
    for d in explanation["decisive"]:
        assert {"rule_id", "title", "layer", "grade", "fact", "computation",
                "result"} <= set(d)
        assert d["fact"]["quote"] and d["fact"]["url"]
    for f in explanation["flips"]:
        assert {"rule_id", "change", "effect", "estimated_verdict"} <= set(f)
    for s in explanation["sensitivity"]:
        assert {"rule_id", "field", "readings", "holds"} <= set(s)
        for r in s["readings"]:
            assert {"value", "quote", "url", "applies"} <= set(r)
            assert str(r["value"]).strip().lower() not in {
                "", "none", "null", "n/a", "unknown", "not stated",
            }
    assert set(explanation["layer_status"]) == {"federal", "iso_rto", "state",
                                                "county", "city"}
    for finding in out["findings"]:
        for e in finding["evidence"]:
            assert e["url"]


def test_tucson_unincorporated_flip():
    out = enrich(load("az-tucson-pima"))
    flips = [
        f for f in out["explanation"]["flips"] if f["rule_id"] == "az-pima-county-2026"
    ]
    assert flips, "unincorporated flip missing"
    assert any("unincorporated" in f["change"] for f in flips)
    assert out["explanation"]["layer_status"]["county"]["lamp"] == "clear"


def test_abilene_threshold_and_titlev_flips():
    from app.applicability import Project, title_v_major_source

    out = enrich(load("tx-abilene-ercot"))
    sb6 = [f for f in out["explanation"]["flips"] if f["rule_id"] == "tx-sb6-large-load"]
    assert sb6 and any("75" in f["change"] for f in sb6)
    tv = [
        f for f in out["explanation"]["flips"]
        if f["rule_id"] == "federal-title-v-major-source"
    ]
    assert tv
    import re

    m = re.search(r"at (\d+) MW", tv[0]["change"])
    assert m, tv[0]["change"]
    x = int(m.group(1))
    assert title_v_major_source(Project(mw=float(x)))["applies"] == "no"
    assert title_v_major_source(Project(mw=float(x + 1)))["applies"] == "yes"


def _synthetic_conflict_report(as_of):
    finding = {
        "rule_id": "test-moratorium",
        "layer": "county",
        "title": "Test moratorium",
        "applies": "yes",
        "reason": "in effect",
        "grade": "major",
        "computed": {"effective": "2026-06-30", "expires": "2027-06-30"},
        "parameters": {
            "effective": "2026-06-30",
            "duration_days": 365,
            "scope": "countywide",
        },
        "evidence": [
            {
                "field": "duration_days",
                "quote": "twelve months",
                "verification": "verified",
                "provenance": "county_source",
                "url": "https://example.com/a",
            }
        ],
    }
    event = {
        "round": 1,
        "role": "evidence_verifier",
        "action": "conflict",
        "detail": {
            "rule": "test-moratorium",
            "field": "duration_days",
            "value": 365,
            "other_county_source": 182,
            "quote": "twelve months",
            "url": "https://example.com/a",
            "other_quote": "six months",
            "other_url": "https://example.com/b",
        },
        "at": f"{as_of}T00:00:00+00:00",
    }
    return {
        "run_id": "synthetic",
        "project": {"address": "x", "mw": 300.0, "permits_submitted": None},
        "jurisdiction": {"place": None},
        "site": {"as_of": as_of},
        "verdict": "conditional",
        "findings": [finding],
        "needs_confirmation": [],
        "conflicts": [],
        "events": [event],
        "model_trace": [],
        "data_trace": [],
        "markovian_runs": [],
        "guard_notes": [],
        "state_watch": [],
    }


def test_synthetic_duration_conflict_holds():
    early = enrich(_synthetic_conflict_report("2026-10-25"))["explanation"]["sensitivity"]
    assert len(early) == 1 and early[0]["holds"] is True
    late = enrich(_synthetic_conflict_report("2027-01-15"))["explanation"]["sensitivity"]
    assert len(late) == 1 and late[0]["holds"] is False


def test_idempotent_and_input_unmutated():
    report = load("md-washington-county-unincorporated")
    frozen = copy.deepcopy(report)
    once = enrich(report)
    assert report == frozen
    assert once["verdict"] == report["verdict"]
    assert enrich(once) == once


def test_api_samples_have_explanation_and_latlon(tmp_path):
    (tmp_path / "az-tucson-pima.json").write_text(
        (SAMPLES / "az-tucson-pima.json").read_text()
    )
    client = TestClient(create_app(Settings(), samples_dir=tmp_path))
    rows = client.get("/samples").json()
    assert rows and all(
        {"lat", "lon", "headline", "county"} <= set(r) for r in rows
    )
    sample = client.get("/samples/az-tucson-pima").json()
    assert sample["explanation"]["headline"]


def test_zero_findings_fallback_headline():
    report = {
        "run_id": "empty",
        "project": {"address": "x", "mw": 100.0, "permits_submitted": None},
        "jurisdiction": {"place": None},
        "site": {"as_of": "2026-10-25"},
        "verdict": "go",
        "findings": [],
        "needs_confirmation": [],
        "conflicts": [],
        "events": [],
        "model_trace": [],
        "data_trace": [],
        "markovian_runs": [],
        "guard_notes": [],
        "state_watch": [],
    }
    explanation = enrich(report)["explanation"]
    assert explanation["decisive"] == []
    assert explanation["flips"] == []
    assert explanation["sensitivity"] == []
    assert (
        explanation["headline"] == "Go: no fatal or major rule applies to this site."
    )


def test_as_of_falls_back_to_today():
    from datetime import date

    out = enrich({})
    assert out["explanation"]["site"]["as_of"] == date.today().isoformat()
