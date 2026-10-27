"""Deterministic explanation layer: decisive chain, flips, sensitivity, catches.

Pure code over a run report's own data. No model calls, never changes the
verdict. `enrich` deep-copies its input, so it is idempotent and never mutates.
"""

import copy
from datetime import date, datetime

from app.applicability import Project, moratorium_applies, mw_threshold, title_v_major_source
from app.layers import load_county_sources, load_rules

LAYER_ORDER = ("federal", "iso_rto", "state", "county", "city")
LAYER_NAMES = {
    "federal": "Federal",
    "iso_rto": "Grid/ISO",
    "state": "State",
    "county": "County",
    "city": "City",
}
VERDICT_WORDS = {
    "go": "Go",
    "conditional": "Conditional",
    "no-go": "No-go",
    "needs_confirmation": "Needs confirmation",
}
FALLBACK_HEADLINE = "Go: no fatal or major rule applies to this site."
TITLE_V_RULE = "federal-title-v-major-source"


def _orchestrator_helpers():
    from app.orchestrator import DECISION_FIELDS, NULL_VALUES, canonical_field, parse_fact

    return DECISION_FIELDS, NULL_VALUES, canonical_field, parse_fact


def _as_of(report) -> str:
    """Report timestamp, else today (outputs embedding it are date-dependent)."""
    for e in report.get("events") or []:
        if e.get("action") == "resolved" and isinstance(e.get("detail"), dict):
            as_of = e["detail"].get("as_of")
            if as_of:
                return as_of
    site = report.get("site") or {}
    if site.get("as_of"):
        return site["as_of"]
    return date.today().isoformat()


def _project(report, as_of: str) -> Project:
    project = report.get("project") or {}
    jurisdiction = report.get("jurisdiction") or {}
    return Project(
        mw=project.get("mw"),
        as_of=date.fromisoformat(as_of),
        incorporated=jurisdiction.get("place") is not None,
        permits_submitted=project.get("permits_submitted"),
    )


def _choose_fact(evidence):
    _, _, canonical_field, _ = _orchestrator_helpers()
    tiers = []
    for e in evidence or []:
        decision = canonical_field(e.get("field", "")) in _decision_fields()
        verified = e.get("verification") == "verified"
        prov = e.get("provenance")
        if prov == "county_source" and verified and decision:
            tier = 0
        elif prov == "county_source" and verified:
            tier = 1
        elif prov == "curated" and verified:
            tier = 2
        elif prov == "dataset":
            tier = 3
        else:
            tier = 4
        tiers.append(tier)
    best = min(tiers) if tiers else 4
    idx = tiers.index(best)
    fact = evidence[idx]
    return {
        "field": fact.get("field"),
        "quote": fact.get("quote"),
        "url": fact.get("url"),
        "verification": fact.get("verification"),
        "provenance": fact.get("provenance"),
    }, max(len(evidence) - 1, 0)


def _decision_fields():
    fields, _, _, _ = _orchestrator_helpers()
    return fields


def _computation(finding, as_of: str) -> str:
    computed = finding.get("computed") or {}
    if "nox_tpy" in computed:
        text = f"estimated NOx {computed['nox_tpy']:,.0f} tpy \u2265 100 tpy"
        if computed.get("assumptions"):
            text += f" ({computed['assumptions']})"
        return text
    if "effective" in computed:
        eff, exp = computed.get("effective"), computed.get("expires")
        if exp:
            return f"in effect {eff} \u2192 {exp}; as of {as_of}"
        return f"in effect since {eff} (no expiry recorded); as of {as_of}"
    return finding.get("reason", "")


def _result_text(applies: str) -> str:
    return {
        "yes": "Applies to this site",
        "no": "Does not apply to this site",
    }.get(applies, "Unknown whether it applies")


def _decisive(findings, as_of: str):
    decisive = [
        f for f in findings
        if f.get("grade") in {"fatal", "major"} and f.get("applies") == "yes"
    ]

    def order(f):
        try:
            layer = LAYER_ORDER.index(f.get("layer"))
        except ValueError:
            layer = len(LAYER_ORDER)
        return (0 if f.get("grade") == "fatal" else 1, layer)

    out = []
    for f in sorted(decisive, key=order):
        fact, more = _choose_fact(f.get("evidence") or [])
        out.append({
            "rule_id": f.get("rule_id"),
            "title": f.get("title"),
            "layer": f.get("layer"),
            "grade": f.get("grade"),
            "fact": fact,
            "more_sources": more,
            "computation": _computation(f, as_of),
            "result": _result_text(f.get("applies")),
        })
    return out


