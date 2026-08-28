"""Tests for LLM response parsing and validation."""

from __future__ import annotations

import json

import pytest
from pydantic import ValidationError

from models.schemas import PersonaLLMResponse, parse_persona_response


class TestValidLLMResponses:
    def test_parse_valid_add_response(self):
        payload = json.dumps(
            {"decision": "ADD", "confidence": 0.82, "reason": "Good expected value."}
        )
        result = parse_persona_response(payload)
        assert result.decision == "ADD"
        assert result.confidence == pytest.approx(0.82)
        assert result.reason == "Good expected value."

    def test_parse_valid_reject_response(self):
        payload = json.dumps(
            {"decision": "REJECT", "confidence": 0.65, "reason": "Too risky."}
        )
        result = parse_persona_response(payload)
        assert result.decision == "REJECT"
        assert result.confidence == pytest.approx(0.65)

    def test_confidence_boundaries(self):
        low = parse_persona_response(
            json.dumps({"decision": "ADD", "confidence": 0.0, "reason": "Unsure."})
        )
        high = parse_persona_response(
            json.dumps({"decision": "REJECT", "confidence": 1.0, "reason": "Certain."})
        )
        assert low.confidence == 0.0
        assert high.confidence == 1.0


class TestMalformedLLMResponses:
    def test_rejects_invalid_json(self):
        with pytest.raises(ValidationError):
            parse_persona_response("{not json")

    def test_rejects_invalid_decision(self):
        payload = json.dumps(
            {"decision": "MAYBE", "confidence": 0.5, "reason": "Unclear."}
        )
        with pytest.raises(ValidationError):
            parse_persona_response(payload)

    def test_rejects_confidence_above_one(self):
        payload = json.dumps(
            {"decision": "ADD", "confidence": 1.5, "reason": "Overconfident."}
        )
        with pytest.raises(ValidationError):
            parse_persona_response(payload)

    def test_rejects_confidence_below_zero(self):
        payload = json.dumps(
            {"decision": "REJECT", "confidence": -0.1, "reason": "Negative."}
        )
        with pytest.raises(ValidationError):
            parse_persona_response(payload)

    def test_rejects_blank_reason(self):
        payload = json.dumps({"decision": "ADD", "confidence": 0.5, "reason": "   "})
        with pytest.raises(ValidationError):
            parse_persona_response(payload)

    def test_rejects_missing_fields(self):
        with pytest.raises(ValidationError):
            parse_persona_response(json.dumps({"decision": "ADD"}))

    def test_strips_whitespace_from_reason(self):
        result = parse_persona_response(
            json.dumps({"decision": "ADD", "confidence": 0.5, "reason": "  valid  "})
        )
        assert result.reason == "valid"


class TestOllamaClientStructuredParsing:
    def test_chat_structured_parses_valid_response(self):
        from ai.ollama_client import OllamaClient

        payload = json.dumps(
            {"decision": "ADD", "confidence": 0.77, "reason": "Looks good."}
        )

        class FakeMessage:
            content = payload

        class FakeResponse:
            message = FakeMessage()

        class FakeClient:
            def chat(self, **kwargs):
                assert kwargs["stream"] is False
                assert kwargs["format"] == PersonaLLMResponse.model_json_schema()
                assert "keep_alive" in kwargs
                assert kwargs["options"]["num_predict"] == 128
                return FakeResponse()

            def list(self):
                return type("List", (), {"models": []})()

        client = OllamaClient(host="http://localhost:11434", client=FakeClient())
        result = client.chat_structured(model="qwen2.5:3b", prompt="vote")
        assert result.decision == "ADD"
        assert result.confidence == pytest.approx(0.77)

    def test_chat_structured_rejects_empty_content(self):
        from ai.ollama_client import OllamaClient, OllamaResponseError

        class FakeMessage:
            content = ""

        class FakeResponse:
            message = FakeMessage()

        class FakeClient:
            def chat(self, **kwargs):
                return FakeResponse()

            def list(self):
                return type("List", (), {"models": []})()

        client = OllamaClient(host="http://localhost:11434", client=FakeClient())
        with pytest.raises(OllamaResponseError, match="empty content"):
            client.chat_structured(model="qwen2.5:3b", prompt="vote")

    def test_chat_structured_rejects_malformed_json(self):
        from ai.ollama_client import OllamaClient, OllamaResponseError

        class FakeMessage:
            content = '{"decision": "MAYBE", "confidence": 0.5, "reason": "nope"}'

        class FakeResponse:
            message = FakeMessage()

        class FakeClient:
            def chat(self, **kwargs):
                return FakeResponse()

            def list(self):
                return type("List", (), {"models": []})()

        client = OllamaClient(host="http://localhost:11434", client=FakeClient())
        with pytest.raises(OllamaResponseError, match="Failed to validate"):
            client.chat_structured(model="qwen2.5:3b", prompt="vote")


