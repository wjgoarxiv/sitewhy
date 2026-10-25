"""Score recorded showcase samples against data/eval/ground_truth.yaml (Todo 10).

Usage: uv run python scripts/eval.py [--live]
Default scores samples/*.json. --live re-runs the three ground-truth sites
live first (slow). Prints a table and writes data/eval/results.json.
"""

import argparse
import json
import sys
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parent.parent
SAMPLES_DIR = ROOT / "samples"
EVAL_DIR = ROOT / "data" / "eval"
TRUTH_PATH = EVAL_DIR / "ground_truth.yaml"
RESULTS_PATH = EVAL_DIR / "results.json"

SITES = (
    "md-washington-county-unincorporated",
    "tx-abilene-ercot",
    "az-tucson-pima",
)


def load_truth() -> dict:
    return yaml.safe_load(TRUTH_PATH.read_text())


def check_site(sample: dict, expectation: dict) -> dict:
    checks: dict = {}
    verdict = expectation.get("verdict")
    if isinstance(verdict, list):
        checks["verdict"] = sample.get("verdict") in verdict
    else:
        checks["verdict"] = sample.get("verdict") == verdict
    findings = {f.get("rule_id"): f for f in sample.get("findings", [])}
    rules: dict = {}
    for rule_id, want in (expectation.get("rules") or {}).items():
        got = findings.get(rule_id, {})
        ok = all(got.get(k) == v for k, v in want.items() if k != "reason_contains")
        needles = want.get("reason_contains") or []
        if needles:
            reason = str(got.get("reason", "")).lower()
            ok = ok and any(n.lower() in reason for n in needles)
        rules[rule_id] = ok
    checks["rules"] = rules
    if expectation.get("no_fatal"):
        checks["no_fatal"] = all(f.get("grade") != "fatal" for f in findings.values())
    passed = all(
        v if isinstance(v, bool) else all(v.values()) for v in checks.values()
    )
    return {"passed": passed, "checks": checks}


def score_samples(samples_dir: Path = SAMPLES_DIR) -> dict:
    truth = load_truth()
    sites = {}
    for name in SITES:
        sample = json.loads((samples_dir / f"{name}.json").read_text())
        sites[name] = check_site(sample, truth[name])
    passed = sum(1 for s in sites.values() if s["passed"])
    return {"sites": sites, "passed": passed, "total": len(sites)}


def write_results(ground_truth: dict) -> dict:
    EVAL_DIR.mkdir(parents=True, exist_ok=True)
    results = {}
    if RESULTS_PATH.is_file():
        results = json.loads(RESULTS_PATH.read_text())
    results["ground_truth"] = ground_truth
    RESULTS_PATH.write_text(json.dumps(results, indent=1))
    return results


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--live", action="store_true")
    args = parser.parse_args()
    if args.live:
        from scripts.record_samples import SITES as RECORD_SITES
        from scripts.record_samples import record

        for name in SITES:
            record(name, RECORD_SITES[name])
    result = score_samples()
    for name, site in result["sites"].items():
        mark = "PASS" if site["passed"] else "FAIL"
        print(f"{mark} {name}")
    print(f"{result['passed']}/{result['total']} sites match ground truth")
    write_results(result)
    if result["passed"] != result["total"]:
        sys.exit(1)


if __name__ == "__main__":
    main()
