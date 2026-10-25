import json

import httpx
import pytest

from app.config import Settings, load_settings
from app.data import DuckDbHarness, FallbackHarness, HarnessError, ZetarisHarness

ZSET = Settings(zetaris_base_url="http://z", zetaris_org_id="1", zetaris_api_key="k")


@pytest.fixture
def csvs(tmp_path):
    sites = tmp_path / "pipeline_sites.csv"
    sites.write_text("site_id,county_fips,mw\nS1,24043,300\nS2,48453,120\n")
    mor = tmp_path / "moratoria.csv"
    mor.write_text("county_fips,status\n24043,active\n")
    return sites, mor


def test_duckdb_registers_csv_and_joins_with_string_values(csvs):
    sites, mor = csvs
    h = DuckDbHarness()
    h.register_csv("pipeline_sites", sites)
    h.register_csv("moratoria", mor)
    rows = h.query(
        "SELECT s.site_id, m.status FROM SITEWHY.pipeline_sites s "
        "LEFT JOIN SITEWHY.moratoria m ON s.county_fips = m.county_fips ORDER BY s.site_id"
    )
    assert rows == [{"site_id": "S1", "status": "active"}, {"site_id": "S2", "status": None}]


def test_duckdb_bad_sql_raises_harness_error():
    with pytest.raises(HarnessError):
        DuckDbHarness().query("SELECT * FROM SITEWHY.nope")


def zclient(handler):
    return httpx.Client(transport=httpx.MockTransport(handler))


def test_zetaris_query_sends_auth_headers_and_maps_rows():
    seen = {}

    def handler(request):
        seen["headers"] = dict(request.headers)
        seen["body"] = json.loads(request.content)
        return httpx.Response(200, json={"headers": ["a", "b"], "data": [["1", "x"]], "total": 1})

    h = ZetarisHarness(ZSET, client=zclient(handler))
    assert h.query("SELECT 1") == [{"a": "1", "b": "x"}]
    assert seen["headers"]["authorization"] == "Bearer k"
    assert seen["headers"]["x-org-id"] == "1" and seen["headers"]["x-request-id"]
    assert seen["body"]["sql"] == "SELECT 1"


def test_zetaris_error_and_unreachable_raise_harness_error():
    h = ZetarisHarness(ZSET, client=zclient(lambda r: httpx.Response(500, text="boom")))
    with pytest.raises(HarnessError):
        h.query("SELECT 1")

    def down(request):
        raise httpx.ConnectError("refused")

    with pytest.raises(HarnessError):
        ZetarisHarness(ZSET, client=zclient(down)).query("SELECT 1")


def test_zetaris_unconfigured_raises():
    with pytest.raises(HarnessError):
        ZetarisHarness(Settings(), client=zclient(lambda r: httpx.Response(200))).query("x")


def test_zetaris_register_stages_file_then_creates_table(tmp_path):
    sqls, staged = [], []

    def handler(request):
        sqls.append(json.loads(request.content)["sql"])
        return httpx.Response(200, json={"headers": ["Result"], "data": [], "total": 0})

    f = tmp_path / "t.csv"
    f.write_text("a\n1\n")
    h = ZetarisHarness(
        ZSET, client=zclient(handler), stage=lambda p: staged.append(p) or "/c/t.csv"
    )
    h.register_csv("t", f)
    assert staged == [f]
    create = [s for s in sqls if s.startswith("CREATE LIGHTNING FILESTORE TABLE t FROM SITEWHY")]
    assert create and 'path "file:///c/t.csv"' in create[0]


def test_fallback_uses_duckdb_and_records_blocked(csvs):
    sites, _ = csvs

    def down(request):
        raise httpx.ConnectError("refused")

    duck = DuckDbHarness()
    duck.register_csv("pipeline_sites", sites)
    h = FallbackHarness(ZetarisHarness(ZSET, client=zclient(down)), duck)
    rows = h.query("SELECT count(*) AS n FROM SITEWHY.pipeline_sites")
    assert rows == [{"n": "2"}]
    assert h.trace[-2]["backend"] == "zetaris" and h.trace[-2]["status"] == "BLOCKED"
    assert h.trace[-1]["backend"] == "duckdb" and h.trace[-1]["status"] == "ok"


def test_fallback_prefers_primary_when_healthy():
    ok = ZetarisHarness(
        ZSET,
        client=zclient(lambda r: httpx.Response(200, json={"headers": ["n"], "data": [["5"]]})),
    )
    h = FallbackHarness(ok, DuckDbHarness())
    assert h.query("SELECT 5 AS n") == [{"n": "5"}]
    assert [t["backend"] for t in h.trace] == ["zetaris"]


@pytest.mark.live
def test_live_zetaris_join(csvs):
    sites, mor = csvs
    h = ZetarisHarness(load_settings())
    h.register_csv("t_sites", sites)
    h.register_csv("t_moratoria", mor)
    rows = h.query(
        "SELECT s.site_id, m.status FROM SITEWHY.t_sites s "
        "LEFT JOIN SITEWHY.t_moratoria m ON s.county_fips = m.county_fips ORDER BY s.site_id"
    )
    assert rows == [{"site_id": "S1", "status": "active"}, {"site_id": "S2", "status": None}]