class TestAgentServiceWithMockClient:
    def test_collect_votes_returns_five_persona_votes(self):
        from agents.service import AgentService
        from ai.ollama_client import OllamaClient
        from game.history import GameHistory

        call_count = 0
        decisions = ["ADD", "REJECT", "ADD", "REJECT", "ADD"]

        class FakeMessage:
            def __init__(self, content: str) -> None:
                self.content = content

        class FakeResponse:
            def __init__(self, content: str) -> None:
                self.message = FakeMessage(content)

        class FakeClient:
            def chat(self, **kwargs):
                nonlocal call_count
                decision = decisions[call_count]
                call_count += 1
                payload = json.dumps(
                    {
                        "decision": decision,
                        "confidence": 0.6,
                        "reason": f"Vote {call_count}.",
                    }
                )
                return FakeResponse(payload)

            def list(self):
                return type("List", (), {"models": []})()

        service = AgentService(
            OllamaClient(host="http://localhost:11434", client=FakeClient()),
            model="qwen2.5:3b",
        )
        votes = service.collect_votes(offer=50, score=10, round_num=1, history=GameHistory())
        assert len(votes) == 5
        assert call_count == 5
        assert {v.name for v in votes} == {
            "Analyst",
            "Gambler",
            "Conservative",
            "Impulsive",
            "Strategist",
        }

    def test_agent_failure_raises_with_persona_name(self):
        from agents.service import AgentService, AgentVoteError
        from ai.ollama_client import OllamaClient, OllamaResponseError
        from game.history import GameHistory

        class FakeClient:
            def __init__(self) -> None:
                self.calls = 0

            def chat(self, **kwargs):
                self.calls += 1
                if self.calls == 2:
                    raise OllamaResponseError("timeout")
                payload = json.dumps(
                    {"decision": "ADD", "confidence": 0.5, "reason": "ok"}
                )
                return type(
                    "R",
                    (),
                    {"message": type("M", (), {"content": payload})()},
                )()

            def list(self):
                return type("List", (), {"models": []})()

        service = AgentService(
            OllamaClient(host="http://localhost:11434", client=FakeClient()),
            model="qwen2.5:3b",
        )
        with pytest.raises(AgentVoteError, match="Gambler"):
            service.collect_votes(offer=50, score=0, round_num=1, history=GameHistory())

    def test_verify_connection_and_model_with_fake_client(self):
        from ai.ollama_client import OllamaClient

        class ModelEntry:
            def __init__(self, name: str) -> None:
                self.model = name

        class FakeClient:
            def list(self):
                return type("List", (), {"models": [ModelEntry("qwen2.5:3b")]})()

            def chat(self, **kwargs):
                raise AssertionError("chat should not be called during verify")

        client = OllamaClient(host="http://localhost:11434", client=FakeClient())
        client.verify_connection()
        client.verify_model("qwen2.5:3b")

    def test_verify_model_missing_raises(self):
        from ai.ollama_client import OllamaClient, OllamaModelError

        class FakeClient:
            def list(self):
                return type("List", (), {"models": []})()

        client = OllamaClient(host="http://localhost:11434", client=FakeClient())
        with pytest.raises(OllamaModelError, match="not installed"):
            client.verify_model("missing-model")

    def test_verify_connection_failure_raises(self):
        from ai.ollama_client import OllamaClient, OllamaConnectionError

        class FakeClient:
            def list(self):
                raise ConnectionError("refused")

        client = OllamaClient(host="http://localhost:11434", client=FakeClient())
        with pytest.raises(OllamaConnectionError, match="Cannot reach Ollama"):
            client.verify_connection()
