"""Run one screening from an input JSON file.

Usage:
    python run.py --input input_examples/md-washington-county-unincorporated.json --sample

With --sample the run replays the committed caches (geocode, sources, LLM) and
needs no credentials, Zetaris or Nightshift. Without it, live credentials from
the environment apply. The report JSON goes to stdout and to logs/<run_id>.json
unless --output names a path. The agent trace goes to
output_examples/traces/<input stem>.jsonl (one JSON object per line, committed
as the reference trace) and is echoed to stderr so stdout stays
machine-readable; --logs-dir writes the trace to <dir>/<run_id>.jsonl instead
for local runs.
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
from app.llm import NotConfiguredError, ProviderError, SampleMissError  # noqa: E402
from app.orchestrator import new_run_id  # noqa: E402
from app.trace import trace_events  # noqa: E402


def parse_args(argv=None):
    parser = argparse.ArgumentParser(description="Run one SiteWhy screening.")
    parser.add_argument("--input", required=True, help="input JSON file")
    parser.add_argument("--sample", action="store_true",
                        help="replay committed caches; no credentials needed")
    parser.add_argument("--output", default=None,
                        help="report output path (default logs/<run_id>.json)")
    parser.add_argument("--logs-dir", default=None,
                        help="write the trace to <dir>/<run_id>.jsonl instead of "
                             "output_examples/traces/")
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
    except UnresolvedAddressError as exc:
        print(f"cannot resolve address: {exc}", file=sys.stderr)
        return 1
    except SampleMissError as exc:
        print(f"sample-mode cache miss: {exc}", file=sys.stderr)
        return 1
    except (NotConfiguredError, ProviderError) as exc:
        print(f"run failed: {exc}", file=sys.stderr)
        return 1
    except Exception as exc:  # noqa: BLE001 - CLI reports errors, never tracebacks
        print(f"error: {type(exc).__name__}: {exc}", file=sys.stderr)
        return 1
    out_path = (
        Path(args.output) if args.output
        else ROOT / "logs" / f"{report['run_id']}.json"
    )
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(json.dumps(report, indent=1, default=str))
    if args.logs_dir:
        trace_path = Path(args.logs_dir) / f"{report['run_id']}.jsonl"
    else:
        trace_path = ROOT / "output_examples" / "traces" / (Path(args.input).stem + ".jsonl")
    trace_path.parent.mkdir(parents=True, exist_ok=True)
    with trace_path.open("w") as fh:
        for row in trace_events(report):
            line = json.dumps(row, default=str)
            fh.write(line + "\n")
            print(line, file=sys.stderr)
    print(json.dumps(report, indent=1, default=str))
    return 0


if __name__ == "__main__":
    sys.exit(main())