def _estimated_verdict(rule_id: str, decisive) -> str:
    grades = [d["grade"] for d in decisive if d["rule_id"] != rule_id]
    if "fatal" in grades:
        return "no-go"
    if "major" in grades:
        return "conditional"
    return "go"


def _flip(rule_id, change: str, old: str, new: str, decisive) -> dict:
    return {
        "rule_id": rule_id,
        "change": change,
        "effect": f"applies {old} \u2192 {new}",
        "estimated_verdict": _estimated_verdict(rule_id, decisive),
    }


def _moratorium_flips(finding, project: Project, decisive, place=None):
    from dataclasses import replace

    params = finding.get("parameters") or {}
    if not any(k in params for k in ("effective", "duration_days", "scope")):
        return []
    layer = finding.get("layer")
    out = []
    old = finding.get("applies")
    if params.get("scope") == "unincorporated" and project.incorporated is not None:
        toggled = replace(project, incorporated=not project.incorporated)
        new = moratorium_applies(toggled, params, layer=layer, place=place)["applies"]
        if new != old:
            where = (
                "outside city limits (unincorporated)"
                if project.incorporated else "inside city limits"
            )
            out.append(_flip(
                finding["rule_id"], f"if the site were {where}",
                old, new, decisive,
            ))
    if params.get("exempt_if_permits_submitted") is True and not project.permits_submitted:
        permitted = replace(project, permits_submitted=True)
        new = moratorium_applies(permitted, params, layer=layer, place=place)["applies"]
        if new != old:
            out.append(_flip(
                finding["rule_id"], "if permits had been submitted before the moratorium",
                old, new, decisive,
            ))
    expires = (finding.get("computed") or {}).get("expires")
    if expires:
        try:
            later = replace(project, as_of=date.fromisoformat(expires))
        except ValueError:
            later = None
        if later is not None:
            new = moratorium_applies(later, params, layer=layer, place=place)["applies"]
            if new != old:
                out.append(_flip(
                    finding["rule_id"], f"after the moratorium expires ({expires})",
                    old, new, decisive,
                ))
    return out


def _threshold_flip_mw(current_applies: str, threshold: float, inclusive: bool,
                       label: str, project: Project) -> float | None:
    def applies_at(mw: float) -> str:
        return mw_threshold(Project(mw=mw), threshold, label, inclusive)["applies"]

    if applies_at(threshold) != current_applies:
        return threshold
    step = 1.0 if inclusive else 1.0
    candidate = threshold - step if current_applies == "yes" else threshold + step
    if applies_at(candidate) != current_applies:
        return candidate
    return None


def _rule_flips(finding, project: Project, decisive, rules_by_id, place=None):
    old = finding.get("applies")
    if old not in {"yes", "no"}:
        return []
    rule_id = finding.get("rule_id")
    if finding.get("parameters") and any(
        k in finding["parameters"] for k in ("effective", "duration_days", "scope")
    ):
        return _moratorium_flips(finding, project, decisive, place=place)
    computed = finding.get("computed") or {}
    if rule_id == TITLE_V_RULE or "nox_tpy" in computed:
        mw = project.mw
        if mw is None:
            return []
        if old == "yes":
            x = int(mw)
            while x >= 0 and title_v_major_source(Project(mw=float(x)))["applies"] != "no":
                x -= 1
            if x < 0:
                return []
        else:
            x = int(mw)
            while title_v_major_source(Project(mw=float(x + 1)))["applies"] == "no":
                x += 1
                if x > (mw or 0) + 10000:
                    return []
        return [_flip(
            rule_id,
            f"at {x} MW instead of {mw:g} MW ({x + 1} MW would trigger it)",
            old, "no" if old == "yes" else "yes", decisive,
        )]
    if "margin_mw" in computed:
        rule = (rules_by_id or {}).get(rule_id) or {}
        check = rule.get("check") or {}
        if not isinstance(check, dict) or "mw_threshold" not in check:
            return []
        flip_mw = _threshold_flip_mw(
            old, check["mw_threshold"], check.get("inclusive", True),
            check.get("label", "threshold"), project,
        )
        if flip_mw is None or project.mw is None:
            return []
        return [_flip(
            rule_id, f"at {flip_mw:g} MW instead of {project.mw:g} MW",
            old, "yes" if old == "no" else "no", decisive,
        )]
    return []


