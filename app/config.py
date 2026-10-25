"""Runtime settings.

Secrets stay outside the repo: values come from the process environment, then
from ~/.hackathon-keys.env. The Nightshift bearer token is read from the file
Nightshift writes, so it is never copied anywhere.
"""

import os
from collections.abc import Mapping
from dataclasses import dataclass
from pathlib import Path

DEFAULT_KEYS_FILE = Path.home() / ".hackathon-keys.env"
DEFAULT_NIGHTSHIFT_TOKEN_FILE = (
    Path.home() / "Library/Application Support/ai.meterless.nightshift.m1m4/runtime-token"
)


@dataclass(frozen=True)
class Settings:
    nightshift_base_url: str = "http://127.0.0.1:8088/v1"
    nightshift_token: str = ""
    zetaris_base_url: str = ""
    zetaris_org_id: str = ""
    zetaris_api_key: str = ""
    sample_mode: bool = False

    @property
    def nightshift_configured(self) -> bool:
        return bool(self.nightshift_base_url and self.nightshift_token)

    @property
    def zetaris_configured(self) -> bool:
        return bool(self.zetaris_base_url and self.zetaris_org_id and self.zetaris_api_key)


def _read_env_file(path: Path) -> dict[str, str]:
    if not path.is_file():
        return {}
    values = {}
    for line in path.read_text().splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, _, value = line.partition("=")
        values[key.strip()] = value.strip().strip('"').strip("'")
    return values


def _read_token(path: Path) -> str:
    return path.read_text().strip() if path.is_file() else ""


def load_settings(
    env: Mapping[str, str] | None = None,
    keys_file: Path = DEFAULT_KEYS_FILE,
    nightshift_token_file: Path = DEFAULT_NIGHTSHIFT_TOKEN_FILE,
) -> Settings:
    merged = {**_read_env_file(keys_file), **(os.environ if env is None else env)}
    token_file = Path(merged.get("NIGHTSHIFT_TOKEN_FILE", nightshift_token_file))
    return Settings(
        nightshift_base_url=merged.get("NIGHTSHIFT_BASE_URL", Settings.nightshift_base_url),
        nightshift_token=merged.get("METERLESS_RUNTIME_TOKEN") or _read_token(token_file),
        zetaris_base_url=merged.get("ZETARIS_BASE_URL", ""),
        zetaris_org_id=merged.get("ZETARIS_ORG_ID", ""),
        zetaris_api_key=merged.get("ZETARIS_API_KEY", ""),
        sample_mode=merged.get("SAMPLE_MODE", "").lower() in {"1", "true", "yes"},
    )
