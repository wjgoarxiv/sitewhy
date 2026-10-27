import json
import re
import threading
from collections.abc import Callable
from functools import cache
from pathlib import Path

from fastapi import FastAPI, HTTPException
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field, model_validator

from app.config import Settings, load_settings
from app.explain import enrich
from app.geo import Resolver, UnresolvedAddressError
from app.orchestrator import RUNS_DIR, Orchestrator, new_run_id
from app.screen import Screener
from app.sitecontext import SiteContext

ROOT = Path(__file__).resolve().parent.parent
SAMPLES_DIR = ROOT / "samples"
WEB_DIR = ROOT / "web"
RUN_ID_RE = re.compile(r"^[0-9TZ]+-[0-9a-f]{6}$")


class ScreenRequest(BaseModel):
    address: str
    mw: float = Field(gt=0, le=10000)


class RunRequest(BaseModel):
    address: str | None = None
    lat: float | None = None
    lon: float | None = None
    mw: float = Field(gt=0, le=10000)
    permits_submitted: bool | None = None

    @model_validator(mode="after")
    def exactly_one_target(self):
        has_address = bool(self.address and self.address.strip())
        has_lat = self.lat is not None
        has_lon = self.lon is not None
        if has_lat != has_lon or has_address == (has_lat and has_lon):
            raise ValueError("provide either address or lat+lon")
        if has_lat and not (18 <= self.lat <= 72 and -180 <= self.lon <= -60):
            raise ValueError("lat/lon outside the US range (lat 18..72, lon -180..-60)")
        return self


