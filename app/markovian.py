"""Meterless Markovian engine, implemented in Python from the open spec
(github.com/Meterless/Meterless, engines/markovian/AGENTS.md, Apache-2.0).

A long task runs as a chain of bounded chunks. Each chunk sees only the goal
(truncated after the first chunk), a compressed carryover state, and an optional
overlap window, so per-step context stays flat instead of growing with history.
The generator is injected: `generator(prompt, system) -> str | {"text", "usage"}`.
"""

import math
import re
import time
import uuid
from collections.abc import Callable
from dataclasses import dataclass, field

STATE_MARKERS = ["[STATE_CHECKPOINT]", "@@@STATE@@@", "[STATE]", "---STATE---"]
FINAL_MARKERS = ["[TASK_COMPLETE]", "@@@FINAL@@@", "[FINAL]", "---FINAL---"]
DEFAULTS = {"chunkSize": 8000, "maxChunks": 24, "carryoverTokens": 800, "overlapTokens": 0}
BOUNDS = {
    "chunkSize": (1000, 128000, 1000),
    "maxChunks": (1, 32, 1),
    "carryoverTokens": (128, 32768, 128),
    "overlapTokens": (0, 4096, 1),
}
FRAMING_TOKENS = 400
OUTPUT_BUDGET = 1200
GOAL_SUMMARY_CHARS = 200
HEURISTIC_CUES = re.compile(
    r"[^.\n]*\b(therefore|key insight|status|conclusion|applies|does not apply)\b[^.\n]*\.?", re.I
)
MARKER_RULES = (
    "End every chunk with exactly one marker. If more work remains, end with "
    "[STATE_CHECKPOINT] followed by:\nCOMPLETED: <what was done>\nREMAINING: <what is left>\n"
    "DECISIONS: <key choices with values>\nCONTEXT: <entities, open questions>\n"
    "If the task is finished, end with [TASK_COMPLETE]. Never mention the markers otherwise."
)


class ChunkConfigError(ValueError):
    pass


def validate_config(config: dict) -> dict:
    cfg = {**DEFAULTS, **config}
    for key, (lo, hi, step) in BOUNDS.items():
        value = cfg[key]
        if not isinstance(value, int) or not lo <= value <= hi or value % step:
            raise ChunkConfigError(f"{key}={value!r} outside [{lo}, {hi}] step {step}")
    if cfg["chunkSize"] < FRAMING_TOKENS + cfg["carryoverTokens"] + OUTPUT_BUDGET:
        raise ChunkConfigError("chunkSize too small for framing + carryoverTokens + output budget")
    return cfg


def estimate_tokens(text: str) -> int:
    return math.ceil(len(text) / 4)


def model_totals(
    n: int, f: int = 400, g: int = 200, s: int = 300, o: int = 1200, c: int = 800
) -> dict:
    """Modeled naive vs Markovian totals (docs/efficiency-model.md)."""
    naive = n * (f + g + s) + o * n * (n - 1) // 2
    markovian = n * (f + g + c + s)
    return {
        "naive_total": naive,
        "markovian_total": markovian,
        "efficiency": (naive - markovian) / naive if naive else 0.0,
    }


def run_efficiency(chunks: list[dict], config: dict) -> dict:
    """Historical efficiency, always against the run's own config snapshot."""
    tokens = [c["tokens"] for c in chunks]
    standard = sum(sum(tokens[: i + 1]) for i in range(len(tokens)))
    markovian = len(tokens) * config["carryoverTokens"] + sum(tokens)
    saved = max(0, standard - markovian)
    return {
        "standard_cost": standard,
        "markovian_cost": markovian,
        "tokens_saved": saved,
        "efficiency_percent": saved / standard * 100 if standard else 0.0,
    }


def _find(text: str, markers: list[str]) -> int:
    hits = [text.find(m) for m in markers if m in text]
    return min(hits) if hits else -1


def _clean(text: str) -> str:
    cut = _find(text, STATE_MARKERS)
    if cut != -1:
        text = text[:cut]
    for m in FINAL_MARKERS:
        text = text.replace(m, "")
    return text.strip()


@dataclass
class MarkovianRun:
    id: str
    timestamp: float
    prompt: str
    mode: str
    chunk_config: dict
    chunks: list[dict] = field(default_factory=list)
    status: str = "completed"
    output: str = ""
    final_state: str = ""
    reflection: str | None = None
    error: str | None = None
    token_label: str = "estimated"
    total_tokens_used: int = 0
    total_tokens_saved: int = 0
    efficiency_percent: float = 0.0
    duration_ms: float = 0.0


