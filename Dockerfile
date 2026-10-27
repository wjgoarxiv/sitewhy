FROM python:3.12-slim

# Live mode: pass NIGHTSHIFT/ZETARIS settings with `--env-file` and reach
# host services via `host.docker.internal`.

COPY --from=ghcr.io/astral-sh/uv:0.6.12 /uv /usr/local/bin/uv

WORKDIR /app

ENV UV_COMPILE_BYTECODE=1 \
    UV_LINK_MODE=copy \
    SAMPLE_MODE=true \
    PATH="/app/.venv/bin:$PATH"

COPY pyproject.toml uv.lock ./
RUN uv sync --frozen --no-dev --no-install-project

COPY app/ app/
COPY web/ web/
COPY data/ data/
COPY samples/ samples/
COPY scripts/ scripts/
COPY run.py ./
COPY input_examples/ input_examples/
COPY output_examples/ output_examples/
COPY zetaris/ zetaris/

RUN uv sync --frozen --no-dev

EXPOSE 8000

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
