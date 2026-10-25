"""Run the full multi-agent screen from the command line.

Usage: uv run python scripts/run_screen.py "<address>" <mw> [--permits-submitted yes|no]
"""

import argparse
import json

from app.factory import build_orchestrator


def main() -> None:
    p = argparse.ArgumentParser()
    p.add_argument("address")
    p.add_argument("mw", type=float)
    p.add_argument("--permits-submitted", choices=["yes", "no"])
    a = p.parse_args()
    permits = None if a.permits_submitted is None else a.permits_submitted == "yes"
    r = build_orchestrator().run(a.address, a.mw, permits_submitted=permits)
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
