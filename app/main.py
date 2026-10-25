from fastapi import FastAPI

from app.config import Settings, load_settings


def create_app(settings: Settings | None = None) -> FastAPI:
    settings = settings or load_settings()
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

    return app


app = create_app()
