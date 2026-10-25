import json

import httpx
import pytest

from app.config import Settings
from app.llm import (
    LIGHTNING,
    ULTRA,
    ModelRouter,
    NotConfiguredError,
    ProviderError,
    SampleMissError,
    strip_think,
)

SETTINGS = Settings(nightshift_token="tok")


def reply(model, content, status=200, receipt="rcpt_1"):
    body = {
        "model": model,
        "choices": [{"message": {"role": "assistant", "content": content}}],
        "usage": {"prompt_tokens": 3, "completion_tokens": 2, "total_tokens": 5},
        "meterless": {
            "receipt_id": receipt,
            "routed_model": model,
            "winning_route": {"provider": "nvidia", "kind": "cloud"},
        },
    }
    return httpx.Response(status, json=body)


def make_router(handler, tmp_path, settings=SETTINGS, **kw):
    client = httpx.Client(transport=httpx.MockTransport(handler))
    return ModelRouter(settings, client=client, cache_dir=tmp_path, sleep=lambda s: None, **kw)


def test_strip_think_handles_open_tag_missing_and_present():
    assert strip_think("reasoning here</think>OK") == "OK"
    assert strip_think("<think>a</think>\n  B ") == "B"
    assert strip_think("plain") == "plain"


def test_steps_route_to_expected_models_with_required_headers(tmp_path):
    seen = []

    def handler(request):
        body = json.loads(request.content)
        seen.append((body["model"], dict(request.headers)))
        return reply(body["model"], "ok")

    router = make_router(handler, tmp_path)
    router.generate("extract", [{"role": "user", "content": "a"}])
    router.generate("critique", [{"role": "user", "content": "b"}])
    assert [m for m, _ in seen] == [LIGHTNING, ULTRA]
    headers = seen[0][1]
    assert headers["authorization"] == "Bearer tok"
    assert headers["meterless-app"] == "sitewhy"
    assert headers["meterless-scope"] == "user"


def test_trace_records_answering_model_receipt_and_role(tmp_path):
    router = make_router(lambda r: reply(ULTRA, "x</think>verdict", receipt="rcpt_9"), tmp_path)
    out = router.generate("synthesize", [{"role": "user", "content": "q"}], role="adjudicator")
    assert out.text == "verdict"
    entry = router.trace[-1]
    assert entry["step"] == "synthesize" and entry["role"] == "adjudicator"
    assert entry["model"] == ULTRA and entry["receipt_id"] == "rcpt_9"
    assert entry["provider"] == "nvidia" and entry["total_tokens"] == 5
    assert entry["cached"] is False and entry["latency_ms"] >= 0


def test_live_mode_always_calls_network_and_records_for_replay(tmp_path):
    calls = []

    def handler(request):
        calls.append(1)
        return reply(LIGHTNING, f"answer {len(calls)}")

    router = make_router(handler, tmp_path)
    msgs = [{"role": "user", "content": "q"}]
    assert router.generate("extract", msgs).text == "answer 1"
    assert router.generate("extract", msgs).text == "answer 2"
    assert len(calls) == 2 and router.trace[-1]["cached"] is False
    replay = make_router(handler, tmp_path, settings=Settings(sample_mode=True))
    assert replay.generate("extract", msgs).cached is True and len(calls) == 2


def test_retries_on_429_then_succeeds(tmp_path):
    responses = iter([httpx.Response(429), httpx.Response(503), reply(LIGHTNING, "ok")])
    router = make_router(lambda r: next(responses), tmp_path)
    assert router.generate("classify", [{"role": "user", "content": "q"}]).text == "ok"


def test_gives_up_after_max_retries(tmp_path):
    router = make_router(lambda r: httpx.Response(429), tmp_path)
    with pytest.raises(ProviderError):
        router.generate("classify", [{"role": "user", "content": "q"}])


def test_provider_error_is_not_retried(tmp_path):
    calls = []

    def handler(request):
        calls.append(1)
        return httpx.Response(404, json={"error": {"message": "not found"}})

    router = make_router(handler, tmp_path)
    with pytest.raises(ProviderError):
        router.generate("plan", [{"role": "user", "content": "q"}])
    assert len(calls) == 1


