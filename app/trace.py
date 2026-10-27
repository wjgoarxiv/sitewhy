"""JSONL agent traces for run.py.

Maps a run report's `events` + `model_trace` (never hand-written) to one row
per event: timestamp, agent_name, action, input_summary, output_summary,
target_agent, model, retry_count, status.
"""

RETRY_ACTIONS = {"retry_requested", "conflict"}


def _short(value, limit: int = 160) -> str:
    text = value if isinstance(value, str) else json_dumps(value)
    text = " ".join(str(text).split())
    return text if len(text) <= limit else text[:limit] + "…"


def json_dumps(value) -> str:
    import json

    try:
        return json.dumps(value, default=str)
    except (TypeError, ValueError):
        return str(value)


def _summarize(action: str, detail) -> tuple[str, str]:
    """Return (input_summary, output_summary) for one event."""
    if action == "resolved" and isinstance(detail, dict):
        place = f" · {detail['place']}" if detail.get("place") else " · unincorporated"
        return "", f"Site resolved: {detail.get('county')}, {detail.get('state')}{place}"
    if action == "seeded" and isinstance(detail, dict):
        local = detail.get("local") or []
        curated = detail.get("curated") or []
        return "", f"{len(local)} local rule(s), {len(curated)} curated rule(s)"
    if action in {"tasks", "targeted_tasks"}:
        items = detail if isinstance(detail, list) else []
        ins = "; ".join(
            f"{t.get('rule_id')}: {len(t.get('questions') or [])} question(s)" for t in items
            if isinstance(t, dict)
        )
        return "", ins or "no local rules"
    if action == "computed" and isinstance(detail, list):
        return "", ", ".join(
            f"{f.get('rule_id')}: {f.get('applies')}" for f in detail if isinstance(f, dict)
        )
    if action == "draft" and isinstance(detail, dict):
        return "", f"verdict {detail.get('verdict')}"
    if action == "objections":
        items = detail if isinstance(detail, list) else []
        if not items:
            return "", "no objections"
        return "", "; ".join(
            f"{o.get('type')} on {o.get('rule_id')}" for o in items if isinstance(o, dict)
        )
    if action == "markovian_run" and isinstance(detail, dict):
        return "", (
            f"{detail.get('rule')} attempt {detail.get('attempt')}: "
            f"{detail.get('chunks')} chunk(s), {detail.get('facts')} fact(s), "
            f"{detail.get('status')}"
        )
    if action == "verified" and isinstance(detail, dict):
        return "", (
            f"{detail.get('rule')} attempt {detail.get('attempt')}: "
            f"{detail.get('checked', 0) - detail.get('failed', 0)}"
            f"/{detail.get('checked', 0)} quotes verbatim"
        )
    if action == "retry_requested":
        return _short(detail), "retrying with verifier feedback"
    if action == "conflict" and isinstance(detail, dict):
        other = detail.get("other_county_source", detail.get("other_dataset"))
        return f"{detail.get('field')}: {detail.get('value')} vs {other}", "kept for adjudication"
    if action == "escalated":
        items = detail if isinstance(detail, list) else [detail]
        return "", f"{len(items)} objection(s) need confirmation"
    if action == "timeout":
        return "", _short(detail)
    if action == "state_watch" and isinstance(detail, list):
        return "", f"{len(detail)} watch-list item(s)"
    return "", _short(detail)


def _status(action: str, detail) -> str:
    if action == "timeout":
        return "timeout"
    if action == "escalated":
        return "escalated"
    if action in RETRY_ACTIONS:
        return "retry"
    if action == "objections" and detail:
        return "retry"
    return "ok"


def trace_events(report: dict) -> list[dict]:
    """Map a run report to JSONL-ready trace rows."""
    model_by_role: dict[str, str] = {}
    for entry in report.get("model_trace") or []:
        if entry.get("role"):
            model_by_role[entry["role"]] = entry.get("model") or ""
    events = report.get("events") or []
    rows = []
    retries = 0
    for i, event in enumerate(events):
        action = event.get("action", "")
        detail = event.get("detail")
        if action == "retry_requested":
            retries += 1
        attempt = detail.get("attempt") if isinstance(detail, dict) else None
        in_summary, out_summary = _summarize(action, detail)
        nxt = events[i + 1] if i + 1 < len(events) else None
        rows.append({
            "timestamp": event.get("at") or "",
            "agent_name": event.get("role") or "",
            "action": action,
            "input_summary": in_summary,
            "output_summary": out_summary,
            "target_agent": (nxt.get("role") or "") if nxt else "",
            "model": model_by_role.get(event.get("role") or "", ""),
            "retry_count": (attempt - 1) if isinstance(attempt, int) and attempt > 0 else retries,
            "status": _status(action, detail),
        })
    return rows
