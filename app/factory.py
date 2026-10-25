"""Wire the live components: Zetaris (DuckDB fallback), Census, Nightshift, fetcher."""

from app.config import Settings, load_settings
from app.data import DuckDbHarness, FallbackHarness, HarnessError, ZetarisHarness
from app.evidence import EvidenceFetcher
from app.geo import Resolver
from app.llm import ModelRouter
from app.orchestrator import Orchestrator
from app.seed import register_seed


def build_harness(settings: Settings) -> FallbackHarness:
    duck = DuckDbHarness()
    register_seed(duck)
    zetaris = ZetarisHarness(settings)
    harness = FallbackHarness(zetaris, duck)
    try:
        register_seed(zetaris)
    except (HarnessError, OSError) as exc:
        harness.trace.append({"backend": "zetaris", "status": "BLOCKED", "error": str(exc)[:200]})
    return harness


def build_orchestrator(settings: Settings | None = None) -> Orchestrator:
    settings = settings or load_settings()
    return Orchestrator(
        Resolver(), build_harness(settings), ModelRouter(settings), EvidenceFetcher()
    )
