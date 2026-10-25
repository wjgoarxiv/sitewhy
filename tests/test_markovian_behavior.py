from app.markovian import Markovian

CFG = {"chunkSize": 4000, "carryoverTokens": 640, "maxChunks": 3}


def test_carryover_from_marker_feeds_next_prompt_and_goal_is_truncated():
    prompts = []

    def gen(prompt, system=None):
        prompts.append(prompt)
        if len(prompts) == 1:
            return "work [STATE_CHECKPOINT]\nCOMPLETED: read ordinance\nREMAINING: exemptions"
        return "final answer [TASK_COMPLETE]"

    run = Markovian(chunk_config=CFG).run(goal="G" * 500, generator=gen, reflect=False)
    assert "COMPLETED: read ordinance" in prompts[1]
    assert "G" * 500 not in prompts[1] and "G" * 200 in prompts[1]
    assert run.chunks[1]["carryover"].startswith("COMPLETED: read ordinance")
    assert run.final_state == ""


def test_memory_context_only_enters_first_chunk():
    prompts = []

    def gen(prompt, system=None):
        prompts.append(prompt)
        return (
            "x [STATE_CHECKPOINT]\nCOMPLETED: one step of work done"
            if len(prompts) < 2
            else "y [TASK_COMPLETE]"
        )

    Markovian(chunk_config=CFG).run(
        goal="g", generator=gen, memory_context="SOURCE TEXT ABC", reflect=False
    )
    assert "SOURCE TEXT ABC" in prompts[0] and "SOURCE TEXT ABC" not in prompts[1]


def test_max_chunks_status_and_heuristic_carryover_without_marker():
    run = Markovian(chunk_config=CFG).run(
        goal="g",
        generator=lambda p, s=None: "Therefore the rule applies. More text.",
        reflect=False,
    )
    assert run.status == "max-chunks" and len(run.chunks) == 3
    assert "Therefore the rule applies" in run.chunks[1]["carryover"]


def test_generator_error_preserves_partial_output():
    calls = {"n": 0}

    def gen(prompt, system=None):
        calls["n"] += 1
        if calls["n"] == 2:
            raise RuntimeError("boom")
        return "first part [STATE_CHECKPOINT]\nCOMPLETED: first part finished ok"

    run = Markovian(chunk_config=CFG).run(goal="g", generator=gen, reflect=False)
    assert run.status == "errored" and "first part" in run.output and "boom" in run.error


def test_measured_label_when_generator_reports_usage():
    run = Markovian(chunk_config=CFG).run(
        goal="g",
        generator=lambda p, s=None: {"text": "a [TASK_COMPLETE]", "usage": {"output_tokens": 7}},
        reflect=False,
    )
    assert run.token_label == "measured" and run.chunks[0]["tokens"] == 7


def test_reflection_appends_when_completed():
    outputs = iter(["body [TASK_COMPLETE]", "REFLECTION TEXT"])
    run = Markovian(chunk_config=CFG).run(goal="g", generator=lambda p, s=None: next(outputs))
    assert run.reflection == "REFLECTION TEXT"
