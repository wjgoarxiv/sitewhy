"""Todo 4: cached site context (TIGERweb county/city, HIFLD transmission)."""

import json

import httpx
import pytest
from fastapi.testclient import TestClient

from app.config import Settings

COUNTY_FC = {
    "type": "FeatureCollection",
    "features": [
        {
            "type": "Feature",
            "properties": {"GEOID": "04019", "NAME": "Pima County"},
            "geometry": {
                "type": "Polygon",
                "coordinates": [[[0.0, 0.0], [1.0, 0.0], [1.0, 1.0], [0.0, 0.0]]],
            },
        }
    ],
}
PLACE_FC = {
    "type": "FeatureCollection",
    "features": [
        {
            "type": "Feature",
            "properties": {"NAME": "Tucson city"},
            "geometry": {"type": "Point", "coordinates": [-110.975, 32.223]},
        }
    ],
}
EMPTY_FC = {"type": "FeatureCollection", "features": []}
TRANS_FC = {
    "type": "FeatureCollection",
    "features": [
        {
            "type": "Feature",
            "properties": {"VOLTAGE": 138, "OWNER": "X", "STATUS": "IN SERVICE"},
            "geometry": {"type": "LineString", "coordinates": [[0.0, 0.0], [1.0, 1.0]]},
        },
        {
            "type": "Feature",
            "properties": {"VOLTAGE": 345, "OWNER": "Y", "STATUS": "IN SERVICE"},
            "geometry": {"type": "LineString", "coordinates": [[2.0, 2.0], [3.0, 3.0]]},
        },
    ],
}


def handler_factory(calls, place=PLACE_FC, trans_status=200):
    def handler(request):
        calls.append(request.url.path)
        path = request.url.path
        if path.endswith("/82/query"):
            assert "GEOID" in request.url.params["where"]
            assert request.url.params["outSR"] == "4326"
            assert request.url.params["f"] == "geojson"
            return httpx.Response(200, json=COUNTY_FC)
        if path.endswith("/28/query"):
            assert request.url.params["geometryType"] == "esriGeometryPoint"
            return httpx.Response(200, json=place)
        if path.endswith("/0/query"):
            assert request.url.params["outFields"] == "VOLTAGE,OWNER,STATUS"
            assert request.url.params["resultRecordCount"] == "300"
            if trans_status != 200:
                return httpx.Response(trans_status, json={"error": "boom"})
            return httpx.Response(200, json=TRANS_FC)
        raise AssertionError(f"unexpected host in {request.url!r}")

    return handler


def make_context(tmp_path, **kw):
    from app.sitecontext import SiteContext

    calls: list = []
    transport = httpx.MockTransport(handler_factory(calls, **kw))
    return SiteContext(client=httpx.Client(transport=transport), cache_dir=tmp_path), calls


def test_place_and_county_assembled(tmp_path):
    sc, _ = make_context(tmp_path)
    out = sc.context(32.2230, -110.9750, "04019")
    assert out["county"]["features"][0]["properties"]["NAME"] == "Pima County"
    assert out["place"]["properties"]["NAME"] == "Tucson city"
    assert len(out["transmission"]["features"]) == 2
    assert out["errors"] == []
    assert any("TIGERweb" in s["attribution"] for s in out["sources"])
    assert any("HIFLD" in s["attribution"] for s in out["sources"])
    assert out["google_maps_url"].startswith("https://www.google.com/maps/search/?api=1&query=")


def test_second_call_served_from_cache(tmp_path):
    sc, calls = make_context(tmp_path)
    sc.context(32.2230, -110.9750, "04019")
    assert len(calls) == 3
    calls.clear()
    out = sc.context(32.2230, -110.9750, "04019")
    assert calls == []
    assert out["place"]["properties"]["NAME"] == "Tucson city"


def test_transmission_failure_keeps_county(tmp_path):
    sc, _ = make_context(tmp_path, trans_status=500)
    out = sc.context(32.2230, -110.9750, "04019")
    assert out["transmission"] is None
    assert any(e["part"] == "transmission" for e in out["errors"])
    assert out["county"]["features"][0]["properties"]["NAME"] == "Pima County"


def test_no_place_gives_null(tmp_path):
    sc, _ = make_context(tmp_path, place=EMPTY_FC)
    out = sc.context(39.6929, -77.7215, "24043")
    assert out["place"] is None
    assert not [e for e in out["errors"] if e["part"] == "place"]
    assert out["county"] is not None


def test_context_endpoint_validates(tmp_path):
    from app.main import create_app
    from tests.test_screen import WASHINGTON, FakeResolver

    client = TestClient(create_app(Settings(), resolver=FakeResolver(WASHINGTON)))
    bad_lat = {"lat": 10, "lon": -110.0, "county_fips": "04019"}
    bad_fips = {"lat": 32.0, "lon": -110.0, "county_fips": "4019"}
    bad_lon = {"lat": 32.0, "lon": 10.0, "county_fips": "04019"}
    assert client.get("/context", params=bad_lat).status_code == 422
    assert client.get("/context", params=bad_fips).status_code == 422
    assert client.get("/context", params=bad_lon).status_code == 422


def test_sample_context_served_from_cache(tmp_path):
    from app.main import create_app
    from tests.test_screen import WASHINGTON, FakeResolver

    samples = tmp_path / "samples"
    samples.mkdir()
    (samples / "demo.json").write_text(
        json.dumps({"jurisdiction": {"lat": 32.2230, "lon": -110.9750, "county_fips": "04019"}})
    )
    sc, calls = make_context(tmp_path / "cache")
    app = create_app(Settings(), resolver=FakeResolver(WASHINGTON), samples_dir=samples)
    app.state.site_context = sc
    client = TestClient(app)
    first = client.get("/samples/demo/context")
    assert first.status_code == 200
    assert first.json()["place"]["properties"]["NAME"] == "Tucson city"
    calls.clear()
    second = client.get("/samples/demo/context")
    assert second.status_code == 200 and calls == []
    assert client.get("/samples/nope/context").status_code == 404


def test_run_context_served_from_report(tmp_path):
    import time

    from app.main import create_app
    from tests.test_screen import WASHINGTON, FakeResolver

    class OrchestratorWithJurisdiction:
        def run(self, address, mw, permits_submitted=None, run_id=None, on_event=None):
            on_event({"role": "system"})
            return {
                "run_id": run_id,
                "verdict": "go",
                "jurisdiction": {"lat": 32.2230, "lon": -110.9750, "county_fips": "04019"},
            }

    app = create_app(
        Settings(),
        resolver=FakeResolver(WASHINGTON),
        orchestrator_factory=OrchestratorWithJurisdiction,
    )
    sc, _ = make_context(tmp_path)
    app.state.site_context = sc
    client = TestClient(app)
    run_id = client.post("/runs", json={"address": "x", "mw": 300}).json()["run_id"]
    assert client.get(f"/runs/{run_id}/context").status_code in (200, 409)
    for _ in range(50):
        state = client.get(f"/runs/{run_id}").json()
        if state["status"] != "running":
            break
        time.sleep(0.02)
    out = client.get(f"/runs/{run_id}/context")
    assert out.status_code == 200
    assert out.json()["place"]["properties"]["NAME"] == "Tucson city"


@pytest.mark.live
def test_tucson_place_live():
    from app.sitecontext import SiteContext

    out = SiteContext().context(32.2230, -110.9750, "04019")
    assert out["place"]["properties"]["NAME"] == "Tucson city"
    assert out["county"]["features"][0]["properties"]["GEOID"] == "04019"