def _sensitivity(report, findings, project: Project):
    _, null_values, canonical_field, parse_fact = _orchestrator_helpers()
    jurisdiction = report.get("jurisdiction") or {}
    place = jurisdiction.get("place")
    by_rule = {f.get("rule_id"): f for f in findings}
    out, seen = [], set()
    for e in report.get("events") or []:
        if e.get("action") != "conflict" or not isinstance(e.get("detail"), dict):
            continue
        d = e["detail"]
        field = canonical_field(d.get("field", ""))
        if field not in _decision_fields():
            continue
        finding = by_rule.get(d.get("rule"))
        if finding is None:
            continue
        pairs = [(d.get("value"), d.get("quote"), d.get("url"))]
        for other in ("other_county_source", "other_dataset"):
            if other in d:
                pairs.append((
                    d.get(other), d.get("other_quote"), d.get("other_url"),
                ))
        params = finding.get("parameters") or {}
        readings = []
        skip = False
        for value, quote, url in pairs:
            if value is None or str(value).strip().lower() in null_values:
                skip = True
                break
            parsed = value if isinstance(value, (int, float, bool)) else parse_fact(field, value)
            if parsed is None:
                skip = True
                break
            trial = moratorium_applies(
                project, {**params, field: parsed},
                layer=finding.get("layer"), place=place,
            )
            readings.append({
                "value": value, "quote": quote, "url": url, "applies": trial["applies"],
            })
        if skip or len(readings) < 2:
            continue
        key = (finding.get("rule_id"), field,
               tuple(sorted(str(r["value"]) for r in readings)))
        if key in seen:
            continue
        seen.add(key)
        out.append({
            "rule_id": finding.get("rule_id"),
            "field": field,
            "readings": readings,
            "holds": all(r["applies"] == finding.get("applies") for r in readings),
        })
    return out


