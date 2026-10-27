"""Run one screening from an input JSON file.

Usage:
    python run.py --input input_examples/md-washington-county-unincorporated.json --sample

With --sample the run replays the committed caches (geocode, sources, LLM) and
needs no credentials, Zetaris or Nightshift. Without it, live credentials from
the environment apply. The report JSON goes to stdout and to
output_examples/<input stem>.json; the agent trace goes to
logs/<run_id>.jsonl (one JSON object per line) and is echoed to stderr so
stdout stays machine-readable.
"""

import argparse
import json
import sys
from dataclasses import replace
from pathlib import Path

ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT))

from app.config import load_settings  # noqa: E402
from app.factory import build_orchestrator  # noqa: E402
from app.geo import UnresolvedAddressError  # noqa: E402
from app.llm import SampleMissError  # noqa: E402
from app.orchestrator import new_run_id  # noqa: E402
from app.trace import trace_events  # noqa: E402


def parse_args(argv=None):
    parser = argparse.ArgumentParser(description="Run one SiteWhy screening.")
    parser.add_argument("--input", required=True, help="input JSON file")
    parser.add_argument("--sample", action="store_true",
                        help="replay committed caches; no credentials needed")
    parser.add_argument("--output", default=None, help="report output path")
    parser.add_argument("--logs-dir", default=None, help="trace output directory")
    return parser.parse_args(argv)


def main(argv=None) -> int:
    args = parse_args(argv)
    try:
        payload = json.loads(Path(args.input).read_text())
    except (OSError, json.JSONDecodeError) as exc:
        print(f"cannot read input {args.input}: {exc}", file=sys.stderr)
        return 2
    settings = load_settings()
    if args.sample:
        settings = replace(settings, sample_mode=True)
    try:
        orchestrator = build_orchestrator(settings)
        if payload.get("address"):
            report = orchestrator.run(
                payload["address"], payload.get("mw", 300),
                permits_submitted=payload.get("permits_submitted"),
                run_id=new_run_id(),
            )
        else:
            report = orchestrator.run(
                None, payload.get("mw", 300),
                permits_submitted=payload.get("permits_submitted"),
                run_id=new_run_id(),
                lat=payload["lat"], lon=payload["lon"],
            )
    except (UnresolvedAddressError, SampleMissError) as exc:
        print(f"sample-mode cache miss: {exc}", file=sys.stderr)
        return 1
    out_path = Path(args.output) if args.output else (
        ROOT / "output_examples" / (Path(args.input).stem + ".json")
    )
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(json.dumps(report, indent=1, default=str))
    logs_dir = Path(args.logs_dir) if args.logs_dir else ROOT / "logs"
    logs_dir.mkdir(parents=True, exist_ok=True)
    trace_path = logs_dir / f"{report['run_id']}.jsonl"
    with trace_path.open("w") as fh:
        for row in trace_events(report):
            line = json.dumps(row, default=str)
            fh.write(line + "\n")
            print(line, file=sys.stderr)
    print(json.dumps(report, indent=1, default=str))
    return 0


if __name__ == "__main__":
    sys.exit(main())
