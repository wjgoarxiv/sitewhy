"""Jurisdiction resolver: US address -> state, county, place, utilities, ISO/RTO.

Geography comes from the Census Geocoder (free, no key). Utilities and markets
come from EIA-861 2025 service territories (data/geo/eia861_county_utilities.csv,
built by scripts/build_geo.py for the covered states).
"""

import csv
import hashlib
import json
from collections import Counter
from dataclasses import asdict, dataclass, field
from pathlib import Path

import httpx

ROOT = Path(__file__).resolve().parent.parent
CENSUS_URL = "https://geocoding.geo.census.gov/geocoder/geographies/onelineaddress"
CENSUS_PARAMS = {
    "benchmark": "Public_AR_Current",
    "vintage": "Current_Current",
    "layers": "Counties,States,Incorporated Places,County Subdivisions",
    "format": "json",
}
COORDS_URL = "https://geocoding.geo.census.gov/geocoder/geographies/coordinates"
COORDS_PARAMS = {"benchmark": "Public_AR_Current", "vintage": "Current_Current", "format": "json"}
UTILITIES_CSV = ROOT / "data/geo/eia861_county_utilities.csv"
DEFAULT_CACHE_DIR = ROOT / "data/geo/cache"
STATE_ABBR = {
    "01": "AL", "02": "AK", "04": "AZ", "05": "AR", "06": "CA", "08": "CO", "09": "CT",
    "10": "DE", "11": "DC", "12": "FL", "13": "GA", "15": "HI", "16": "ID", "17": "IL",
    "18": "IN", "19": "IA", "20": "KS", "21": "KY", "22": "LA", "23": "ME", "24": "MD",
    "25": "MA", "26": "MI", "27": "MN", "28": "MS", "29": "MO", "30": "MT", "31": "NE",
    "32": "NV", "33": "NH", "34": "NJ", "35": "NM", "36": "NY", "37": "NC", "38": "ND",
    "39": "OH", "40": "OK", "41": "OR", "42": "PA", "44": "RI", "45": "SC", "46": "SD",
    "47": "TN", "48": "TX", "49": "UT", "50": "VT", "51": "VA", "53": "WA", "54": "WV",
    "55": "WI", "56": "WY",
}  # fmt: skip
EASTERN_RTOS = ["PJM", "MISO", "SPP", "NYISO", "ISONE"]


class UnresolvedAddressError(ValueError):
    pass


@dataclass
class Jurisdiction:
    matched_address: str
    lat: float
    lon: float
    state: str
    state_fips: str
    county_name: str
    county_fips: str
    place: str | None
    county_subdivision: str | None
    utilities: list[dict] = field(default_factory=list)
    nerc_regions: list[str] = field(default_factory=list)
    iso: str = "unknown"
    iso_candidates: list[str] = field(default_factory=list)

    @property
    def multiple_utilities(self) -> bool:
        return len(self.utilities) > 1

    def to_dict(self) -> dict:
        return {**asdict(self), "multiple_utilities": self.multiple_utilities}


def _market(utility: dict) -> str | None:
    """Market a utility sits in. NERC region decides, because EIA's RTO flags also
    mark wholesale participation (e.g. WECC utilities flagged CAISO or ERCOT)."""
    nerc = utility.get("nerc_region") or ""
    rtos = (utility.get("rtos") or "").split(";")
    if nerc == "TRE":
        return "ERCOT"
    if nerc == "WECC":
        return "CAISO" if "CAISO" in rtos and utility.get("state") == "CA" else "non-ISO (WECC)"
    if nerc:
        return next((r for r in EASTERN_RTOS if r in rtos), f"non-ISO ({nerc})")
    return None


def iso_for(utilities: list[dict]) -> tuple[str, list[str]]:
    counts = Counter(m for m in map(_market, utilities) if m)
    if not counts:
        return "unknown", []
    return counts.most_common(1)[0][0], sorted(counts)


def _load_utilities() -> dict[tuple[str, str], list[dict]]:
    by_county: dict[tuple[str, str], list[dict]] = {}
    if UTILITIES_CSV.is_file():
        with UTILITIES_CSV.open() as f:
            for row in csv.DictReader(f):
                by_county.setdefault((row["state"], row["county"].lower()), []).append(row)
    return by_county


def _county_key(name: str) -> str:
    for suffix in (" County", " Parish", " Borough"):
        name = name.removesuffix(suffix)
    return name.lower()


