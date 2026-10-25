"""Deterministic applicability checks. Threshold math, date windows and
exemptions are decided here in code, never by a model. Every result is
{applies: yes|no|unknown, reason, computed} and states its assumptions.
"""

import math
from dataclasses import dataclass, field
from datetime import date, timedelta

GENSET_KW = 2500
EMERGENCY_HOURS = 500
NOX_G_PER_KWH = 6.4
GRAMS_PER_SHORT_TON = 907_184.74
TITLE_V_MAJOR_TPY = 100


@dataclass
class Project:
    mw: float | None = None
    as_of: date = field(default_factory=date.today)
    incorporated: bool | None = None
    permits_submitted: bool | None = None


def _result(applies: str, reason: str, **computed) -> dict:
    return {"applies": applies, "reason": reason, "computed": computed}


def mw_threshold(project: Project, threshold_mw: float, label: str, inclusive: bool = True) -> dict:
    if project.mw is None:
        return _result("unknown", f"project size unknown; {label} starts at {threshold_mw} MW")
    over = project.mw >= threshold_mw if inclusive else project.mw > threshold_mw
    op = ">=" if inclusive else ">"
    word = "meets" if over else "is below"
    return _result(
        "yes" if over else "no",
        f"{project.mw:g} MW {word} the {label} threshold ({op} {threshold_mw:g} MW)",
        margin_mw=project.mw - threshold_mw,
    )


def moratorium_applies(project: Project, m: dict, layer: str | None = None,
                       place: str | None = None) -> dict:
    """m: {effective: ISO date, duration_days, scope: countywide|unincorporated,
    exempt_if_permits_submitted}. layer/place gate the county-vs-city boundary:
    a countywide county pause does not silently reach an incorporated city."""
    if not m.get("effective"):
        return _result("unknown", "effective date not established")
    start = date.fromisoformat(m["effective"])
    days = m.get("duration_days")
    end = start + timedelta(days=days) if days else None
    window = {"effective": start.isoformat(), "expires": end.isoformat() if end else None}
    if project.as_of < start:
        return _result("no", f"not yet in effect on {project.as_of}", **window)
    if end and project.as_of >= end:
        return _result("no", f"expired on {end}", **window)
    if m.get("scope") not in {"countywide", "unincorporated", "all_jurisdictions"}:
        return _result("unknown", "geographic scope (countywide or unincorporated) not established",
                       **window)  # fmt: skip
    if m.get("scope") == "unincorporated":
        if project.incorporated is None:
            return _result("unknown", "applies only to unincorporated areas; site status unknown",
                           **window)  # fmt: skip
        if project.incorporated:
            return _result("no", "applies only to unincorporated areas; site is inside a city",
                           **window)  # fmt: skip
    if layer == "county" and m.get("scope") == "countywide" and project.incorporated is not False:
        # A "countywide" county pause does not silently reach an incorporated
        # city; only explicit municipality coverage ("all_jurisdictions") does.
        inside = f"the site is inside {place}" if place else "the site may be inside a city"
        return _result(
            "unknown",
            f"county ordinance; {inside}, which has its own zoning — "
            "confirm the pause reaches city limits",
            **window,
        )
    if m.get("exempt_if_permits_submitted"):
        if project.permits_submitted is None:
            return _result("unknown", "projects that already submitted permits are exempt; "
                           "permit status unknown", **window)  # fmt: skip
        if project.permits_submitted:
            return _result("no", "exempt: permits were submitted before the moratorium", **window)
    return _result(
        "yes", f"in effect on {project.as_of} and the site is within its scope", **window
    )


def backup_generator_estimate(project: Project) -> dict:
    units = math.ceil(project.mw * 1000 / GENSET_KW) + 1
    return {
        "units": units,
        "unit_kw": GENSET_KW,
        "total_kw": units * GENSET_KW,
        "assumption": f"N+1 diesel gensets of {GENSET_KW} kW sized to the full IT load",
    }


def title_v_major_source(project: Project) -> dict:
    """Potential to emit NOx from emergency gensets vs the 100 tpy major-source line."""
    if project.mw is None:
        return _result("unknown", "project size unknown; cannot estimate generator emissions")
    gens = backup_generator_estimate(project)
    nox_tpy = gens["total_kw"] * EMERGENCY_HOURS * NOX_G_PER_KWH / GRAMS_PER_SHORT_TON
    major = nox_tpy >= TITLE_V_MAJOR_TPY
    return _result(
        "yes" if major else "no",
        f"estimated NOx potential to emit {nox_tpy:,.0f} tpy "
        f"{'meets' if major else 'is below'} the {TITLE_V_MAJOR_TPY} tpy major-source threshold",
        nox_tpy=nox_tpy,
        generators=gens,
        assumptions=(
            f"{EMERGENCY_HOURS} h/yr emergency-engine PTE, "
            f"{NOX_G_PER_KWH} g/kWh NOx (Tier 2 diesel)"
        ),
    )
