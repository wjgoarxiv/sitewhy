"""Static checks for the explainer panel plus node-run checks of its pure logic.

Every AI/code claim the panel makes is pinned to app/llm.py, app/agents.py and
app/orchestrator.py, so the copy cannot drift from what the code does.
"""

import json
import re
import shutil
import subprocess
from html.parser import HTMLParser
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from app.config import Settings
from app.llm import LIGHTNING, STEP_MODELS, ULTRA
from app.main import create_app

ROOT = Path(__file__).resolve().parent.parent
WEB = ROOT / "web"
SAMPLES = ROOT / "samples"

STEP_ORDER = ["planner", "investigator", "verifier", "rulecheck", "adjudicator", "critic"]
# pipeline chip -> (report event/trace role, router step it calls, or None for code)
CHIPS = {
    "planner": ("planner", "plan"),
    "investigator": ("county_investigator", "extract"),
    "verifier": ("evidence_verifier", None),
    "rulecheck": ("applicability", None),
    "adjudicator": ("adjudicator", "synthesize"),
    "critic": ("critic", "critique"),
}


class Steps(HTMLParser):
    """Collects each <li data-step> with its attributes and visible text."""

    def __init__(self):
        super().__init__()
        self.steps: list[dict] = []
        self._open: dict | None = None

    def handle_starttag(self, tag, attrs):
        a = dict(attrs)
        if tag == "li" and "data-step" in a:
            self._open = {"attrs": a, "text": ""}

    def handle_endtag(self, tag):
        if tag == "li" and self._open is not None:
            self.steps.append(self._open)
            self._open = None

    def handle_data(self, data):
        if self._open is not None:
            self._open["text"] += data


@pytest.fixture(scope="module")
def html() -> str:
    return (WEB / "index.html").read_text()


@pytest.fixture(scope="module")
def steps(html) -> list[dict]:
    parser = Steps()
    parser.feed(html)
    return parser.steps


def role_names(path: Path, pattern: str) -> set[str]:
    return set(re.findall(pattern, path.read_text()))


def test_explainer_panel_replaces_the_strip(html):
    assert 'id="explainer"' in html
    assert 'data-demo="explainer"' in html
    assert "What you get" in html
    assert "Where AI is used" in html
    assert "how-steps" not in html, "the old three-step strip is replaced"


def test_assets_are_linked_and_served(html):
    assert '<link rel="stylesheet" href="/explain.css">' in html
    scripts = [html.index(f'src="/{name}.js"') for name in ("app", "explain-logic", "explain")]
    assert scripts == sorted(scripts), "explain-logic.js loads before explain.js, both after app.js"
    client = TestClient(create_app(Settings()))
    assert "Where AI is used" in client.get("/").text
    for asset in ("/explain-logic.js", "/explain.js", "/explain.css"):
        assert client.get(asset).status_code == 200


def test_four_tiles_say_what_you_get(html):
    tiles = re.findall(r'data-tile="(\w+)"', html)
    assert tiles == ["verdict", "rule", "math", "flips"]
    assert "1,067 tpy ≥ 100 tpy" in html
    assert "at 25 MW instead of 300 MW" in html


def test_pipeline_has_six_steps_in_order(html, steps):
    assert 'data-demo="pipeline"' in html
    assert [s["attrs"]["data-step"] for s in steps] == STEP_ORDER


def test_pipeline_roles_match_the_code(steps):
    assert len(steps) == 6
    ai_roles = role_names(ROOT / "app/agents.py", r'role="(\w+)"')
    orchestrator = (ROOT / "app/orchestrator.py").read_text()
    for step in steps:
        name, role = step["attrs"]["data-step"], step["attrs"]["data-role"]
        expected_role, llm_step = CHIPS[name]
        assert role == expected_role
        if llm_step:
            assert step["attrs"]["data-kind"] == "ai"
            assert role in ai_roles, f"{role} never calls the model router"
        else:
            assert step["attrs"]["data-kind"] == "code"
            assert role not in ai_roles, f"{role} calls a model, so it is not code"
            assert f'"{role}"' in orchestrator, f"orchestrator never emits {role} events"


