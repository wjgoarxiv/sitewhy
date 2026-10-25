"""Site context: county/city boundaries (Census TIGERweb) and lines (HIFLD).

Public map services, no key. Each part is cached under ``data/geo/context/``
keyed by a sha of the query (lat/lon rounded to 4 decimals); the cache is read
first and never expires. Parts fail independently: a failing part returns null
plus an entry in ``errors`` while the other parts are still served.
"""

import hashlib
import json
from pathlib import Path

import httpx

ROOT = Path(__file__).resolve().parent.parent
DEFAULT_CACHE_DIR = ROOT / "data/geo/context"

TIGERWEB_BASE = (
    "https://tigerweb.geo.census.gov/arcgis/rest/services/TIGERweb/tigerWMS_Current/MapServer"
)
HIFLD_BASE = (
    "https://services1.arcgis.com/Hp6G80Pky0om7QvQ/arcgis/rest/services"
    "/Electric_Power_Transmission_Lines/FeatureServer/0"
)

SOURCES = [
    {
        "part": "county",
        "attribution": "County boundaries: U.S. Census Bureau TIGERweb "
        "(tigerWMS_Current, layer 82 Counties)",
        "url": f"{TIGERWEB_BASE}/82",
    },
    {
        "part": "place",
        "attribution": "City limits: U.S. Census Bureau TIGERweb "
        "(tigerWMS_Current, layer 28 Incorporated Places)",
        "url": f"{TIGERWEB_BASE}/28",
    },
    {
        "part": "transmission",
        "attribution": "Transmission lines: Homeland Infrastructure "
        "Foundation-Level Data (HIFLD), Electric Power Transmission Lines",
        "url": HIFLD_BASE,
    },
]

_MISS = object()


class InvalidContextQuery(ValueError):
    pass


def _validate(lat: float, lon: float, county_fips: str) -> tuple[float, float, str]:
    try:
        lat, lon = float(lat), float(lon)
    except (TypeError, ValueError) as exc:
        raise InvalidContextQuery(f"lat/lon must be numbers: {lat!r}, {lon!r}") from exc
    fips = str(county_fips or "")
    if not 18 <= lat <= 72:
        raise InvalidContextQuery(f"lat {lat} out of range 18..72")
    if not -180 <= lon <= -60:
        raise InvalidContextQuery(f"lon {lon} out of range -180..-60")
    if len(fips) != 5 or not fips.isdigit():
        raise InvalidContextQuery(f"county_fips {fips!r} must be exactly 5 digits")
    return lat, lon, fips


class SiteContext:
    def __init__(
        self, client: httpx.Client | None = None, cache_dir: Path = DEFAULT_CACHE_DIR
    ):
        self.client = client or httpx.Client(timeout=30.0)
        self.cache_dir = Path(cache_dir)

    def _path(self, kind: str, key: str) -> Path:
        digest = hashlib.sha256(key.encode()).hexdigest()[:16]
        return self.cache_dir / f"{kind}-{digest}.json"

    def _read(self, path: Path):
        try:
            if path.is_file():
                return json.loads(path.read_text())
        except (OSError, ValueError):
            pass
        return _MISS

    def _write(self, path: Path, data) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(data))

    def _fetch(self, url: str, params: dict, timeout: float | None = None):
        kwargs = {"params": params}
        if timeout is not None:
            kwargs["timeout"] = timeout
        resp = self.client.get(url, **kwargs)
        resp.raise_for_status()
        return resp.json()

    def context(self, lat: float, lon: float, county_fips: str) -> dict:
        lat, lon, fips = _validate(lat, lon, county_fips)
        lat4, lon4 = round(lat, 4), round(lon, 4)
        errors: list[dict] = []

        county_path = self._path("county", f"county:{fips}")
        county = self._read(county_path)
        if county is _MISS:
            try:
                data = self._fetch(
                    f"{TIGERWEB_BASE}/82/query",
                    {
                        "where": f"GEOID='{fips}'",
                        "outFields": "*",
                        "outSR": "4326",
                        "maxAllowableOffset": "0.002",
                        "geometryPrecision": "5",
                        "f": "geojson",
                    },
                )
                county = data if data.get("features") else None
                if county is None:
                    errors.append({"part": "county", "error": f"no county for GEOID {fips}"})
                else:
                    self._write(county_path, county)
            except Exception as exc:  # noqa: BLE001 - one part must not kill the others
                county, errors = None, [*errors, {"part": "county", "error": str(exc)[:200]}]

        place_path = self._path("place", f"place:{lat4},{lon4}")
        place = self._read(place_path)
        if place is _MISS:
            try:
                data = self._fetch(
                    f"{TIGERWEB_BASE}/28/query",
                    {
                        "geometry": f"{lon4},{lat4}",
                        "geometryType": "esriGeometryPoint",
                        "inSR": "4326",
                        "spatialRel": "esriSpatialRelIntersects",
                        "outFields": "*",
                        "outSR": "4326",
                        "maxAllowableOffset": "0.002",
                        "geometryPrecision": "5",
                        "f": "geojson",
                    },
                )
                feats = data.get("features") or []
                place = feats[0] if feats else None
                self._write(place_path, place)
            except Exception as exc:  # noqa: BLE001 - one part must not kill the others
                place, errors = None, [*errors, {"part": "place", "error": str(exc)[:200]}]

        trans_path = self._path("transmission", f"transmission:{lat4},{lon4}")
        transmission = self._read(trans_path)
        if transmission is _MISS:
            try:
                envelope = f"{lon4 - 0.12},{lat4 - 0.12},{lon4 + 0.12},{lat4 + 0.12}"
                transmission = self._fetch(
                    f"{HIFLD_BASE}/query",
                    {
                        "geometry": envelope,
                        "geometryType": "esriGeometryEnvelope",
                        "inSR": "4326",
                        "spatialRel": "esriSpatialRelIntersects",
                        "outFields": "VOLTAGE,OWNER,STATUS",
                        "outSR": "4326",
                        "maxAllowableOffset": "0.0005",
                        "resultRecordCount": "300",
                        "returnGeometry": "true",
                        "f": "geojson",
                    },
                    timeout=10.0,
                )
                self._write(trans_path, transmission)
            except Exception as exc:  # noqa: BLE001 - visual context only, degrade gracefully
                transmission, errors = (
                    None,
                    [*errors, {"part": "transmission", "error": str(exc)[:200]}],
                )

        return {
            "query": {"lat": lat, "lon": lon, "county_fips": fips},
            "county": county,
            "place": place,
            "transmission": transmission,
            "errors": errors,
            "sources": SOURCES,
            "google_maps_url": f"https://www.google.com/maps/search/?api=1&query={lat},{lon}",
        }