def _catches(report, sensitivity):
    catches = []
    events = report.get("events") or []
    for i, e in enumerate(events):
        if e.get("action") != "retry_requested":
            continue
        nxt = next(
            (x for x in events[i + 1:] if x.get("action") == "verified"), None,
        )
        if nxt and isinstance(nxt.get("detail"), dict):
            failed = nxt["detail"].get("failed", 0)
            checked = nxt["detail"].get("checked", 0)
            outcome = (
                "all quotes verified" if not failed
                else f"{failed} of {checked} still failing"
            )
        else:
            outcome = "no follow-up verification recorded"
        detail = e.get("detail")
        catches.append({
            "round": e.get("round", 0),
            "actor": "evidence_verifier",
            "kind": "retry",
            "text": str(detail)[:300] if detail else "verifier asked for another attempt",
            "outcome": outcome,
        })
    for e in events:
        if e.get("action") != "value_corrected_from_quote":
            continue
        detail = e.get("detail") or {}
        label = "duration" if detail.get("field") == "duration_days" else detail.get("field", "")
        suffix = " days" if detail.get("field") == "duration_days" else ""
        catches.append({
            "round": e.get("round", 0),
            "actor": "evidence_verifier",
            "kind": "correction",
            "text": (
                f"Verifier recomputed {label} from the quoted text: "
                f"{detail.get('model_value')} → {detail.get('quote_value')}{suffix}"
            ),
            "outcome": "kept the quoted value",
        })
    for s in sensitivity:
        readings = " vs ".join(str(r["value"]) for r in s["readings"])
        catches.append({
            "round": 1,
            "actor": "evidence_verifier",
            "kind": "conflict",
            "text": f"Sources disagree on {s['field']}: {readings}",
            "outcome": (
                "verdict holds under both readings" if s["holds"]
                else "disagreement could change the answer"
            ),
        })
    open_objections = report.get("needs_confirmation") or []

    def open_key(o):
        return (o.get("rule_id"), o.get("type"), o.get("text"))

    open_keys = {open_key(o) for o in open_objections}
    for e in events:
        if e.get("action") != "objections":
            continue
        detail = e.get("detail") or []
        for o in detail if isinstance(detail, list) else []:
            if not isinstance(o, dict):
                continue
            if open_key(o) in open_keys:
                continue
            catches.append({
                "round": e.get("round", 0),
                "actor": "critic",
                "kind": o.get("type", "objection"),
                "text": str(o.get("text", ""))[:300],
                "outcome": f"re-investigated in round {e.get('round', 1) + 1}",
            })
    for o in open_objections:
        catches.append({
            "round": 1,
            "actor": "critic",
            "kind": o.get("type", "objection"),
            "text": str(o.get("text", ""))[:300],
            "outcome": (
                "resolved by code: applies under every conflicting reading"
                if o.get("blocking", True) is False
                else "left open for your team"
            ),
        })
    for e in events:
        if e.get("action") != "escalated" or e.get("role") != "system":
            continue
        detail = e.get("detail") or []
        for text in detail if isinstance(detail, list) else [detail]:
            catches.append({
                "round": e.get("round", 0),
                "actor": "system",
                "kind": "escalation",
                "text": str(text)[:300],
                "outcome": "left open for your team",
            })
    last_round = max([e.get("round", 0) for e in events] + [0])
    for note in report.get("guard_notes") or []:
        catches.append({
            "round": last_round,
            "actor": "guard",
            "kind": "guard",
            "text": str(note)[:300],
            "outcome": "applied to the verdict",
        })
    for m in report.get("model_trace") or []:
        if not m.get("escalated_from"):
            continue
        catches.append({
            "round": 0,
            "actor": m.get("role", "model"),
            "kind": "model_escalation",
            "text": f"{m.get('step')} moved from {m['escalated_from']} to {m.get('model')}",
            "outcome": "completed",
        })
    for m in report.get("model_trace") or []:
        if m.get("role") != "county_investigator" or m.get("step") != "plan":
            continue
        catches.append({
            "round": last_round,
            "actor": "county_investigator",
            "kind": "ultra_reextract",
            "text": "Lightning returned no facts; Ultra re-extracted",
            "outcome": "completed",
        })
    return catches


def _layer_status(findings, state_watch):
    status = {}
    for layer in LAYER_ORDER:
        fs = [f for f in findings if f.get("layer") == layer]
        yes = [f for f in fs if f.get("applies") == "yes"]
        name = LAYER_NAMES[layer]
        if yes:
            worst = next(
                (g for g in ("fatal", "major", "minor") if any(f.get("grade") == g for f in yes)),
                "info",
            )
            lamp = worst if worst in {"fatal", "major", "minor"} else "clear"
            matched = [f for f in yes if f.get("grade") == worst]
            first = matched[0] if matched else yes[0]
            grade_note = f" ({first.get('grade')})" if first.get("grade") else ""
            status[layer] = {
                "lamp": lamp,
                "summary": f"{first.get('title')} applies{grade_note}",
            }
        elif any(f.get("applies") == "unknown" for f in fs):
            first = next(f for f in fs if f.get("applies") == "unknown")
            status[layer] = {
                "lamp": "unknown",
                "summary": f"{first.get('title')} applicability unknown",
            }
        elif fs:
            status[layer] = {
                "lamp": "clear",
                "summary": f"No {name.lower()} rule applies to this site",
            }
        elif layer == "state" and state_watch:
            status[layer] = {
                "lamp": "not_modelled",
                "summary": (
                    f"No state rule applies; {len(state_watch)} "
                    "watch-list items (dataset, not verified)"
                ),
            }
        else:
            status[layer] = {"lamp": "not_modelled", "summary": f"No {name.lower()} rules modelled"}
    return status


