"""Nemotron step router. Every model call goes through Meterless Nightshift.

Each call is recorded in `trace` with the model Nightshift reports as having
answered it and its compute receipt, so the UI can show which model handled
every request.
"""

import hashlib
import json
import re
import time
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path

import httpx

from app.config import Settings

LIGHTNING = "nvidia/nemotron-3.5-lightning-30b-a3b"
ULTRA = "nvidia/nemotron-3-ultra-550b-a55b"

STEP_MODELS = {
    "extract": LIGHTNING,
    "classify": LIGHTNING,
    "verify_support": LIGHTNING,
    "plan": ULTRA,
    "synthesize": ULTRA,
    "critique": ULTRA,
}

# Reasoning stays on only where judgment matters; elsewhere it costs time and,
# on Lightning, sometimes leaves the completion empty.
THINKING_STEPS = {"synthesize", "critique"}
THINKING_MAX_TOKENS = 8192

APP_ID = "sitewhy"
RETRYABLE = {429, 500, 502, 503, 504}
MAX_ATTEMPTS = 3
DEFAULT_CACHE_DIR = Path(__file__).resolve().parent.parent / "data" / "llm_cache"


class NotConfiguredError(RuntimeError):
    pass


class ProviderError(RuntimeError):
    pass


class DeadlineExceeded(RuntimeError):
    pass


class SampleMissError(RuntimeError):
    pass


@dataclass(frozen=True)
class Completion:
    text: str
    model: str
    receipt_id: str
    cached: bool


def strip_think(text: str) -> str:
    """Drop reasoning that Ultra emits before `</think>` (the opening tag may be absent)."""
    if "</think>" in text:
        text = text.rsplit("</think>", 1)[1]
    return re.sub(r"<think>.*?</think>", "", text, flags=re.S).strip()


class ModelRouter:
    def __init__(
        self,
        settings: Settings,
        client: httpx.Client | None = None,
        cache_dir: Path = DEFAULT_CACHE_DIR,
        rpm: int = 30,
        sleep: Callable[[float], None] = time.sleep,
        clock: Callable[[], float] = time.monotonic,
        deadline: float | None = None,
    ):
        self.settings = settings
        self.client = client or httpx.Client(timeout=180)
        self.cache_dir = Path(cache_dir)
        self.interval = 60.0 / rpm
        self.sleep = sleep
        self.clock = clock
        self.deadline = deadline
        self.deadline_start: float | None = None
        self._next_ok = 0.0
        self._started = 0.0
        self.trace: list[dict] = []

    def _check_deadline(self) -> None:
        if self.deadline is None:
            return
        start = self.deadline_start if self.deadline_start is not None else 0.0
        if self.clock() - start >= self.deadline:
            raise DeadlineExceeded(f"model call exceeded the {self.deadline:g}s limit")

    def _headers(self) -> dict:
        return {
            "Authorization": f"Bearer {self.settings.nightshift_token}",
            "meterless-app": APP_ID,
            "meterless-scope": "user",
        }

    def _call_timeout(self) -> float:
        if self.deadline is None:
            return 180.0
        start = self.deadline_start if self.deadline_start is not None else 0.0
        remaining = self.deadline - (self.clock() - start)
        return max(min(180.0, remaining), 0.0)

    def status(self) -> str:
        try:
            resp = self.client.get(
                f"{self.settings.nightshift_base_url}/models", headers=self._headers()
            )
        except httpx.HTTPError:
            return "offline"
        if resp.status_code in (401, 403):
            return "unauthorized"
        return "online" if resp.status_code == 200 else "offline"

    def _cache_path(self, payload: dict) -> Path:
        key = hashlib.sha256(json.dumps(payload, sort_keys=True).encode()).hexdigest()
        return self.cache_dir / f"{key}.json"

    def _throttle(self) -> None:
        now = self.clock()
        wait = self._next_ok - now
        if wait > 0:
            self.sleep(wait)
            now += wait
        self._next_ok = max(now, self._next_ok) + self.interval

    def _post(self, payload: dict) -> dict:
        url = f"{self.settings.nightshift_base_url}/chat/completions"
        for attempt in range(MAX_ATTEMPTS):
            self._check_deadline()
            self._throttle()
            self._started = self.clock()
            try:
                resp = self.client.post(
                    url, json=payload, headers=self._headers(),
                    timeout=self._call_timeout(),
                )
            except httpx.HTTPError as exc:
                if attempt == MAX_ATTEMPTS - 1:
                    raise ProviderError(f"Nightshift unreachable: {exc}") from exc
            else:
                if resp.status_code == 200:
                    return resp.json()
                if resp.status_code not in RETRYABLE or attempt == MAX_ATTEMPTS - 1:
                    raise ProviderError(
                        f"Nightshift returned {resp.status_code}: {resp.text[:200]}"
                    )
            self.sleep(2**attempt)
        raise AssertionError("unreachable")

    def generate(
        self,
        step: str,
        messages: list[dict],
        role: str | None = None,
        max_tokens: int = 4096,
        temperature: float = 0.2,
    ) -> Completion:
        if step not in STEP_MODELS:
            raise ValueError(f"unknown step {step!r}; expected one of {sorted(STEP_MODELS)}")
        thinking = step in THINKING_STEPS
        payload = {
            "model": STEP_MODELS[step],
            "messages": messages,
            "max_tokens": max(max_tokens, THINKING_MAX_TOKENS) if thinking else max_tokens,
            "temperature": temperature,
            "chat_template_kwargs": {"enable_thinking": thinking},
        }
        cache_file = self._cache_path(payload)
        escalated_from = None
        if self.settings.sample_mode:
            # The cache is a replay store: read only in SAMPLE_MODE, so live retries
            # always get a fresh completion instead of the one that just failed.
            if not cache_file.is_file():
                raise SampleMissError(f"no cached response for step {step!r} in SAMPLE_MODE")
            start = self.clock()
            data, cached = json.loads(cache_file.read_text()), True
        elif not self.settings.nightshift_configured:
            raise NotConfiguredError("Nightshift is not configured (token missing)")
        else:
            try:
                data = self._post(payload)
            except ProviderError:
                if payload["model"] != LIGHTNING:
                    raise
                # Lightning intermittently returns an empty completion; escalate once.
                self._check_deadline()
                payload = {**payload, "model": ULTRA}
                data = self._post(payload)
                escalated_from = LIGHTNING
            data, cached = data, False
            start = self._started
            self.cache_dir.mkdir(parents=True, exist_ok=True)
            cache_file.write_text(json.dumps(data))
        end = self.clock()

        receipt = data.get("meterless") or {}
        model = receipt.get("routed_model") or data.get("model") or payload["model"]
        usage = data.get("usage") or {}
        text = strip_think(data["choices"][0]["message"].get("content") or "")
        self.trace.append(
            {
                "step": step,
                "role": role,
                "model": model,
                "provider": (receipt.get("winning_route") or {}).get("provider"),
                "receipt_id": receipt.get("receipt_id", ""),
                "total_tokens": usage.get("total_tokens"),
                "latency_ms": round(max(end - start, 0) * 1000),
                "cached": cached,
                "escalated_from": escalated_from,
            }
        )
        return Completion(text, model, receipt.get("receipt_id", ""), cached)

    def generator(self, step: str, role: str | None = None) -> Callable[[list[dict]], str]:
        """Plain `messages -> text` callable injected into the Meterless engines."""
        return lambda messages: self.generate(step, messages, role=role).text
