"""Re-record the four showcase runs live (Todo 9).

Usage: uv run python scripts/record_samples.py [name]
Runs each site (or one named site) at 300 MW, permits unknown, then writes
samples/<name>.json with a relative worldmodel_log plus
samples/<name>/worldmodel.jsonl, and warms data/geo/context.
"""

import json
import shutil
import sys
from pathlib import Path

from app.config import load_settings
from app.data import ZetarisHarness
from app.factory import build_orchestrator
from app.llm import ModelRouter

ROOT = Path(__file__).resolve().parent.parent
SAMPLES_DIR = ROOT / "samples"

SITES = {
    "md-washington-county-unincorporated": "13820 Pennsylvania Ave, Hagerstown MD 21742",
    "tx-abilene-ercot": "555 Walnut St, Abilene TX 79601",
    "az-tucson-pima": "255 W Alameda St, Tucson AZ 85701",
    "md-hagerstown-city": "100 W Washington St, Hagerstown MD 21740",
}


def preflight(settings) -> None:
    router = ModelRouter(settings)
    if router.status() != "online":
        print(f"BLOCKED: Nightshift is {router.status()} at {settings.nightshift_base_url}")
        sys.exit(2)
    try:
        ZetarisHarness(settings).query("SELECT 1")
    except Exception as exc:  # noqa: BLE001 - report the named blocker, then stop
        print(f"BLOCKED: Zetaris unreachable: {exc}")
        sys.exit(2)


def record(name: str, address: str) -> dict:
    report = build_orchestrator().run(address, 300.0, permits_submitted=None)
    sample_dir = SAMPLES_DIR / name
    sample_dir.mkdir(parents=True, exist_ok=True)
    shutil.copyfile(ROOT / report["worldmodel_log"], sample_dir / "worldmodel.jsonl")
    report["worldmodel_log"] = f"samples/{name}/worldmodel.jsonl"
    (SAMPLES_DIR / f"{name}.json").write_text(json.dumps(report, indent=1, default=str))
    jurisdiction = report.get("jurisdiction") or {}
    try:
        from app.sitecontext import SiteContext

        SiteContext().context(
            float(jurisdiction["lat"]), float(jurisdiction["lon"]), str(jurisdiction["county_fips"])
        )
    except Exception as exc:  # noqa: BLE001 - context is visual only, never fatal
        print(f"  context warm failed for {name}: {exc}")
    return report


def main() -> None:
    settings = load_settings()
    preflight(settings)
    names = sys.argv[1:]
    for name in names:
        if name not in SITES:
            print(f"unknown sample {name!r}; expected one of {sorted(SITES)}")
            sys.exit(2)
    for name in names or SITES:
        address = SITES[name]
        print(f"recording {name}: {address}", flush=True)
        report = record(name, address)
        print(f"  verdict={report['verdict']} findings={len(report['findings'])}")


if __name__ == "__main__":
    main()
