import json
import time

import pytest
from fastapi.testclient import TestClient
from pydantic import ValidationError

from app.config import Settings
from app.main import RunRequest, create_app
from tests.test_screen import WASHINGTON, FakeResolver


class FakeOrchestrator:
    def __init__(self):
        self.calls = []

    def run(
        self,
        address=None,
        mw=0,
        permits_submitted=None,
        run_id=None,
        on_event=None,
        lat=None,
        lon=None,
    ):
        self.calls.append({"address": address, "lat": lat, "lon": lon})
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
        {
            "name": "md-showcase",
            "address": "A",
            "mw": 300,
            "verdict": "no-go",
            "lat": None,
            "lon": None,
            "headline": "Go: no fatal or major rule applies to this site.",
            "county": None,
        }
    ]
    assert c.get("/samples/md-showcase").json()["verdict"] == "no-go"
    assert c.get("/samples/..%2Fsecrets").status_code == 404


def test_sample_mode_runs_posts_through_orchestrator(tmp_path):
    c = client(tmp_path, Settings(sample_mode=True))
    run_id = c.post("/runs", json={"address": "x", "mw": 300}).json()["run_id"]
    for _ in range(50):
        state = c.get(f"/runs/{run_id}").json()
        if state["status"] != "running":
            break
        time.sleep(0.02)
    assert state["status"] == "done"
    assert c.get("/samples").status_code == 200


def test_run_request_accepts_address_xor_lat_lon():
    assert RunRequest(address="x", mw=300).address == "x"
    assert RunRequest(lat=32.223, lon=-110.975, mw=300).lat == 32.223
    with pytest.raises(ValidationError):
        RunRequest(address="x", lat=32.223, lon=-110.975, mw=300)
    with pytest.raises(ValidationError):
        RunRequest(mw=300)
    with pytest.raises(ValidationError):
        RunRequest(lat=32.223, mw=300)
    with pytest.raises(ValidationError):
        RunRequest(lat=10.0, lon=-110.975, mw=300)
    with pytest.raises(ValidationError):
        RunRequest(lat=32.223, lon=-10.0, mw=300)


