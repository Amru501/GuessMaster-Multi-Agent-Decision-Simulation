"""Ollama client — the only module that imports the ollama package."""

from __future__ import annotations

from typing import Any, Protocol

from ollama import Client
from ollama import ResponseError as OllamaResponseErrorBase

from ai.config import DEFAULT_KEEP_ALIVE, DEFAULT_TIMEOUT_SECONDS
from models.schemas import PersonaLLMResponse

DEFAULT_TEMPERATURE = 0.4
DEFAULT_NUM_PREDICT = 128

WARMUP_PROMPT = """Warmup ping. Return ONLY a JSON object matching this schema:
{"decision": "ADD" or "REJECT", "confidence": 0.0-1.0, "reason": "non-empty string"}
Use: {"decision": "ADD", "confidence": 0.01, "reason": "warmup"}"""


class OllamaConnectionError(Exception):
    """Raised when Ollama is unreachable at the configured host."""


class OllamaModelError(Exception):
    """Raised when the configured model is missing or not installed."""


class OllamaResponseError(Exception):
    """Raised when Ollama returns a malformed or invalid response."""


class ChatClient(Protocol):
    def chat(self, **kwargs: Any) -> Any: ...

    def list(self) -> Any: ...


class OllamaClient:
    def __init__(
        self,
        host: str,
        client: ChatClient | None = None,
        timeout: float = DEFAULT_TIMEOUT_SECONDS,
        keep_alive: str = DEFAULT_KEEP_ALIVE,
    ) -> None:
        self.host = host
        self._keep_alive = keep_alive
        self._client = client or Client(host=host, timeout=timeout)

    @property
    def keep_alive(self) -> str:
        return self._keep_alive

    def verify_connection(self) -> None:
        try:
            self._client.list()
        except Exception as exc:
            raise OllamaConnectionError(
                f"Cannot reach Ollama at {self.host}. "
                "Ensure Ollama is running and OLLAMA_HOST is correct."
            ) from exc

    def verify_model(self, model: str) -> None:
        if not model or not model.strip():
            raise OllamaModelError(
                "OLLAMA_MODEL is missing. Set it in .env to an installed local model name."
            )

        try:
            listing = self._client.list()
        except Exception as exc:
            raise OllamaConnectionError(
                f"Cannot reach Ollama at {self.host} while checking models."
            ) from exc

        installed = {
            entry.model
            for entry in getattr(listing, "models", [])
            if getattr(entry, "model", None)
        }
        if model not in installed:
            available = ", ".join(sorted(installed)) if installed else "(none found)"
            raise OllamaModelError(
                f"Model '{model}' is not installed. Available models: {available}"
            )

    def chat_structured(
        self,
        *,
        model: str,
        prompt: str,
        temperature: float = DEFAULT_TEMPERATURE,
    ) -> PersonaLLMResponse:
        schema = PersonaLLMResponse.model_json_schema()
        try:
            response = self._client.chat(
                model=model,
                messages=[{"role": "user", "content": prompt}],
                format=schema,
                stream=False,
                keep_alive=self._keep_alive,
                options={
                    "temperature": temperature,
                    "num_predict": DEFAULT_NUM_PREDICT,
                },
            )
        except OllamaResponseErrorBase as exc:
            raise OllamaResponseError(f"Ollama request failed: {exc}") from exc
        except Exception as exc:
            raise OllamaResponseError(f"Ollama request failed: {exc}") from exc

        content = response.message.content
        if not content or not content.strip():
            raise OllamaResponseError("Ollama returned empty content.")

        try:
            return PersonaLLMResponse.model_validate_json(content)
        except Exception as exc:
            raise OllamaResponseError(
                f"Failed to validate structured response: {exc}"
            ) from exc

    def warmup(self, model: str) -> None:
        """Load the model with a small structured request."""
        self.chat_structured(model=model, prompt=WARMUP_PROMPT, temperature=0.0)
