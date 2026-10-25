import json
import time

from fastapi.testclient import TestClient

from app.config import Settings
from app.main import create_app
from tests.test_screen import WASHINGTON, FakeResolver


class FakeOrchestrator:
    def run(self, address, mw, permits_submitted=None, run_id=None, on_event=None):
        on_event({"round": 1, "role": "planner", "action": "tasks", "detail": []})
        return {"run_id": run_id, "verdict": "no-go", "project": {"address": address, "mw": mw}}


def client(tmp_path, settings=None):
    (tmp_path / "md-showcase.json").write_text(
        json.dumps({"project": {"address": "A", "mw": 300}, "verdict": "no-go"})
    )
    app = create_app(settings or Settings(), resolver=FakeResolver(WASHINGTON),
                     orchestrator_factory=FakeOrchestrator, samples_dir=tmp_path)  # fmt: skip
    return TestClient(app)


def test_run_lifecycle_streams_events_then_report(tmp_path):
    c = client(tmp_path)
    run_id = c.post("/runs", json={"address": "x", "mw": 300}).json()["run_id"]
    for _ in range(50):
        state = c.get(f"/runs/{run_id}").json()
        if state["status"] != "running":
            break
        time.sleep(0.02)
    assert state["status"] == "done" and state["report"]["verdict"] == "no-go"
    assert state["events"][0]["role"] == "planner"
    assert c.get("/runs/nope").status_code == 404


def test_samples_list_and_fetch(tmp_path):
    c = client(tmp_path)
    assert c.get("/samples").json() == [
        {"name": "md-showcase", "address": "A", "mw": 300, "verdict": "no-go"}
    ]
    assert c.get("/samples/md-showcase").json()["verdict"] == "no-go"
    assert c.get("/samples/..%2Fsecrets").status_code == 404


def test_sample_mode_disables_live_runs(tmp_path):
    c = client(tmp_path, Settings(sample_mode=True))
    assert c.post("/runs", json={"address": "x", "mw": 300}).status_code == 503
    assert c.get("/samples").status_code == 200