class Resolver:
    def __init__(
        self,
        client: httpx.Client | None = None,
        cache_dir: Path = DEFAULT_CACHE_DIR,
        sample_mode: bool = False,
    ):
        self.client = client or httpx.Client(timeout=60)
        self.cache_dir = Path(cache_dir)
        self.sample_mode = sample_mode
        self.utilities = _load_utilities()

    def _geocode(self, address: str) -> dict:
        key = hashlib.sha256(address.strip().lower().encode()).hexdigest()[:24]
        cache = self.cache_dir / f"census-{key}.json"
        if cache.is_file():
            return json.loads(cache.read_text())
        if self.sample_mode:
            raise UnresolvedAddressError(
                f"Address {address!r} is not in the sample-mode geocode cache "
                "(SAMPLE_MODE serves only cached inputs; see input_examples/)."
            )
        resp = self.client.get(CENSUS_URL, params={**CENSUS_PARAMS, "address": address})
        resp.raise_for_status()
        data = resp.json()
        self.cache_dir.mkdir(parents=True, exist_ok=True)
        cache.write_text(json.dumps(data))
        return data

    def _jurisdiction(
        self, geo: dict, matched_address: str, lat: float, lon: float
    ) -> Jurisdiction:
        counties = geo.get("Counties") or []
        if not counties:
            raise UnresolvedAddressError("No county found for this location (Census Geocoder).")
        county = counties[0]
        state = STATE_ABBR.get(county["STATE"], county["STATE"])
        place = (geo.get("Incorporated Places") or [{}])[0].get("NAME")
        subdivision = (geo.get("County Subdivisions") or [{}])[0].get("NAME")
        rows = self.utilities.get((state, _county_key(county["NAME"])), [])
        utilities = [
            {
                "name": r["utility_name"],
                "eia_id": r["utility_number"],
                "ownership": r["ownership"],
                "nerc_region": r["nerc_region"],
                "rtos": r["rtos"],
                "state": state,
            }
            for r in rows
        ]
        iso, candidates = iso_for(utilities)
        return Jurisdiction(
            matched_address=matched_address,
            lat=lat,
            lon=lon,
            state=state,
            state_fips=county["STATE"],
            county_name=county["NAME"],
            county_fips=county["GEOID"],
            place=place,
            county_subdivision=None if place else subdivision,
            utilities=utilities,
            nerc_regions=sorted({u["nerc_region"] for u in utilities if u["nerc_region"]}),
            iso=iso,
            iso_candidates=candidates,
        )

    def resolve(self, address: str) -> Jurisdiction:
        matches = self._geocode(address).get("result", {}).get("addressMatches") or []
        if not matches:
            raise UnresolvedAddressError(
                f"Could not match address {address!r} to a US location (Census Geocoder)."
            )
        m = matches[0]
        return self._jurisdiction(
            m["geographies"], m["matchedAddress"], m["coordinates"]["y"], m["coordinates"]["x"]
        )

    def resolve_point(self, lat: float, lon: float) -> Jurisdiction:
        if not (18 <= lat <= 72 and -180 <= lon <= -60):
            raise UnresolvedAddressError(
                f"Coordinates ({lat}, {lon}) are outside the US range "
                "(lat 18..72, lon -180..-60)."
            )
        key = hashlib.sha256(f"point:{lat},{lon}".encode()).hexdigest()[:24]
        cache = self.cache_dir / f"census-{key}.json"
        if cache.is_file():
            data = json.loads(cache.read_text())
        elif self.sample_mode:
            raise UnresolvedAddressError(
                f"Coordinates ({lat}, {lon}) are not in the sample-mode geocode cache "
                "(SAMPLE_MODE serves only cached inputs; see input_examples/)."
            )
        else:
            resp = self.client.get(COORDS_URL, params={**COORDS_PARAMS, "x": lon, "y": lat})
            resp.raise_for_status()
            data = resp.json()
            self.cache_dir.mkdir(parents=True, exist_ok=True)
            cache.write_text(json.dumps(data))
        geo = data.get("result", {}).get("geographies") or {}
        counties = geo.get("Counties") or []
        if not counties:
            raise UnresolvedAddressError(
                f"Could not match coordinates ({lat}, {lon}) to a US county."
            )
        state = STATE_ABBR.get(counties[0]["STATE"], counties[0]["STATE"])
        matched = f"{lat}, {lon} ({counties[0]['NAME']}, {state})"
        return self._jurisdiction(geo, matched, lat, lon)
