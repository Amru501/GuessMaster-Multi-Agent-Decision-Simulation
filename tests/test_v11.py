"""Tests for V1.1 Ollama reliability and configuration."""

from __future__ import annotations

import json
from io import StringIO

import pytest

from ai.config import (
    DEFAULT_HOST,
    DEFAULT_KEEP_ALIVE,
    DEFAULT_TIMEOUT_SECONDS,
    OllamaConfigError,
    load_ollama_config,
)
from main import GameState, prepare_ollama_service, run_game


class TestOllamaConfig:
    def test_default_values(self, monkeypatch):
        monkeypatch.delenv("OLLAMA_HOST", raising=False)
        monkeypatch.delenv("OLLAMA_TIMEOUT_SECONDS", raising=False)
        monkeypatch.delenv("OLLAMA_KEEP_ALIVE", raising=False)
        monkeypatch.setenv("OLLAMA_MODEL", "qwen2.5:3b")

        config = load_ollama_config()
        assert config.host == DEFAULT_HOST
        assert config.model == "qwen2.5:3b"
        assert config.timeout_seconds == DEFAULT_TIMEOUT_SECONDS
        assert config.keep_alive == DEFAULT_KEEP_ALIVE

    def test_custom_values(self, monkeypatch):
        monkeypatch.setenv("OLLAMA_HOST", "http://127.0.0.1:11434")
        monkeypatch.setenv("OLLAMA_MODEL", "qwen2.5:3b")
        monkeypatch.setenv("OLLAMA_TIMEOUT_SECONDS", "300")
        monkeypatch.setenv("OLLAMA_KEEP_ALIVE", "5m")

        config = load_ollama_config()
        assert config.host == "http://127.0.0.1:11434"
        assert config.timeout_seconds == 300.0
        assert config.keep_alive == "5m"

    @pytest.mark.parametrize(
        "timeout_value",
        ["abc", "0", "-10", "-0.5"],
    )
    def test_invalid_timeout_raises(self, monkeypatch, timeout_value):
        monkeypatch.setenv("OLLAMA_MODEL", "qwen2.5:3b")
        monkeypatch.setenv("OLLAMA_TIMEOUT_SECONDS", timeout_value)

        with pytest.raises(OllamaConfigError, match="OLLAMA_TIMEOUT_SECONDS"):
            load_ollama_config()

    def test_missing_model_raises(self, monkeypatch):
        monkeypatch.setenv("OLLAMA_MODEL", "")

        with pytest.raises(OllamaConfigError, match="OLLAMA_MODEL"):
            load_ollama_config()


class TestWarmup:
    def test_warmup_success(self):
        from ai.config import OllamaConfig
        from ai.ollama_client import OllamaClient

        payload = json.dumps(
            {"decision": "ADD", "confidence": 0.01, "reason": "warmup"}
        )

        class FakeMessage:
            content = payload

        class FakeResponse:
            message = FakeMessage()

        class FakeClient:
            def chat(self, **kwargs):
                return FakeResponse()

            def list(self):
                return type(
                    "List",
                    (),
                    {"models": [type("M", (), {"model": "qwen2.5:3b"})()]},
                )()

        config = OllamaConfig(
            host="http://localhost:11434",
            model="qwen2.5:3b",
            timeout_seconds=180.0,
            keep_alive="10m",
        )
        client = OllamaClient(
            host=config.host,
            client=FakeClient(),
            timeout=config.timeout_seconds,
            keep_alive=config.keep_alive,
        )
        from agents.service import AgentService

        service = AgentService(client, model=config.model)
        service.warmup()

    def test_prepare_ollama_service_warmup_failure_exits(self, monkeypatch):
        from ai.config import OllamaConfig
        from ai.ollama_client import OllamaResponseError

        class FakeOllamaClient:
            def __init__(self, **kwargs):
                pass

            def verify_connection(self):
                pass

            def verify_model(self, model):
                pass

            def warmup(self, model):
                raise OllamaResponseError("connection timed out")

        monkeypatch.setattr("main.OllamaClient", FakeOllamaClient)

        config = OllamaConfig(
            host="http://localhost:11434",
            model="qwen2.5:3b",
            timeout_seconds=180.0,
            keep_alive="10m",
        )

        stderr = StringIO()
        monkeypatch.setattr("sys.stderr", stderr)

        with pytest.raises(SystemExit) as exc_info:
            prepare_ollama_service(config)

        assert exc_info.value.code == 1
        assert "Warm-up failed" in stderr.getvalue()
        assert "connection timed out" in stderr.getvalue()

    def test_prepare_ollama_service_success_prints_ready(self, monkeypatch, capsys):
        from ai.config import OllamaConfig

        class FakeOllamaClient:
            def __init__(self, **kwargs):
                pass

            def verify_connection(self):
                pass

            def verify_model(self, model):
                pass

        class FakeAgentService:
            def __init__(
                self,
                client,
                model,
                adaptive=False,
                relationships=False,
                profiles=None,
                max_concurrency=1,
                metrics=None,
            ):
                self._model = model
                self._adaptive = adaptive
                self._relationships = relationships

            @property
            def model(self):
                return self._model

            def warmup(self):
                pass

        monkeypatch.setattr("main.OllamaClient", FakeOllamaClient)
        monkeypatch.setattr("main.AgentService", FakeAgentService)

        config = OllamaConfig(
            host="http://localhost:11434",
            model="qwen2.5:3b",
            timeout_seconds=180.0,
            keep_alive="10m",
        )
        prepare_ollama_service(config)
        captured = capsys.readouterr()
        assert "Warming up local model…" in captured.out
        assert "Model ready." in captured.out