def test_sample_mode_serves_cache_only(tmp_path):
    msgs = [{"role": "user", "content": "q"}]
    make_router(lambda r: reply(LIGHTNING, "cached"), tmp_path).generate("extract", msgs)

    def boom(request):
        raise AssertionError("network used in sample mode")

    sample = make_router(boom, tmp_path, settings=Settings(sample_mode=True))
    assert sample.generate("extract", msgs).text == "cached"
    with pytest.raises(SampleMissError):
        sample.generate("extract", [{"role": "user", "content": "other"}])


def test_unconfigured_raises_typed_error(tmp_path):
    router = make_router(lambda r: reply(LIGHTNING, "x"), tmp_path, settings=Settings())
    with pytest.raises(NotConfiguredError):
        router.generate("extract", [{"role": "user", "content": "q"}])


def test_unknown_step_rejected(tmp_path):
    router = make_router(lambda r: reply(LIGHTNING, "x"), tmp_path)
    with pytest.raises(ValueError):
        router.generate("summarize_everything", [])


def test_status_maps_models_endpoint(tmp_path):
    for code, expected in [(200, "online"), (401, "unauthorized"), (500, "offline")]:
        router = make_router(lambda r, c=code: httpx.Response(c, json={"data": []}), tmp_path)
        assert router.status() == expected

    def down(request):
        raise httpx.ConnectError("refused")

    assert make_router(down, tmp_path).status() == "offline"


def test_rate_limiter_spaces_calls(tmp_path):
    slept = []
    clock = iter([0.0, 0.0, 0.5, 0.5, 2.5, 2.5])
    client = httpx.Client(transport=httpx.MockTransport(lambda r: reply(LIGHTNING, "ok")))
    router = ModelRouter(
        SETTINGS,
        client=client,
        cache_dir=tmp_path,
        rpm=60,
        sleep=slept.append,
        clock=lambda: next(clock),
    )
    router.generate("extract", [{"role": "user", "content": "1"}])
    router.generate("extract", [{"role": "user", "content": "2"}])
    assert slept and abs(slept[0] - 0.5) < 1e-9


def test_generator_adapter_for_engines(tmp_path):
    router = make_router(lambda r: reply(LIGHTNING, "g"), tmp_path)
    gen = router.generator("extract", role="investigator")
    assert gen([{"role": "user", "content": "q"}]) == "g"
    assert router.trace[-1]["role"] == "investigator"


@pytest.mark.live
def test_live_nightshift_both_models(tmp_path):
    from app.config import load_settings

    router = ModelRouter(load_settings(), cache_dir=tmp_path)
    assert router.status() == "online"
    for step in ("extract", "plan"):
        out = router.generate(step, [{"role": "user", "content": "Reply with exactly: OK"}])
        assert "OK" in out.text
    assert {e["model"] for e in router.trace} == {LIGHTNING, ULTRA}
    assert all(e["receipt_id"] for e in router.trace)


def test_lightning_failure_escalates_to_ultra_and_is_traced(tmp_path):
    def handler(request):
        model = json.loads(request.content)["model"]
        if model == LIGHTNING:
            return httpx.Response(502, json={"error": {"message": "empty_response"}})
        return reply(ULTRA, "x</think>ok")

    router = make_router(handler, tmp_path)
    out = router.generate("extract", [{"role": "user", "content": "q"}])
    assert out.text == "ok" and out.model == ULTRA
    assert router.trace[-1]["escalated_from"] == LIGHTNING


def test_thinking_only_for_judgment_steps(tmp_path):
    seen = []

    def handler(request):
        body = json.loads(request.content)
        seen.append((body["chat_template_kwargs"]["enable_thinking"], body["max_tokens"]))
        return reply(body["model"], "ok")

    router = make_router(handler, tmp_path)
    router.generate("extract", [{"role": "user", "content": "a"}])
    router.generate("critique", [{"role": "user", "content": "b"}])
    assert seen == [(False, 4096), (True, 8192)]