def fake_report(run_id, address="B", mw=100.0, verdict="go"):
    return {
        "run_id": run_id,
        "project": {"address": address, "mw": mw, "permits_submitted": None},
        "jurisdiction": {
            "place": None,
            "county_name": "Loudoun County",
            "lat": 39.11,
            "lon": -77.55,
            "state": "VA",
            "iso": "unknown",
        },
        "verdict": verdict,
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


def portfolio_client(tmp_path):
    samples = tmp_path / "samples"
    samples.mkdir(exist_ok=True)
    (samples / "md-showcase.json").write_text(
        json.dumps(
            {
                "run_id": "20261025T000000Z-000000",
                "project": {"address": "A", "mw": 300, "permits_submitted": None},
                "jurisdiction": {"place": None, "county_name": "X County"},
                "verdict": "go",
                "findings": [],
                "needs_confirmation": [],
                "conflicts": [],
                "events": [{"round": 0, "role": "system", "action": "seeded", "detail": {}}],
                "model_trace": [],
                "data_trace": [],
                "markovian_runs": [],
                "guard_notes": [],
                "state_watch": [],
            }
        )
    )
    runs = tmp_path / "runs"
    for run_id in ("20261025T120000Z-abc123", "20261026T120000Z-def456"):
        run_dir = runs / run_id
        run_dir.mkdir(parents=True, exist_ok=True)
        (run_dir / "report.json").write_text(json.dumps(fake_report(run_id)))
    app = create_app(
        Settings(), resolver=FakeResolver(WASHINGTON),
        orchestrator_factory=FakeOrchestrator, samples_dir=samples, runs_dir=runs,
    )
    return TestClient(app)


def test_portfolio_lists_samples_plus_live_newest_first(tmp_path):
    rows = portfolio_client(tmp_path).get("/portfolio").json()
    assert [r["kind"] for r in rows] == ["showcase", "live", "live"]
    assert rows[0]["id"] == "md-showcase" and rows[0]["county"] == "X County"
    assert rows[0]["created"] == "20261025T000000Z-000000"
    assert [r["id"] for r in rows[1:]] == [
        "20261026T120000Z-def456",
        "20261025T120000Z-abc123",
    ]
    assert all(
        {"id", "kind", "address", "mw", "verdict", "headline", "lat", "lon", "county",
         "created"} <= set(r) for r in rows
    )
    assert rows[1]["lat"] == 39.11 and rows[1]["headline"].startswith("Go")


def test_run_served_from_disk_after_restart(tmp_path):
    first = portfolio_client(tmp_path)
    run_id = "20261026T120000Z-def456"
    assert first.get(f"/runs/{run_id}").json()["report"]["verdict"] == "go"
    second = portfolio_client(tmp_path)
    assert second.get(f"/runs/{run_id}").json()["report"]["verdict"] == "go"
    assert second.get("/runs/not-an-id!").status_code == 404
    assert second.get("/runs/ABC").status_code == 404


def test_post_runs_with_lat_lon_reaches_orchestrator(tmp_path):
    factory = FakeOrchestrator()
    app = create_app(
        Settings(), resolver=FakeResolver(WASHINGTON),
        orchestrator_factory=lambda: factory, samples_dir=tmp_path,
    )
    c = TestClient(app)
    run_id = c.post("/runs", json={"lat": 32.223, "lon": -110.975, "mw": 300}).json()["run_id"]
    for _ in range(50):
        state = c.get(f"/runs/{run_id}").json()
        if state["status"] != "running":
            break
        time.sleep(0.02)
    assert state["status"] == "done"
    assert factory.calls[-1]["lat"] == 32.223 and factory.calls[-1]["lon"] == -110.975
    assert c.post("/runs", json={"mw": 300}).status_code == 422
    assert c.post("/runs", json={"lat": 10.0, "lon": -110.975, "mw": 300}).status_code == 422


class StubSiteContext:
    def context(self, lat, lon, county_fips):
        return {
            "query": {"lat": lat, "lon": lon, "county_fips": county_fips},
            "county": {"stub": True},
            "place": None,
            "transmission": None,
            "errors": [],
        }


def disk_context_client(tmp_path):
    samples = tmp_path / "samples"
    samples.mkdir(exist_ok=True)
    (samples / "demo.json").write_text(
        json.dumps({"project": {"address": "A", "mw": 300}, "verdict": "go"})
    )
    runs = tmp_path / "runs"
    done_id = "20261026T120000Z-def456"
    report = fake_report(done_id)
    report["jurisdiction"]["county_fips"] = "51107"
    (runs / done_id).mkdir(parents=True, exist_ok=True)
    (runs / done_id / "report.json").write_text(json.dumps(report))
    pending_id = "20261025T120000Z-abc123"
    (runs / pending_id).mkdir(parents=True, exist_ok=True)
    (runs / pending_id / "report.json").write_text(
        json.dumps({"run_id": pending_id, "verdict": "go"})
    )
    app = create_app(
        Settings(), resolver=FakeResolver(WASHINGTON),
        orchestrator_factory=FakeOrchestrator, samples_dir=samples, runs_dir=runs,
    )
    app.state.site_context = StubSiteContext()
    return TestClient(app)


def test_run_context_served_from_disk_after_restart(tmp_path):
    c = disk_context_client(tmp_path)
    out = c.get("/runs/20261026T120000Z-def456/context")
    assert out.status_code == 200
    assert out.json()["query"]["county_fips"] == "51107"
    assert c.get("/runs/20261025T000000Z-000000/context").status_code == 404
    assert c.get("/runs/not-an-id!/context").status_code == 404


def test_run_context_without_jurisdiction_is_not_ready(tmp_path):
    c = disk_context_client(tmp_path)
    assert c.get("/runs/20261025T120000Z-abc123/context").status_code == 409


def test_portfolio_skips_corrupt_live_report(tmp_path):
    c = portfolio_client(tmp_path)
    assert len(c.get("/portfolio").json()) == 3
    runs = tmp_path / "runs"
    (runs / "20261025T120000Z-abc123" / "report.json").write_text(
        json.dumps({"broken": True})
    )
    (runs / "not-a-run" / "report.json").parent.mkdir(parents=True, exist_ok=True)
    (runs / "not-a-run" / "report.json").write_text(json.dumps({"broken": True}))
    rows = c.get("/portfolio").json()
    assert [r["id"] for r in rows] == ["md-showcase", "20261026T120000Z-def456"]
