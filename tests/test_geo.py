import json
from pathlib import Path

import httpx
import pytest
from fastapi.testclient import TestClient

from app.config import Settings
from app.geo import Resolver, UnresolvedAddressError, iso_for
from app.main import create_app

FIX = Path(__file__).parent / "fixtures" / "census"
ADDRESSES = {
    "md": "100 W Washington St, Hagerstown, MD 21740",
    "tx": "555 Walnut St, Abilene, TX 79601",
    "az": "255 W Alameda St, Tucson, AZ 85701",
}


def recorded(request):
    address = request.url.params["address"]
    name = next((k for k, v in ADDRESSES.items() if v == address), "bad")
    return httpx.Response(200, json=json.loads((FIX / f"{name}.json").read_text()))


@pytest.fixture
def resolver(tmp_path):
    return Resolver(
        client=httpx.Client(transport=httpx.MockTransport(recorded)), cache_dir=tmp_path
    )


def test_washington_county_md_is_pjm(resolver):
    j = resolver.resolve(ADDRESSES["md"])
    assert (j.state, j.county_fips, j.county_name) == ("MD", "24043", "Washington County")
    assert j.place == "Hagerstown city"
    assert j.iso == "PJM"
    assert "The Potomac Edison Company" in [u["name"] for u in j.utilities]
    assert j.multiple_utilities


def test_taylor_county_tx_is_ercot(resolver):
    j = resolver.resolve(ADDRESSES["tx"])
    assert (j.state, j.county_fips) == ("TX", "48441")
    assert j.iso == "ERCOT"


def test_pima_county_az_is_non_iso_wecc(resolver):
    j = resolver.resolve(ADDRESSES["az"])
    assert (j.state, j.county_fips) == ("AZ", "04019")
    assert j.iso == "non-ISO (WECC)"
    assert j.nerc_regions == ["WECC"]


def test_unmatched_address_raises(resolver):
    with pytest.raises(UnresolvedAddressError):
        resolver.resolve("asdkjh qwe zzz")


def test_responses_are_cached(tmp_path):
    calls = []

    def handler(request):
        calls.append(1)
        return recorded(request)

    r = Resolver(client=httpx.Client(transport=httpx.MockTransport(handler)), cache_dir=tmp_path)
    r.resolve(ADDRESSES["md"])
    r.resolve(ADDRESSES["md"])
    assert len(calls) == 1


def test_iso_rule_uses_nerc_region_over_noisy_rto_flags():
    utils = [
        {"nerc_region": "WECC", "rtos": "ERCOT"},
        {"nerc_region": "WECC", "rtos": "CAISO"},
        {"nerc_region": "", "rtos": "CAISO;SPP;MISO"},
    ]
    assert iso_for(utils) == ("non-ISO (WECC)", ["non-ISO (WECC)"])
    assert iso_for(
        [{"nerc_region": "TRE", "rtos": "ERCOT"}, {"nerc_region": "SPP", "rtos": "SPP"}]
    )[1] == ["ERCOT", "SPP"]
    assert iso_for([])[0] == "unknown"


def test_resolve_endpoint_returns_422_for_bad_address(resolver):
    client = TestClient(create_app(Settings(), resolver=resolver))
    ok = client.get("/resolve", params={"address": ADDRESSES["md"]})
    assert ok.status_code == 200 and ok.json()["iso"] == "PJM"
    bad = client.get("/resolve", params={"address": "asdkjh qwe zzz"})
    assert bad.status_code == 422 and "address" in bad.json()["detail"].lower()
