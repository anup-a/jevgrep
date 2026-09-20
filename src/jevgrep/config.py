"""Credentials and endpoint resolution, validated at the boundary."""

from __future__ import annotations

import os
from collections.abc import Mapping
from dataclasses import dataclass, field
from pathlib import Path

DEFAULT_BASE_URL = "https://ai-gateway.vercel.sh/v4/ai"
DEFAULT_MODEL = "typesafe-ai/jev"

# The gateway only serves the evaluation model under this path; /v1 and /v3 are 404s.
EVALUATION_PATH = "evaluation-model"

# jev-ultrafast and friends already export TYPESAFE_*, so accept those as a fallback.
_KEY_VARS = ("JEVGREP_API_KEY", "TYPESAFE_API_KEY")
_BASE_URL_VARS = ("JEVGREP_BASE_URL", "TYPESAFE_BASE_URL")
_MODEL_VARS = ("JEVGREP_MODEL", "TYPESAFE_MODEL")


class ConfigError(Exception):
    """Raised when the tool is not configured well enough to make a request."""


@dataclass(frozen=True)
class Config:
    api_key: str = field(repr=False)  # never let this reach a log line or traceback
    endpoint: str
    model: str


def _first_set(env: Mapping[str, str], names: tuple[str, ...]) -> str | None:
    for name in names:
        value = env.get(name)
        if value and value.strip():
            return value.strip()
    return None


def load_config(env: Mapping[str, str] | None = None) -> Config:
    """Build a Config from environment variables, raising ConfigError if unusable."""
    env = os.environ if env is None else env

    api_key = _first_set(env, _KEY_VARS)
    if not api_key:
        raise ConfigError(
            "JEVGREP_API_KEY is not set. Export it, or put it in a .env file "
            "next to where you are running jevgrep (see .env.example)."
        )

    base_url = _first_set(env, _BASE_URL_VARS) or DEFAULT_BASE_URL
    if not base_url.startswith(("http://", "https://")):
        raise ConfigError(f"JEVGREP_BASE_URL must be an http(s) URL, got {base_url!r}")

    return Config(
        api_key=api_key,
        endpoint=f"{base_url.rstrip('/')}/{EVALUATION_PATH}",
        model=_first_set(env, _MODEL_VARS) or DEFAULT_MODEL,
    )


def read_dotenv(path: Path) -> dict[str, str]:
    """Parse a .env file into a dict. Absent or unreadable files yield no values."""
    try:
        text = path.read_text(encoding="utf-8")
    except (OSError, UnicodeDecodeError):
        return {}

    values: dict[str, str] = {}
    for line in text.splitlines():
        stripped = line.strip()
        if not stripped or stripped.startswith("#") or "=" not in stripped:
            continue
        name, _, value = stripped.partition("=")
        values[name.strip()] = value.strip().strip("'\"")
    return values


def environment_with_dotenv(directory: Path | None = None) -> dict[str, str]:
    """Process environment, with a local .env filling in anything it does not define."""
    directory = Path.cwd() if directory is None else directory
    return {**read_dotenv(directory / ".env"), **os.environ}
