"""Ollama configuration loaded from environment variables."""

from __future__ import annotations

import os
from dataclasses import dataclass

from dotenv import load_dotenv

DEFAULT_HOST = "http://localhost:11434"
DEFAULT_TIMEOUT_SECONDS = 180.0
DEFAULT_KEEP_ALIVE = "10m"


class OllamaConfigError(Exception):
    """Raised when Ollama environment configuration is invalid."""


@dataclass(frozen=True)
class OllamaConfig:
    host: str
    model: str
    timeout_seconds: float
    keep_alive: str


def _parse_timeout(raw: str | None) -> float:
    if raw is None or not raw.strip():
        return DEFAULT_TIMEOUT_SECONDS

    try:
        value = float(raw.strip())
    except ValueError as exc:
        raise OllamaConfigError(
            f"OLLAMA_TIMEOUT_SECONDS must be a positive number, got '{raw}'."
        ) from exc

    if value <= 0:
        raise OllamaConfigError(
            f"OLLAMA_TIMEOUT_SECONDS must be a positive number, got {value}."
        )

    return value


def load_ollama_config() -> OllamaConfig:
    load_dotenv()

    host = os.getenv("OLLAMA_HOST", DEFAULT_HOST).strip() or DEFAULT_HOST
    model = os.getenv("OLLAMA_MODEL", "").strip()
    timeout_seconds = _parse_timeout(os.getenv("OLLAMA_TIMEOUT_SECONDS"))
    keep_alive = os.getenv("OLLAMA_KEEP_ALIVE", DEFAULT_KEEP_ALIVE).strip() or DEFAULT_KEEP_ALIVE

    if not model:
        raise OllamaConfigError(
            "OLLAMA_MODEL is missing. Set it in .env to an installed local model name."
        )

    return OllamaConfig(
        host=host,
        model=model,
        timeout_seconds=timeout_seconds,
        keep_alive=keep_alive,
    )
