import json
import threading
from collections.abc import Callable
from functools import cache
from pathlib import Path

from fastapi import FastAPI, HTTPException
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field

from app.config import Settings, load_settings
from app.explain import enrich
from app.geo import Resolver, UnresolvedAddressError
from app.orchestrator import Orchestrator, new_run_id
from app.screen import Screener
from app.sitecontext import SiteContext

ROOT = Path(__file__).resolve().parent.parent
SAMPLES_DIR = ROOT / "samples"
WEB_DIR = ROOT / "web"


class ScreenRequest(BaseModel):
    address: str
    mw: float = Field(gt=0, le=10000)


class RunRequest(ScreenRequest):
    permits_submitted: bool | None = None


def create_app(
    settings: Settings | None = None,
    resolver: Resolver | None = None,
    screener: Screener | None = None,
    orchestrator_factory: Callable[[], Orchestrator] | None = None,
    samples_dir: Path = SAMPLES_DIR,
) -> FastAPI:
    settings = settings or load_settings()
    resolver = resolver or Resolver()
    app = FastAPI(title="SiteWhy")
    runs: dict[str, dict] = {}
    run_lock = threading.Lock()

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
        state = runs[run_id]
        with run_lock:
            try:
                state["report"] = get_orchestrator().run(
                    req.address,
                    req.mw,
                    permits_submitted=req.permits_submitted,
                    run_id=run_id,
                    on_event=state["events"].append,
                )
                state["status"] = "done"
            except UnresolvedAddressError as exc:
                state.update(status="error", error=str(exc))
            except Exception as exc:  # noqa: BLE001 - surfaced to the UI, run thread must not die
                state.update(status="error", error=f"{type(exc).__name__}: {exc}"[:500])

    @app.post("/runs", status_code=202)
    def start_run(req: RunRequest) -> dict:
        if settings.sample_mode:
            raise HTTPException(503, "SAMPLE_MODE is on: live runs are disabled; open a sample")
        run_id = new_run_id()
        runs[run_id] = {"status": "running", "events": [], "request": req.model_dump()}
        threading.Thread(target=execute, args=(run_id, req), daemon=True).start()
        return {"run_id": run_id}

    @app.get("/runs/{run_id}")
    def get_run(run_id: str) -> dict:
        if run_id not in runs:
            raise HTTPException(404, "unknown run")
        return {"run_id": run_id, **runs[run_id]}

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
        if run_id not in runs:
            raise HTTPException(404, "unknown run")
        report = runs[run_id].get("report") or {}
        jurisdiction = report.get("jurisdiction") or {}
        if "lat" not in jurisdiction or "county_fips" not in jurisdiction:
            raise HTTPException(409, "run not ready")
        return context_for(jurisdiction["lat"], jurisdiction["lon"], jurisdiction["county_fips"])

    if WEB_DIR.is_dir():
        app.mount("/", StaticFiles(directory=WEB_DIR, html=True), name="web")
    return app


app = create_app()
