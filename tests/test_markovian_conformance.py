"""Python port of Meterless engines/markovian/conformance/runner.ts (same check ids)."""

import pytest

from app.markovian import ChunkConfigError, Markovian, model_totals, run_efficiency

T0 = 1_750_000_000_000


def step_gen(total):
    calls = {"n": 0}

    def gen(prompt, system=None):
        calls["n"] += 1
        n = calls["n"]
        body = f"Output for step {n} with enough text to register in the accounting math. " * 10
        marker = (
            "[TASK_COMPLETE]"
            if n >= total
            else f"[STATE_CHECKPOINT]\nCOMPLETED: steps 1-{n}\nREMAINING: {total - n}\n"
            "DECISIONS: none\nCONTEXT: conformance"
        )
        return {"text": body + "\n" + marker}

    gen.calls = calls
    return gen


def test_eff_001_efficiency_model_worked_example():
    t = model_totals(20)
    assert t["naive_total"] == 246_000
    assert t["markovian_total"] == 34_000
    assert abs(t["efficiency"] * 100 - 86.18) < 0.5


def test_snap_001_runs_carry_chunk_config_snapshot():
    m = Markovian(chunk_config={"chunkSize": 4000, "carryoverTokens": 640}, clock=lambda: T0)
    run = m.run(goal="snapshot check", generator=step_gen(3), reflect=False)
    assert run.chunk_config["carryoverTokens"] == 640


def test_snap_002_efficiency_uses_the_runs_own_snapshot():
    chunks = [{"id": i, "tokens": 1000, "carryover": "", "content": ""} for i in range(1, 5)]
    base = {"chunkSize": 8000, "maxChunks": 24, "overlapTokens": 0}
    a = run_efficiency(chunks, {**base, "carryoverTokens": 512})
    b = run_efficiency(chunks, {**base, "carryoverTokens": 2048})
    assert a["standard_cost"] == 10_000
    assert a["markovian_cost"] == 6_048
    assert a["tokens_saved"] != b["tokens_saved"]


def test_ovl_001_overlap_is_implemented_not_ignored():
    m = Markovian(
        chunk_config={"chunkSize": 4000, "carryoverTokens": 640, "overlapTokens": 64},
        clock=lambda: T0,
    )
    prompts = []

    def gen(prompt, system=None):
        prompts.append(prompt)
        done = len(prompts) >= 3
        tail = "[TASK_COMPLETE]" if done else "[STATE_CHECKPOINT]\nCOMPLETED: chunk recorded"
        return {"text": f"chunk {len(prompts)} content " * 20 + tail}

    m.run(goal="overlap conformance", generator=gen, reflect=False)
    assert any("[OVERLAP]" in p for p in prompts[1:])


def test_lab_001_token_numbers_are_labeled():
    m = Markovian(chunk_config={"chunkSize": 4000, "carryoverTokens": 640}, clock=lambda: T0)
    run = m.run(goal="label check", generator=step_gen(2), reflect=False)
    assert run.token_label in {"estimated", "measured"}


def test_ref_001_reflection_failure_does_not_fail_the_run():
    calls = {"n": 0}

    def gen(prompt, system=None):
        calls["n"] += 1
        if calls["n"] == 2:
            raise RuntimeError("provider exploded in reflection")
        return {"text": "done in one chunk [TASK_COMPLETE]"}

    m = Markovian(chunk_config={"chunkSize": 4000, "carryoverTokens": 640}, clock=lambda: T0)
    assert m.run(goal="reflection failure", generator=gen).status == "completed"


def test_mrk_001_markers_are_cleaned_and_drive_completion():
    m = Markovian(chunk_config={"chunkSize": 4000, "carryoverTokens": 640}, clock=lambda: T0)
    run = m.run(goal="marker cleaning", generator=step_gen(3), reflect=False)
    assert run.status == "completed"
    assert "STATE_CHECKPOINT" not in run.output and "TASK_COMPLETE" not in run.output
    assert len(run.chunks) == 3


def test_cfg_001_out_of_range_config_is_rejected():
    with pytest.raises(ChunkConfigError):
        Markovian(chunk_config={"chunkSize": 128, "carryoverTokens": 640})
