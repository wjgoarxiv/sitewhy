import json

from scripts.eval import SITES, check_site, load_truth


def test_showcase_ground_truth():
    truth = load_truth()
    assert set(SITES) <= set(truth)
    results = {}
    for name in SITES:
        sample = json.load(open(f"samples/{name}.json"))
        results[name] = check_site(sample, truth[name])
    assert sum(1 for r in results.values() if r["passed"]) == 3
