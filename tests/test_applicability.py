from datetime import date

import pytest

from app.applicability import (
    Project,
    backup_generator_estimate,
    moratorium_applies,
    mw_threshold,
    title_v_major_source,
)


@pytest.mark.parametrize(
    "mw,expected", [(74.9, "no"), (75, "yes"), (75.1, "yes"), (None, "unknown")]
)
def test_mw_threshold_boundaries_inclusive(mw, expected):
    r = mw_threshold(Project(mw=mw), 75, "TX SB 6 large load")
    assert r["applies"] == expected
    if mw is not None:
        assert r["computed"]["margin_mw"] == pytest.approx(mw - 75)


def test_mw_threshold_strict_greater_than():
    assert mw_threshold(Project(mw=100), 100, "x", inclusive=False)["applies"] == "no"


WASH = {
    "effective": "2026-06-30",
    "duration_days": 365,
    "scope": "countywide",
    "exempt_if_permits_submitted": False,
}
PIMA = {
    "effective": "2026-09-22",
    "duration_days": 120,
    "scope": "unincorporated",
    "exempt_if_permits_submitted": True,
}


def test_countywide_moratorium_in_window_applies():
    r = moratorium_applies(Project(mw=300, as_of=date(2026, 10, 25), incorporated=True), WASH)
    assert r["applies"] == "yes" and r["computed"]["expires"] == "2027-06-30"


def test_moratorium_date_edges():
    assert moratorium_applies(Project(as_of=date(2026, 6, 29)), WASH)["applies"] == "no"
    assert moratorium_applies(Project(as_of=date(2026, 6, 30)), WASH)["applies"] == "yes"
    assert moratorium_applies(Project(as_of=date(2027, 6, 29)), WASH)["applies"] == "yes"
    assert moratorium_applies(Project(as_of=date(2027, 6, 30)), WASH)["applies"] == "no"


def test_unincorporated_scope_excludes_incorporated_city_sites():
    r = moratorium_applies(Project(as_of=date(2026, 10, 25), incorporated=True), PIMA)
    assert r["applies"] == "no" and "unincorporated" in r["reason"]
    p = Project(as_of=date(2026, 10, 25), incorporated=False, permits_submitted=False)
    assert moratorium_applies(p, PIMA)["applies"] == "yes"


def test_unknown_incorporation_or_permits_yields_unknown():
    assert moratorium_applies(Project(as_of=date(2026, 10, 25)), PIMA)["applies"] == "unknown"
    p = Project(as_of=date(2026, 10, 25), incorporated=False, permits_submitted=None)
    assert moratorium_applies(p, PIMA)["applies"] == "unknown"


def test_permits_already_submitted_exemption():
    p = Project(as_of=date(2026, 10, 25), incorporated=False, permits_submitted=True)
    r = moratorium_applies(p, PIMA)
    assert r["applies"] == "no" and "exempt" in r["reason"]


def test_missing_effective_date_is_unknown():
    assert (
        moratorium_applies(Project(as_of=date(2026, 10, 25)), {"scope": "countywide"})["applies"]
        == "unknown"
    )


def test_backup_generator_estimate_is_n_plus_one_and_labeled_as_assumption():
    est = backup_generator_estimate(Project(mw=300))
    assert est["units"] == 121 and est["unit_kw"] == 2500
    assert est["total_kw"] == 302_500
    assert "assumption" in est


def test_title_v_major_source_from_emergency_generator_pte():
    r = title_v_major_source(Project(mw=300))
    assert r["applies"] == "yes"
    assert r["computed"]["nox_tpy"] == pytest.approx(302_500 * 500 * 6.4 / 907_184.74, rel=1e-6)
    small = title_v_major_source(Project(mw=10))
    assert small["applies"] == "no"
    assert title_v_major_source(Project(mw=None))["applies"] == "unknown"
