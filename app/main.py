from fastapi import FastAPI, HTTPException

from app.config import Settings, load_settings
from app.geo import Resolver, UnresolvedAddressError


def create_app(settings: Settings | None = None, resolver: Resolver | None = None) -> FastAPI:
    settings = settings or load_settings()
    resolver = resolver or Resolver()
    app = FastAPI(title="SiteWhy")

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

    return app


app = create_app()