class Markovian:
    def __init__(
        self,
        chunk_config: dict | None = None,
        clock: Callable[[], float] = lambda: time.time() * 1000,
    ):
        self.config = validate_config(chunk_config or {})
        self.clock = clock

    def _carryover(self, raw: str, display: str, previous: str, compressor) -> str:
        budget = self.config["carryoverTokens"] * 4
        cut = _find(raw, STATE_MARKERS)
        if cut != -1:
            state = raw[cut:]
            for m in STATE_MARKERS + FINAL_MARKERS:
                state = state.replace(m, "")
            state = state.strip()
            if len(state) >= 24 and len(state) <= budget:
                return state
        if compressor:
            try:
                text = compressor(
                    f"Previous state:\n{previous}\n\nLatest output (tail):\n{display[-2000:]}",
                    "Compress into 3-5 critical points as COMPLETED / REMAINING / DECISIONS / "
                    "CONTEXT lines.",
                )
                if text and text.strip():
                    return text.strip()[:budget]
            except Exception:  # noqa: BLE001 - cascade falls through to heuristics
                pass
        cues = [m.group(0).strip() for m in HEURISTIC_CUES.finditer(display)]
        if cues:
            return "; ".join(cues[:5])[:budget]
        words = display.split()
        return " ".join(words[-(budget // 6) :])[:budget]

    def _prompt(self, goal: str, carry: str, overlap: str, memory: str, first: bool) -> str:
        if first:
            head = f"{memory}\n\nUser Request: {goal}" if memory else goal
            return f"{head}\n\n{MARKER_RULES}"
        parts = [f"GOAL (summary): {goal[:GOAL_SUMMARY_CHARS]}", f"[CARRYOVER]\n{carry}"]
        if overlap:
            parts.append(f"[OVERLAP]\n{overlap}")
        parts.append("Continue from the carryover state. " + MARKER_RULES)
        return "\n\n".join(parts)

    def run(
        self,
        goal: str,
        generator: Callable,
        mode: str = "RESEARCH",
        memory_context: str = "",
        system: str | None = None,
        compressor: Callable | None = None,
        reflect: bool = True,
    ) -> MarkovianRun:
        cfg = dict(self.config)
        run = MarkovianRun(str(uuid.uuid4()), self.clock(), goal[:500], mode, cfg)
        carry, overlap, measured, done = "", "", True, False
        while len(run.chunks) < cfg["maxChunks"] and not done:
            prompt = self._prompt(goal, carry, overlap, memory_context, not run.chunks)
            try:
                result = generator(prompt, system)
            except Exception as exc:  # noqa: BLE001 - a provider failure ends the run, keeps output
                run.status, run.error = "errored", str(exc)
                break
            raw = result["text"] if isinstance(result, dict) else str(result)
            usage = (result.get("usage") or {}) if isinstance(result, dict) else {}
            done = _find(raw, FINAL_MARKERS) != -1
            display = _clean(raw)
            if "output_tokens" in usage:
                tokens = usage["output_tokens"]
            else:
                tokens, measured = estimate_tokens(display), False
            run.chunks.append(
                {
                    "id": len(run.chunks) + 1,
                    "tokens": tokens,
                    "carryover": carry,
                    "content": display,
                }
            )
            if cfg["overlapTokens"]:
                overlap = display[-cfg["overlapTokens"] * 4 :]
            carry = "" if done else self._carryover(raw, display, carry, compressor)
        else:
            run.status = "completed" if done else "max-chunks"

        run.final_state = carry
        run.output = "\n\n".join(c["content"] for c in run.chunks)
        run.token_label = "measured" if measured and run.chunks else "estimated"
        eff = run_efficiency(run.chunks, cfg)
        run.total_tokens_used = sum(c["tokens"] for c in run.chunks)
        run.total_tokens_saved = eff["tokens_saved"]
        run.efficiency_percent = eff["efficiency_percent"]
        if reflect and run.status == "completed" and run.chunks:
            try:
                result = generator(
                    f"Original task: {goal}\n\nFull work:\n{run.output[-12000:]}\n\n"
                    "Reflect: state the final answer and anything that remains uncertain.",
                    system,
                )
                run.reflection = result["text"] if isinstance(result, dict) else str(result)
            except Exception:  # noqa: BLE001 - reflection failure never fails the run
                run.reflection = None
        run.duration_ms = self.clock() - run.timestamp
        return run