class TestChatRequestOptions:
    def test_keep_alive_and_num_predict_passed_to_client(self):
        from ai.ollama_client import DEFAULT_NUM_PREDICT, OllamaClient
        from models.schemas import PersonaLLMResponse

        payload = json.dumps(
            {"decision": "ADD", "confidence": 0.77, "reason": "Looks good."}
        )
        captured_kwargs: dict = {}

        class FakeMessage:
            content = payload

        class FakeResponse:
            message = FakeMessage()

        class FakeClient:
            def chat(self, **kwargs):
                captured_kwargs.update(kwargs)
                return FakeResponse()

            def list(self):
                return type("List", (), {"models": []})()

        client = OllamaClient(
            host="http://localhost:11434",
            client=FakeClient(),
            keep_alive="10m",
        )
        client.chat_structured(model="qwen2.5:3b", prompt="vote")

        assert captured_kwargs["keep_alive"] == "10m"
        assert captured_kwargs["stream"] is False
        assert captured_kwargs["format"] == PersonaLLMResponse.model_json_schema()
        assert captured_kwargs["options"]["num_predict"] == DEFAULT_NUM_PREDICT

    def test_warmup_uses_structured_schema(self):
        from ai.ollama_client import OllamaClient, WARMUP_PROMPT
        from models.schemas import PersonaLLMResponse

        payload = json.dumps(
            {"decision": "ADD", "confidence": 0.01, "reason": "warmup"}
        )
        captured_kwargs: dict = {}

        class FakeMessage:
            content = payload

        class FakeResponse:
            message = FakeMessage()

        class FakeClient:
            def chat(self, **kwargs):
                captured_kwargs.update(kwargs)
                return FakeResponse()

            def list(self):
                return type("List", (), {"models": []})()

        client = OllamaClient(
            host="http://localhost:11434",
            client=FakeClient(),
            keep_alive="5m",
        )
        client.warmup(model="qwen2.5:3b")

        assert captured_kwargs["format"] == PersonaLLMResponse.model_json_schema()
        assert captured_kwargs["messages"][0]["content"] == WARMUP_PROMPT
        assert captured_kwargs["keep_alive"] == "5m"


class TestRoundCancellationOnAgentFailure:
    def test_agent_failure_cancels_round_without_changing_score(self, capsys):
        from agents.service import AgentService
        from ai.ollama_client import OllamaClient, OllamaResponseError

        class FakeClient:
            def __init__(self) -> None:
                self.calls = 0

            def chat(self, **kwargs):
                self.calls += 1
                raise OllamaResponseError("timeout")

            def list(self):
                return type("List", (), {"models": []})()

        service = AgentService(
            OllamaClient(host="http://localhost:11434", client=FakeClient()),
            model="qwen2.5:3b",
        )

        inputs = iter(["50", "q"])

        run_game(
            mock=False,
            agent_service=service,
            input_fn=lambda: next(inputs),
        )

        combined = capsys.readouterr().out
        assert "Agent failure: Analyst" in combined
        assert "Technical error: Ollama request failed: timeout" in combined
        assert "Round 1 cancelled" in combined
        assert "score unchanged (0)" in combined
        assert "GAME OVER" not in combined
        assert "BUST —" not in combined
        assert "Thanks for playing!" in combined

    def test_process_round_state_unchanged_when_collect_votes_raises(self):
        from agents.service import AgentVoteError
        from game.history import GameHistory
        from main import process_round

        def failing_collector(offer, score, round_num, history):
            raise AgentVoteError("Analyst", "timeout")

        state = GameState(score=42, round=3)
        rng = __import__("random").Random(0)
        history = GameHistory()

        with pytest.raises(AgentVoteError):
            process_round(
                state,
                offer=50,
                rng=rng,
                history=history,
                collect_votes_fn=failing_collector,
            )

        assert state.score == 42
        assert state.round == 3
        assert not state.game_over
        assert state.final_score is None

    def test_agent_service_model_property(self):
        from agents.service import AgentService
        from ai.ollama_client import OllamaClient

        class FakeClient:
            def list(self):
                return type("List", (), {"models": []})()

        service = AgentService(
            OllamaClient(host="http://localhost:11434", client=FakeClient()),
            model="qwen2.5:3b",
        )
        assert service.model == "qwen2.5:3b"