def _stats(report):
    models: dict = {}
    receipts = []
    for m in report.get("model_trace") or []:
        models[m.get("model", "unknown")] = models.get(m.get("model", "unknown"), 0) + 1
        if m.get("receipt_id"):
            receipts.append(m["receipt_id"])
    by_backend: dict = {}
    blocked = 0
    for d in report.get("data_trace") or []:
        by_backend[d.get("backend", "unknown")] = by_backend.get(d.get("backend", "unknown"), 0) + 1
        if d.get("status") == "BLOCKED":
            blocked += 1
    verified = checked = 0
    for f in report.get("findings") or []:
        for ev in f.get("evidence") or []:
            checked += 1
            if ev.get("verification") == "verified":
                verified += 1
    chunks = tokens_saved = 0
    for e in report.get("events") or []:
        if e.get("action") == "markovian_run" and isinstance(e.get("detail"), dict):
            chunks += e["detail"].get("chunks", 0) or 0
            tokens_saved += e["detail"].get("tokens_saved", 0) or 0
    stamps = []
    for e in report.get("events") or []:
        try:
            stamps.append(datetime.fromisoformat(e["at"]))
        except (KeyError, TypeError, ValueError):
            continue
    duration = round((max(stamps) - min(stamps)).total_seconds(), 1) if stamps else 0.0
    return {
        "models": models,
        "receipts": sorted(set(receipts)),
        "data_queries": by_backend,
        "data_blocked": blocked,
        "quotes_verified": verified,
        "quotes_checked": checked,
        "markovian_chunks": chunks,
        "markovian_tokens_saved": tokens_saved,
        "run_duration_s": duration,
    }


def _default_coverage(report) -> dict:
    ctx = {**(report.get("site") or {}), **(report.get("jurisdiction") or {})}
    state_rules = [
        r["id"]
        for r in load_rules()
        if r.get("layer") == "state"
        and all(ctx.get(k) == v for k, v in (r.get("scope") or {}).items())
    ]
    county_keys = set(load_county_sources())
    county_sources = [
        f["rule_id"]
        for f in report.get("findings") or []
        if f.get("layer") in {"county", "city"} and f.get("rule_id") in county_keys
    ]
    return {"state_rules": state_rules, "county_sources": county_sources}


def _coverage_note(report) -> str | None:
    if any((f.get("layer") in {"state", "iso_rto"}) for f in report.get("findings") or []):
        return None
    jurisdiction = report.get("jurisdiction") or {}
    state = jurisdiction.get("state") or (report.get("site") or {}).get("state")
    if not state:
        return None
    return (
        f"State and grid rules are not modelled for {state}; "
        "federal rule and county dataset only."
    )


def _headline(report, decisive):
    verdict = report.get("verdict", "needs_confirmation")
    word = VERDICT_WORDS.get(verdict, verdict)
    if decisive:
        return f"{word}: {decisive[0]['title']}"
    for o in report.get("needs_confirmation") or []:
        question = o.get("question") or o.get("text")
        if question:
            return f"{word}: {question}"
    return FALLBACK_HEADLINE


def enrich(report: dict) -> dict:
    """Add a deterministic `explanation` to a run report. Pure and idempotent."""
    out = copy.deepcopy(report)
    out.setdefault("coverage", _default_coverage(out))
    as_of = _as_of(out)
    project = _project(out, as_of)
    findings = out.get("findings") or []
    decisive = _decisive(findings, as_of)
    rules_by_id = {r["id"]: r for r in load_rules()}
    jurisdiction = out.get("jurisdiction") or {}
    flips = []
    for finding in findings:
        flips.extend(
            _rule_flips(finding, project, decisive, rules_by_id,
                        place=jurisdiction.get("place"))
        )
    sensitivity = _sensitivity(out, findings, project)
    state_watch = out.get("state_watch") or []
    out["explanation"] = {
        "site": {
            "as_of": as_of,
            "incorporated": jurisdiction.get("place") is not None,
            "mw": (out.get("project") or {}).get("mw"),
            "permits_submitted": (out.get("project") or {}).get("permits_submitted"),
            "lat": jurisdiction.get("lat"),
            "lon": jurisdiction.get("lon"),
        },
        "headline": _headline(out, decisive),
        "coverage_note": _coverage_note(out),
        "decisive": decisive,
        "flips": flips,
        "sensitivity": sensitivity,
        "catches": _catches(out, sensitivity),
        "layer_status": _layer_status(findings, state_watch),
        "stats": _stats(out),
    }
    return out