def test_ai_chips_name_the_model_the_router_uses(steps):
    assert len(steps) == 6
    for step in steps:
        llm_step = CHIPS[step["attrs"]["data-step"]][1]
        text = step["text"]
        if llm_step is None:
            assert "Code" in text and "Python" in text and "Nemotron" not in text
            continue
        model = STEP_MODELS[llm_step]
        word = "Ultra" if model == ULTRA else "Lightning"
        assert model in (ULTRA, LIGHTNING)
        assert f"AI · Nemotron {word}" in " ".join(text.split())


def test_footer_names_the_gateway_and_the_data(html):
    assert "Every model call goes through Meterless Nightshift" in html
    assert "reference data from Zetaris" in html
    assert "Every model call goes through Meterless Nightshift" in (ROOT / "app/llm.py").read_text()


def test_hide_toggle_and_replay_button(html):
    assert 'id="ex-toggle"' in html and 'aria-expanded="true"' in html
    assert re.search(r'id="ex-replay"[^>]*>\s*Replay how this verdict was built', html)
    js = (WEB / "explain.js").read_text()
    assert re.search(r"try\s*\{[^}]*localStorage", js), "localStorage access must be guarded"


def test_event_names_agree_between_app_and_explainer():
    app, explain = (WEB / "app.js").read_text(), (WEB / "explain.js").read_text()
    for name in ("sitewhy:events", "sitewhy:run-start", "sitewhy:run-end"):
        assert name in app, f"app.js never dispatches {name}"
        assert name in explain, f"explain.js never listens for {name}"


# --- pure logic, run under node against the real recorded reports -------------

NODE = shutil.which("node")
DRIVER = """
const vm = require("vm"), fs = require("fs");
const win = {};
const doc = { getElementById: () => null, querySelector: () => null,
  querySelectorAll: () => [], addEventListener() {} };
vm.runInNewContext(fs.readFileSync(process.argv[1], "utf8"), { window: win, document: doc });
const args = JSON.parse(fs.readFileSync(0, "utf8"));
process.stdout.write(JSON.stringify(win.SiteWhyExplain[process.argv[2]](...args)));
"""


def call(fn: str, *args):
    out = subprocess.run(
        [NODE, "-e", DRIVER, str(WEB / "explain-logic.js"), fn],
        input=json.dumps(args), capture_output=True, text=True, check=True,
    )
    return json.loads(out.stdout)


def sample(name: str) -> dict:
    return json.loads((SAMPLES / f"{name}.json").read_text())


def first_index(events: list[dict], role: str, action: str, round_: int | None = None) -> int:
    return next(
        i for i, e in enumerate(events)
        if e["role"] == role and e["action"] == action and round_ in (None, e["round"])
    )


needs_node = pytest.mark.skipif(NODE is None, reason="node is not installed")


@needs_node
def test_live_state_follows_the_events_of_a_run():
    events = sample("md-washington-county-unincorporated")["events"]
    start = call("liveState", events[:1])
    assert start["active"] == "planner" and start["done"] == []
    planned = call("liveState", events[: first_index(events, "planner", "tasks") + 1])
    assert planned["active"] == "investigator" and planned["done"] == ["planner"]
    computed = call("liveState", events[: first_index(events, "applicability", "computed") + 1])
    assert computed["active"] == "adjudicator"
    assert set(computed["done"]) == {"planner", "investigator", "verifier", "rulecheck"}
    drafted = call("liveState", events[: first_index(events, "adjudicator", "draft") + 1])
    assert drafted["active"] == "critic"