def create_app(
    settings: Settings | None = None,
    resolver: Resolver | None = None,
    screener: Screener | None = None,
    orchestrator_factory: Callable[[], Orchestrator] | None = None,
    samples_dir: Path = SAMPLES_DIR,
    runs_dir: Path | None = None,
) -> FastAPI:
    settings = settings or load_settings()
    resolver = resolver or Resolver()
    app = FastAPI(title="SiteWhy")
    runs: dict[str, dict] = {}
    run_lock = threading.Lock()
    state_lock = threading.Lock()
    runs_dir = Path(runs_dir) if runs_dir is not None else RUNS_DIR

    @cache
    def get_screener() -> Screener:
        if screener:
            return screener
        from app.factory import build_harness
        from app.llm import ModelRouter

        return Screener(resolver, build_harness(settings), ModelRouter(settings))

    @cache
    def get_orchestrator() -> Orchestrator:
        if orchestrator_factory:
            return orchestrator_factory()
        from app.factory import build_orchestrator

        return build_orchestrator(settings)

    @app.get("/health")
    def health() -> dict:
        return {"status": "ok"}

    @app.get("/status")
    def status() -> dict:
        def state(configured: bool) -> str:
            return "configured" if configured else "not configured"

        return {
            "nightshift": state(settings.nightshift_configured),
            "zetaris": state(settings.zetaris_configured),
            "sample_mode": settings.sample_mode,
        }

    @app.get("/resolve")
    def resolve(address: str) -> dict:
        try:
            return resolver.resolve(address).to_dict()
        except UnresolvedAddressError as exc:
            raise HTTPException(status_code=422, detail=str(exc)) from exc

    @app.post("/screen")
    def screen(req: ScreenRequest) -> dict:
        try:
            return get_screener().screen(req.address, req.mw)
        except UnresolvedAddressError as exc:
            raise HTTPException(status_code=422, detail=str(exc)) from exc

    def execute(run_id: str, req: RunRequest) -> None:
        try:
            with state_lock:
                state = runs[run_id]
            try:
                if req.address is not None:
                    report = get_orchestrator().run(
                        req.address,
                        req.mw,
                        permits_submitted=req.permits_submitted,
                        run_id=run_id,
                        on_event=state["events"].append,
                    )
                else:
                    report = get_orchestrator().run(
                        None,
                        req.mw,
                        permits_submitted=req.permits_submitted,
                        run_id=run_id,
                        on_event=state["events"].append,
                        lat=req.lat,
                        lon=req.lon,
                    )
                with state_lock:
                    state["report"] = report
                    state["status"] = "done"
            except UnresolvedAddressError as exc:
                with state_lock:
                    state.update(status="error", error=str(exc))
            except Exception as exc:  # noqa: BLE001 - surfaced to the UI, run thread must not die
                with state_lock:
                    state.update(status="error", error=f"{type(exc).__name__}: {exc}"[:500])
        finally:
            run_lock.release()

    @app.post("/runs", status_code=202)
    def start_run(req: RunRequest) -> dict:
        if settings.sample_mode:
            raise HTTPException(503, "SAMPLE_MODE is on: live runs are disabled; open a sample")
        if not run_lock.acquire(blocking=False):
            raise HTTPException(409, "A screening is already running")
        run_id = new_run_id()
        with state_lock:
            runs[run_id] = {"status": "running", "events": [], "request": req.model_dump()}
        threading.Thread(target=execute, args=(run_id, req), daemon=True).start()
        return {"run_id": run_id}

    @app.get("/runs/{run_id}")
    def get_run(run_id: str) -> dict:
        if not RUN_ID_RE.match(run_id):
            raise HTTPException(404, "unknown run")
        if run_id in runs:
            with state_lock:
                state = dict(runs[run_id])
            return {"run_id": run_id, **state}
        path = runs_dir / run_id / "report.json"
        if not path.is_file():
            raise HTTPException(404, "unknown run")
        report = enrich(json.loads(path.read_text()))
        return {
            "run_id": run_id,
            "status": "done",
            "events": report.get("events", []),
            "report": report,
        }

    def portfolio_row(entry_id: str, kind: str, report: dict) -> dict:
        report = enrich(report)
        jurisdiction = report.get("jurisdiction") or {}
        events = report.get("events") or []
        created = next((e["at"] for e in events if e.get("at")), report.get("run_id", ""))
        return {
            "id": entry_id,
            "kind": kind,
            "address": report["project"]["address"],
            "mw": report["project"]["mw"],
            "verdict": report["verdict"],
            "headline": report["explanation"]["headline"],
            "lat": jurisdiction.get("lat"),
            "lon": jurisdiction.get("lon"),
            "county": jurisdiction.get("county_name"),
            "created": created,
        }

    @app.get("/portfolio")
    def portfolio() -> list[dict]:
        rows = []
        for path in sorted(samples_dir.glob("*.json")):
            rows.append(
                portfolio_row(path.stem, "showcase", json.loads(path.read_text()))
            )
        if runs_dir.is_dir():
            for child in sorted(
                (p for p in runs_dir.iterdir() if (p / "report.json").is_file()),
                reverse=True,
            ):
                try:
                    rows.append(
                        portfolio_row(
                            child.name, "live",
                            json.loads((child / "report.json").read_text()),
                        )
                    )
                except (KeyError, TypeError):
                    # One corrupt live report must not break the portfolio.
                    continue
        return rows

    @app.get("/samples")
    def list_samples() -> list[dict]:
        out = []
        for path in sorted(samples_dir.glob("*.json")):
            r = enrich(json.loads(path.read_text()))
            jurisdiction = r.get("jurisdiction") or {}
            out.append({
                "name": path.stem,
                "address": r["project"]["address"],
                "mw": r["project"]["mw"],
                "verdict": r["verdict"],
                "lat": jurisdiction.get("lat"),
                "lon": jurisdiction.get("lon"),
                "headline": r["explanation"]["headline"],
                "county": jurisdiction.get("county_name"),
            })
        return out

    @app.get("/samples/{name}")
    def get_sample(name: str) -> dict:
        path = samples_dir / f"{name}.json"
        if not name.replace("-", "").replace("_", "").isalnum() or not path.is_file():
            raise HTTPException(404, "unknown sample")
        return enrich(json.loads(path.read_text()))

    def site_context() -> SiteContext:
        override = getattr(app.state, "site_context", None)
        return override if override is not None else SiteContext()

    def context_for(lat, lon, county_fips) -> dict:
        try:
            return site_context().context(lat, lon, county_fips)
        except ValueError as exc:
            raise HTTPException(status_code=422, detail=str(exc)) from exc

    @app.get("/context")
    def get_context(lat: float, lon: float, county_fips: str) -> dict:
        return context_for(lat, lon, county_fips)

    @app.get("/samples/{name}/context")
    def get_sample_context(name: str) -> dict:
        path = samples_dir / f"{name}.json"
        if not name.replace("-", "").replace("_", "").isalnum() or not path.is_file():
            raise HTTPException(404, "unknown sample")
        jurisdiction = json.loads(path.read_text()).get("jurisdiction") or {}
        try:
            lat = float(jurisdiction["lat"])
            lon = float(jurisdiction["lon"])
            county_fips = str(jurisdiction["county_fips"])
        except (KeyError, TypeError, ValueError) as exc:
            raise HTTPException(404, "sample has no jurisdiction") from exc
        return context_for(lat, lon, county_fips)

    @app.get("/runs/{run_id}/context")
    def get_run_context(run_id: str) -> dict:
        if not RUN_ID_RE.match(run_id):
            raise HTTPException(404, "unknown run")
        report: dict = {}
        if run_id in runs:
            report = runs[run_id].get("report") or {}
        else:
            path = runs_dir / run_id / "report.json"
            if path.is_file():
                report = enrich(json.loads(path.read_text()))
        if not report:
            raise HTTPException(404, "unknown run")
        jurisdiction = report.get("jurisdiction") or {}
        if "lat" not in jurisdiction or "county_fips" not in jurisdiction:
            raise HTTPException(409, "run not ready")
        return context_for(jurisdiction["lat"], jurisdiction["lon"], jurisdiction["county_fips"])

    if WEB_DIR.is_dir():
        app.mount("/", StaticFiles(directory=WEB_DIR, html=True), name="web")
    return app


app = create_app()
