import pytest

from app.applicability import Project
from app.layers import evaluate_rule, load_county_sources, load_rules

REQUIRED = {"id", "layer", "title", "scope", "check", "quote", "source_url", "as_of", "status"}
ALLOWED_STATUS = {"final", "proposed", "pending", "in_force"}


def test_every_rule_has_source_quote_as_of_and_status():
    rules = load_rules()
    assert rules
    for r in rules:
        assert REQUIRED <= r.keys(), r["id"]
        assert r["status"] in ALLOWED_STATUS
        assert r["source_url"].startswith("https://") and len(r["quote"]) > 20


def test_county_sources_point_at_https_urls():
    for mid, sources in load_county_sources().items():
        assert sources and all(s["url"].startswith("https://") for s in sources), mid


def test_scope_filter_and_checks():
    sb6 = next(r for r in load_rules() if r["id"] == "tx-sb6-large-load")
    assert evaluate_rule(sb6, Project(mw=300), {"iso": "PJM"}) is None
    assert evaluate_rule(sb6, Project(mw=75), {"iso": "ERCOT"})["applies"] == "no"
    assert evaluate_rule(sb6, Project(mw=75.1), {"iso": "ERCOT"})["applies"] == "yes"
    tv = next(r for r in load_rules() if r["id"] == "federal-title-v-major-source")
    assert evaluate_rule(tv, Project(mw=300), {"iso": "PJM"})["applies"] == "yes"


def test_tx_audit_rule_scope():
    audit = next(r for r in load_rules() if r["id"] == "tx-ercot-data-center-audit-2026")
    assert audit["layer"] == "state"
    assert evaluate_rule(audit, Project(mw=300), {"iso": "ERCOT"})["applies"] == "yes"
    assert evaluate_rule(audit, Project(mw=70), {"iso": "ERCOT"})["applies"] == "no"
    assert evaluate_rule(audit, Project(mw=300), {"iso": "PJM"}) is None


@pytest.mark.live
def test_live_every_curated_quote_is_verbatim_in_its_source():
    from app.evidence import EvidenceFetcher

    f = EvidenceFetcher()
    for r in load_rules():
        assert f.verify(r["quote"], r["source_url"])["status"] == "verified", r["id"]
