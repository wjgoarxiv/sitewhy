import json
import threading
from collections.abc import Callable
from functools import cache
from pathlib import Path

from fastapi import FastAPI, HTTPException
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field

from app.config import Settings, load_settings
from app.geo import Resolver, UnresolvedAddressError
from app.orchestrator import Orchestrator, new_run_id
from app.screen import Screener

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
            r = json.loads(path.read_text())
            out.append({"name": path.stem, "address": r["project"]["address"],
                        "mw": r["project"]["mw"], "verdict": r["verdict"]})  # fmt: skip
        return out

    @app.get("/samples/{name}")
    def get_sample(name: str) -> dict:
        path = samples_dir / f"{name}.json"
        if not name.replace("-", "").replace("_", "").isalnum() or not path.is_file():
            raise HTTPException(404, "unknown sample")
        return json.loads(path.read_text())

    if WEB_DIR.is_dir():
        app.mount("/", StaticFiles(directory=WEB_DIR, html=True), name="web")
    return app


app = create_app()
