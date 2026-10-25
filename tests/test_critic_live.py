import json
from pathlib import Path

import pytest

from app.agents import Critic
from app.config import load_settings
from app.llm import ModelRouter
from scripts.eval import EVAL_DIR

SAMPLES = Path(__file__).resolve().parent.parent / "samples"


def load(name):
    return json.loads((SAMPLES / f"{name}.json").read_text())


def site_of(report, **overrides):
    site = dict(report.get("site") or {})
    site.update(overrides)
    return site


def merge_results(critic_result: dict, path: Path) -> dict:
    results = json.loads(path.read_text()) if path.is_file() else {}
    results["critic_seeded_faults"] = critic_result
    path.write_text(json.dumps(results, indent=1))
    return results


def test_merge_results_writes_to_given_path(tmp_path):
    path = tmp_path / "results.json"
    out = merge_results({"caught": 2}, path)
    assert json.loads(path.read_text())["critic_seeded_faults"] == {"caught": 2}
    assert out["critic_seeded_faults"] == {"caught": 2}


@pytest.mark.live
def test_critic_catches_seeded_faults():
    router = ModelRouter(load_settings())
    assert router.status() == "online"
    critic = Critic(router)

    tucson = load("az-tucson-pima")
    abilene = load("tx-abilene-ercot")
    washington = load("md-washington-county-unincorporated")
    pima = next(f for f in tucson["findings"] if f["rule_id"] == "az-pima-county-2026")
    title_v = next(
        f for f in abilene["findings"] if f["rule_id"] == "federal-title-v-major-source"
    )
    moratorium = next(
        f for f in washington["findings"] if f["rule_id"] == "md-washington-county-2026"
    )

    faults = [
        {
            "id": "fatal-pima",
            "rule_id": "az-pima-county-2026",
            "site": site_of(tucson),
            "draft": {"verdict": "conditional", "why": "seeded", "grades": {
                "az-pima-county-2026": "fatal",
                "federal-title-v-major-source": "major",
            }},
            "findings": [pima, next(
                f for f in tucson["findings"]
                if f["rule_id"] == "federal-title-v-major-source"
            )],
            "conflicts": [],
        },
        {
            "id": "title-v-below-threshold",
            "rule_id": "federal-title-v-major-source",
            "site": site_of(abilene),
            "draft": {"verdict": "conditional", "why": "seeded", "grades": {
                "federal-title-v-major-source": "major",
            }},
            "findings": [{**title_v,
                           "reason": "estimated NOx potential to emit 25 tpy, "
                           "below the 100 tpy major-source threshold, "
                           "so the rule does not trigger"}],
            "conflicts": [],
        },
        {
            "id": "washington-missed-exemption",
            "rule_id": "md-washington-county-2026",
            "site": site_of(washington, permits_submitted=True),
            "draft": {"verdict": "no-go", "why": "seeded", "grades": {
                "md-washington-county-2026": "fatal",
            }},
            "findings": [{**moratorium, "parameters": {
                **(moratorium.get("parameters") or {}),
                "exempt_if_permits_submitted": True,
            }}],
            "conflicts": [],
        },
    ]
    caught = []
    for fault in faults:
        objections = critic.review(
            fault["site"], fault["draft"], fault["findings"], fault["conflicts"]
        )
        hit = any(o.get("rule_id") == fault["rule_id"] for o in objections)
        caught.append(fault["id"] if hit else None)
        print(f"{'CAUGHT' if hit else 'MISSED'} {fault['id']}: {objections}")

    result = {"caught": sum(1 for c in caught if c), "total": len(faults), "faults": caught}
    EVAL_DIR.mkdir(parents=True, exist_ok=True)
    merge_results(result, EVAL_DIR / "results.json")
    assert result["caught"] >= 2