@needs_node
def test_live_state_shows_round_two_when_the_critic_sends_work_back():
    events = sample("md-washington-county-unincorporated")["events"]
    after_critic = call("liveState", events[: first_index(events, "critic", "objections", 1) + 1])
    assert after_critic["round"] == 2
    assert after_critic["active"] == "planner" and after_critic["done"] == []
    assert "Round 2" in after_critic["text"]
    final = call("liveState", events)
    assert final["round"] == 2 and final["active"] is None and "critic" in final["done"]


@needs_node
def test_live_state_skips_the_investigator_when_there_is_nothing_to_plan():
    events = sample("tx-abilene-ercot")["events"]
    planned = call("liveState", events[: first_index(events, "planner", "tasks") + 1])
    assert planned["active"] == "rulecheck"


@needs_node
def test_replay_beats_walk_the_pipeline_once_per_round_with_model_and_latency():
    report = sample("md-washington-county-unincorporated")
    beats = call("replayBeats", report)
    assert [b["step"] for b in beats] == STEP_ORDER * 2
    assert [b["round"] for b in beats] == [1] * 6 + [2] * 6
    planner = beats[0]
    assert "Nemotron Ultra" in planner["readout"] and "2.7 s" in planner["readout"]
    investigator = beats[1]["readout"]
    assert "Lightning ×3" in investigator and "Ultra" in investigator
    checked = r"\d+ quotes checked · (all verbatim|\d+ not verbatim)"
    assert re.fullmatch(checked, beats[2]["readout"])
    assert "Python" in beats[3]["readout"] or "rules computed" in beats[3]["readout"]
    assert "Nemotron Ultra" in beats[4]["readout"]
    assert beats[1]["text"].startswith("Round 1 · County investigator")


@needs_node
def test_replay_beats_for_a_run_without_county_work_skip_those_steps():
    beats = call("replayBeats", sample("tx-abilene-ercot"))
    assert [b["step"] for b in beats if b["round"] == 1] == [
        "planner", "rulecheck", "adjudicator", "critic",
    ]
    assert "Round" not in beats[0]["text"] or beats[0]["text"].startswith("Round 1")


@needs_node
def test_provenance_text_matches_how_the_evidence_was_made():
    verified = "verified word for word by code"
    assert call("provenanceText", "curated", "verified", False) == f"Curated rule text · {verified}"
    county = "Pulled from the county source by Nemotron Lightning"
    for prov in ("county_source", "primary"):
        assert call("provenanceText", prov, "verified", False) == f"{county} · {verified}"
    assert call("provenanceText", "primary", "verified", True) == (
        f"{county}, Ultra on retry · {verified}"
    )
    assert call("provenanceText", "dataset", "dataset", False) == (
        "From the Moratorium Nation dataset in Zetaris"
    )
    assert "not verified" in call("provenanceText", "primary", "unverifiable", False)
    assert call("provenanceText", "unheard-of", "verified", False) == ""


@needs_node
def test_banner_text_only_claims_what_the_trace_shows():
    full = call("bannerText", sample("md-hagerstown-city"))
    assert full == (
        "Verdict drafted by Nemotron Ultra from code-checked rules, "
        "then challenged by the critic"
    )
    no_model = {"events": [{"role": "system", "action": "timeout"}], "model_trace": []}
    assert call("bannerText", no_model) == ""


@needs_node
def test_helpers_survive_empty_and_malformed_reports():
    idle = call("liveState", [{}, {"role": "planner"}, {"role": "critic", "detail": None}])
    assert idle["round"] == 1 and idle["active"] is None
    assert call("liveState", []) == {
        "round": 1, "active": None, "done": [], "text": "Resolving the site…",
    }
    assert call("replayBeats", None) == []
    sparse = call("replayBeats", {"events": [{"role": "planner"}], "model_trace": [{}]})
    assert [b["step"] for b in sparse] == ["planner"]
    assert call("bannerText", None) == ""
    assert call("provenanceText", None, None, False) == ""
