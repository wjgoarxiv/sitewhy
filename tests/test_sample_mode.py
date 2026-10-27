"""Sample mode runs the real agents on cached data (Todo 10)."""

import json
import time

from fastapi.testclient import TestClient

from app.config import Settings
from app.main import create_app
from app.trace import trace_events

WASHINGTON = {"address": "13820 Pennsylvania Ave, Hagerstown MD 21742", "mw": 300,
              "permits_submitted": False}


def sample_client(tmp_path):
    app = create_app(
        Settings(sample_mode=True), samples_dir=tmp_path, runs_dir=tmp_path / "runs",
    )
    return TestClient(app)


def wait_done(c, run_id, timeout_s=60):
    start = time.monotonic()
    while time.monotonic() - start < timeout_s:
        state = c.get(f"/runs/{run_id}").json()
        if state["status"] != "running":
            return state
        time.sleep(0.2)
    raise AssertionError(f"run {run_id} still running after {timeout_s}s")


def test_sample_mode_post_runs_real_orchestrator(tmp_path):
    from pathlib import Path

    before = set(p.name for p in Path("data/llm_cache").glob("*.json"))
    c = sample_client(tmp_path)
    run_id = c.post("/runs", json=WASHINGTON).json()["run_id"]
    state = wait_done(c, run_id)
    assert state["status"] == "done", state.get("error")
    report = state["report"]
    assert report["verdict"] == "no-go"
    assert report["project"]["address"] == WASHINGTON["address"]
    roles = {e["role"] for e in report["events"]}
    assert {"planner", "county_investigator", "adjudicator", "critic"} <= roles
    assert report["model_trace"] and all(m.get("model") for m in report["model_trace"])
    after = set(p.name for p in Path("data/llm_cache").glob("*.json"))
    assert after == before, "sample run must replay caches, not write new ones"


def test_sample_mode_unknown_address_fails_fast_with_message(tmp_path):
    c = sample_client(tmp_path)
    start = time.monotonic()
    run_id = c.post(
        "/runs", json={"address": "999 Nowhere St, Nowhere XX 00000", "mw": 300}
    ).json()["run_id"]
    state = wait_done(c, run_id, timeout_s=10)
    elapsed = time.monotonic() - start
    assert state["status"] == "error"
    assert "sample" in state["error"].lower(), state["error"]
    assert elapsed < 10, f"took {elapsed:.1f}s"


def test_sample_mode_llm_cache_miss_is_a_clear_message(tmp_path):
    c = sample_client(tmp_path)
    start = time.monotonic()
    run_id = c.post(
        "/runs", json={**WASHINGTON, "mw": 50}
    ).json()["run_id"]
    state = wait_done(c, run_id, timeout_s=10)
    assert state["status"] == "error"
    assert "sample_mode" in state["error"].lower() or "cached" in state["error"].lower()
    assert time.monotonic() - start < 10


def synthetic_report():
    return {
        "run_id": "r1",
        "events": [
            {"round": 1, "role": "planner", "action": "tasks", "at": "2026-10-26T00:00:01+00:00",
             "detail": [{"rule_id": "r", "questions": ["q1"]}]},
            {"round": 1, "role": "county_investigator", "action": "markovian_run",
             "at": "2026-10-26T00:00:02+00:00",
             "detail": {"rule": "r", "attempt": 1, "chunks": 2, "facts": 1,
                        "status": "completed"}},
            {"round": 1, "role": "adjudicator", "action": "draft",
             "at": "2026-10-26T00:00:03+00:00",
             "detail": {"verdict": "no-go", "grades": {}}},
            {"round": 1, "role": "critic", "action": "objections",
             "at": "2026-10-26T00:00:04+00:00", "detail": []},
        ],
        "model_trace": [
            {"step": "plan", "role": "planner", "model": "nvidia/light", "receipt_id": "a"},
            {"step": "synthesize", "role": "adjudicator", "model": "nvidia/ultra",
             "receipt_id": "b"},
        ],
    }


def test_trace_jsonl_shape(tmp_path):
    rows = trace_events(synthetic_report())
    assert len(rows) == 4
    required = {"timestamp", "agent_name", "action", "input_summary", "output_summary",
                "target_agent", "model", "retry_count", "status"}
    assert all(required <= set(r) for r in rows)
    assert len({r["agent_name"] for r in rows}) >= 2
    assert any(r["agent_name"] == "critic" for r in rows)
    assert rows[2]["model"] == "nvidia/ultra"
    assert all(isinstance(r["retry_count"], int) for r in rows)
    lines = [json.dumps(r) for r in rows]
    assert all("\n" not in line for line in lines)
