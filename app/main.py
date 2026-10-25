from functools import cache

from fastapi import FastAPI, HTTPException
from pydantic import BaseModel, Field

from app.config import Settings, load_settings
from app.data import DuckDbHarness, FallbackHarness, HarnessError, ZetarisHarness
from app.geo import Resolver, UnresolvedAddressError
from app.llm import ModelRouter
from app.screen import Screener
from app.seed import register_seed


class ScreenRequest(BaseModel):
    address: str
    mw: float = Field(gt=0, le=10000)


def build_screener(settings: Settings, resolver: Resolver) -> Screener:
    duck = DuckDbHarness()
    register_seed(duck)
    zetaris = ZetarisHarness(settings)
    harness = FallbackHarness(zetaris, duck)
    try:
        register_seed(zetaris)
    except (HarnessError, OSError) as exc:
        harness.trace.append({"backend": "zetaris", "status": "BLOCKED", "error": str(exc)[:200]})
    return Screener(resolver, harness, ModelRouter(settings))


def create_app(
    settings: Settings | None = None,
    resolver: Resolver | None = None,
    screener: Screener | None = None,
) -> FastAPI:
    settings = settings or load_settings()
    resolver = resolver or Resolver()
    app = FastAPI(title="SiteWhy")

    @cache
    def get_screener() -> Screener:
        return screener or build_screener(settings, resolver)

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

    return app


app = create_app()
