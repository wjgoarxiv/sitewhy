"""Run the full multi-agent screen from the command line.

Usage: uv run python scripts/run_screen.py "<address>" <mw> [--permits-submitted yes|no]
"""

import argparse
import json

from app.config import load_settings
from app.data import DuckDbHarness, FallbackHarness, HarnessError, ZetarisHarness
from app.evidence import EvidenceFetcher
from app.geo import Resolver
from app.llm import ModelRouter
from app.orchestrator import Orchestrator
from app.seed import register_seed


def build(settings=None) -> Orchestrator:
    settings = settings or load_settings()
    duck = DuckDbHarness()
    register_seed(duck)
    zetaris = ZetarisHarness(settings)
    harness = FallbackHarness(zetaris, duck)
    try:
        register_seed(zetaris)
    except (HarnessError, OSError) as exc:
        harness.trace.append({"backend": "zetaris", "status": "BLOCKED", "error": str(exc)[:200]})
    return Orchestrator(Resolver(), harness, ModelRouter(settings), EvidenceFetcher())


def main() -> None:
    p = argparse.ArgumentParser()
    p.add_argument("address")
    p.add_argument("mw", type=float)
    p.add_argument("--permits-submitted", choices=["yes", "no"])
    a = p.parse_args()
    permits = None if a.permits_submitted is None else a.permits_submitted == "yes"
    r = build().run(a.address, a.mw, permits_submitted=permits)
    print(f"verdict: {r['verdict']}\nwhy: {r['why']}")
    for f in r["findings"]:
        print(f"  [{f['grade']}] {f['rule_id']}: applies={f['applies']} - {f['reason']}")
    for o in r["needs_confirmation"]:
        print(f"  needs confirmation: {o['rule_id']} ({o['type']}): {o['text']}")
    print("guard:", r["guard_notes"])
    print("events:", json.dumps([(e["round"], e["role"], e["action"]) for e in r["events"]]))
    print("models:", sorted({(t["role"], t["model"].split("/")[-1]) for t in r["model_trace"]}))
    print("data:", [(t["backend"], t["status"]) for t in r["data_trace"]][:3])
    print("log:", r["worldmodel_log"])


if __name__ == "__main__":
    main()
