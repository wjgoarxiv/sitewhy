"""Run safety (Todo 3): deadline, single-run guard, Markovian reset. RED first."""

import threading
import time

import httpx
import pytest
from fastapi.testclient import TestClient

from app.config import Settings
from app.data import DuckDbHarness, FallbackHarness
from app.evidence import EvidenceFetcher
from app.llm import LIGHTNING, DeadlineExceeded, ModelRouter
from app.main import create_app
from app.orchestrator import Orchestrator
from app.seed import register_seed
from tests.test_llm import SETTINGS, reply
from tests.test_orchestrator import (
    DRAFT_NO_GO,
    GOOD_FACTS,
    PLAN,
    WASHINGTON_UNINCORPORATED,
    ScriptedRouter,
    facts_reply,
    serve,
)
from tests.test_screen import WASHINGTON, FakeResolver


def make_orchestrator(router, tmp_path, **kw):
    h = FallbackHarness(DuckDbHarness(), DuckDbHarness())
    register_seed(h.primary)
    fetcher = EvidenceFetcher(
        client=httpx.Client(transport=httpx.MockTransport(serve)),
        cache_dir=tmp_path / "src",
    )
    return Orchestrator(
        FakeResolver(WASHINGTON_UNINCORPORATED), h, router, fetcher,
        runs_dir=tmp_path / "runs", **kw,
    )


def scripted_router():
    return ScriptedRouter(
        planner=[PLAN],
        county_investigator=[facts_reply(GOOD_FACTS)],
        adjudicator=[DRAFT_NO_GO],
        critic=["[]"],
    )


def test_deadline_expiry_returns_partial_needs_confirmation(tmp_path):
    ticks = iter([0.0] + [400.0] * 100)
    orch = make_orchestrator(
        scripted_router(), tmp_path, deadline=300, clock=lambda: next(ticks)
    )
    report = orch.run("addr", mw=300)
    assert report["verdict"] == "needs_confirmation"
    assert any(
        "Run stopped at the 5-minute limit before" in o["text"]
        for o in report["needs_confirmation"]
    )
    assert any(e["action"] == "timeout" for e in report["events"])
    assert "model_trace" in report and "markovian_runs" in report


class BlockingOrchestrator:
    def __init__(self):
        self.release = threading.Event()

    def run(self, address=None, mw=0, permits_submitted=None, run_id=None,
            on_event=None, lat=None, lon=None):
        on_event({"round": 1, "role": "planner", "action": "tasks", "detail": []})
        assert self.release.wait(10)
        return {"run_id": run_id, "verdict": "go",
                "project": {"address": address, "mw": mw}}


def test_second_concurrent_post_returns_409(tmp_path):
    factory = BlockingOrchestrator()
    app = create_app(
        Settings(), resolver=FakeResolver(WASHINGTON),
        orchestrator_factory=lambda: factory, samples_dir=tmp_path,
    )
    c = TestClient(app)
    first = c.post("/runs", json={"address": "x", "mw": 300})
    assert first.status_code == 202
    mid = c.get(f"/runs/{first.json()['run_id']}")
    assert mid.json()["status"] == "running"
    second = c.post("/runs", json={"address": "y", "mw": 100})
    assert second.status_code == 409
    assert second.json()["detail"] == "A screening is already running"
    factory.release.set()
    state = mid.json()
    for _ in range(100):
        state = c.get(f"/runs/{first.json()['run_id']}").json()
        if state["status"] != "running":
            break
        time.sleep(0.02)
    assert state["status"] == "done"


def test_markovian_runs_reset_between_runs(tmp_path):
    router = ScriptedRouter(
        planner=[PLAN, PLAN],
        county_investigator=[facts_reply(GOOD_FACTS), facts_reply(GOOD_FACTS)],
        adjudicator=[DRAFT_NO_GO, DRAFT_NO_GO],
        critic=["[]", "[]"],
    )
    orch = make_orchestrator(router, tmp_path)
    first = orch.run("addr", mw=300)
    second = orch.run("addr", mw=300)
    assert len(first["markovian_runs"]) == 1
    assert len(second["markovian_runs"]) == 1


def test_llm_deadline_blocks_network_call(tmp_path):
    calls = []

    def handler(request):
        calls.append(1)
        return reply(LIGHTNING, "ok")

    client = httpx.Client(transport=httpx.MockTransport(handler))
    router = ModelRouter(
        SETTINGS, client=client, cache_dir=tmp_path,
        sleep=lambda s: None, deadline=0,
    )
    with pytest.raises(DeadlineExceeded):
        router.generate("extract", [{"role": "user", "content": "q"}])
    assert calls == []
