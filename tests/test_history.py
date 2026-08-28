"""Tests for V3 round history and bounded agent memory."""

from __future__ import annotations

import json

import pytest

from agents.profiles import PROFILE_BY_NAME, build_persona_prompt
from game.engine import PersonaVote
from game.history import (
    CompletedRoundRecord,
    GameHistory,
    RoundOutcome,
    VoteRecord,
    build_completed_round_record,
    resolve_round_outcome,
)
from main import process_round, run_game, save_history_file


def _sample_vote(name: str = "Analyst", decision: str = "ADD") -> PersonaVote:
    profile = PROFILE_BY_NAME[name]
    return PersonaVote(profile.name, profile.emoji, decision, 0.8, "Test reason.")


def _sample_record(
    round_number: int = 1,
    outcome: str = "SAFE_ADD",
    score_after: int = 50,
) -> CompletedRoundRecord:
    return CompletedRoundRecord(
        round_number=round_number,
        offer=30,
        score_before=20,
        score_after=score_after,
        bust_probability=0.30,
        votes=[VoteRecord(name="Analyst", emoji="📊", decision="ADD", confidence=0.8, reason="ok")],
        majority_decision="ADD",
        outcome=outcome,
    )


class TestHistoryRecording:
    def test_resolve_outcomes(self):
        assert resolve_round_outcome("REJECT", game_over=True, score_after=100) == "CASH_OUT"
        assert resolve_round_outcome("ADD", game_over=True, score_after=0) == "BUST"
        assert resolve_round_outcome("ADD", game_over=False, score_after=50) == "SAFE_ADD"

    def test_build_completed_round_record(self):
        votes = [_sample_vote("Analyst"), _sample_vote("Gambler")]
        record = build_completed_round_record(
            round_number=2,
            offer=40,
            score_before=10,
            score_after=50,
            bust_probability=0.383,
            votes=votes,
            majority_decision="ADD",
            outcome="SAFE_ADD",
        )
        assert record.round_number == 2
        assert record.offer == 40
        assert record.score_before == 10
        assert record.score_after == 50
        assert len(record.votes) == 2
        assert record.votes[0].reason == "Test reason."

    def test_process_round_records_safe_add_in_history(self):
        from game.engine import GameState

        history = GameHistory()
        state = GameState(score=0, round=1)
        rng = __import__("random").Random(0)

        class _Rng:
            def random(self):
                return 0.99

        state, votes, majority = process_round(
            state, offer=50, rng=_Rng(), history=history
        )
        assert len(history.rounds) == 0  # recording happens in main, not process_round

    def test_run_game_records_completed_rounds(self, tmp_path):
        path = tmp_path / "game-history.json"
        inputs = iter(["50", "q"])
        rng = type("R", (), {"random": lambda self: 0.99})()

        run_game(
            mock=True,
            input_fn=lambda: next(inputs),
            history_file=str(path),
            rng=rng,
        )

        data = json.loads(path.read_text(encoding="utf-8"))
        assert len(data["rounds"]) == 1
        assert "statistics" in data
        record = data["rounds"][0]
        assert record["round_number"] == 1
        assert record["offer"] == 50
        assert record["outcome"] == "SAFE_ADD"
        assert len(record["votes"]) == 5


class TestJsonSerialization:
    def test_to_json_round_trip(self):
        history = GameHistory()
        history.add_completed_round(_sample_record())
        raw = history.to_json()
        parsed = json.loads(raw)
        assert parsed["rounds"][0]["outcome"] == "SAFE_ADD"
        restored = GameHistory.from_json(raw)
        assert restored.rounds[0].round_number == 1

    def test_save_history_file(self, tmp_path):
        from game.statistics import compute_game_statistics

        history = GameHistory()
        history.add_completed_round(_sample_record(round_number=3))
        stats = compute_game_statistics(history, final_score=50, final_outcome="QUIT")
        out = tmp_path / "game.json"
        save_history_file(history, str(out), statistics=stats)
        data = json.loads(out.read_text(encoding="utf-8"))
        assert data["rounds"][0]["round_number"] == 3
        assert data["statistics"]["completed_rounds"] == 1


class TestCancelledRoundExclusion:
    def test_cancelled_round_not_recorded(self, tmp_path):
        from agents.service import AgentService, AgentVoteError
        from ai.ollama_client import OllamaClient, OllamaResponseError

        class FakeClient:
            def chat(self, **kwargs):
                raise OllamaResponseError("timeout")

            def list(self):
                return type("List", (), {"models": []})()

        service = AgentService(
            OllamaClient(host="http://localhost:11434", client=FakeClient()),
            model="qwen2.5:3b",
        )
        out = tmp_path / "cancelled.json"
        inputs = iter(["50", "q"])

        run_game(
            mock=False,
            agent_service=service,
            input_fn=lambda: next(inputs),
            history_file=str(out),
        )

        data = json.loads(out.read_text(encoding="utf-8"))
        assert data["rounds"] == []


class TestBoundedHistory:
    def test_bounded_summary_empty(self):
        history = GameHistory()
        assert history.bounded_summary() == "No prior completed rounds."

    def test_bounded_summary_includes_only_safe_add(self):
        history = GameHistory()
        history.add_completed_round(_sample_record(round_number=1, outcome="SAFE_ADD", score_after=30))
        history.add_completed_round(_sample_record(round_number=2, outcome="BUST", score_after=0))
        summary = history.bounded_summary(limit=3)
        assert "Round 1" in summary
        assert "Round 2" not in summary
        assert "outcome SAFE_ADD" in summary

    def test_bounded_summary_limits_to_three(self):
        history = GameHistory()
        for i in range(1, 6):
            history.add_completed_round(
                _sample_record(round_number=i, outcome="SAFE_ADD", score_after=i * 10)
            )
        summary = history.bounded_summary(limit=3)
        assert "Round 3" in summary
        assert "Round 4" in summary
        assert "Round 5" in summary
        assert "Round 1" not in summary
        assert "Round 2" not in summary

    def test_bounded_summary_facts_only(self):
        history = GameHistory()
        history.add_completed_round(_sample_record())
        summary = history.bounded_summary()
        assert "offer 30" in summary
        assert "majority ADD" in summary
        assert "score after 50" in summary
        assert "Test reason" not in summary


class TestPromptInclusion:
    def test_prompt_includes_history_summary(self):
        profile = PROFILE_BY_NAME["Analyst"]
        summary = "Round 1: offer 20, majority ADD, outcome SAFE_ADD, score after 20"
        prompt = build_persona_prompt(
            profile,
            score=40,
            round_num=2,
            offer=30,
            bust_probability=0.30,
            history_summary=summary,
        )
        assert summary in prompt

    def test_strategist_prompt_uses_history_for_long_term_score(self):
        profile = PROFILE_BY_NAME["Strategist"]
        summary = "Round 1: offer 20, majority ADD, outcome SAFE_ADD, score after 20"
        prompt = build_persona_prompt(
            profile,
            score=40,
            round_num=2,
            offer=30,
            bust_probability=0.30,
            history_summary=summary,
        )
        assert "protect or pursue long-term score" in prompt
        assert summary in prompt

    def test_prompt_omits_history_when_none(self):
        profile = PROFILE_BY_NAME["Gambler"]
        prompt = build_persona_prompt(
            profile,
            score=0,
            round_num=1,
            offer=10,
            bust_probability=0.133,
        )
        assert "Recent rounds" not in prompt

    def test_prompt_never_includes_current_round_votes(self):
        profile = PROFILE_BY_NAME["Analyst"]
        summary = "Round 1: offer 20, majority ADD, outcome SAFE_ADD, score after 20"
        prompt = build_persona_prompt(
            profile,
            score=40,
            round_num=2,
            offer=30,
            bust_probability=0.30,
            history_summary=summary,
        )
        assert "cannot see other personas" in prompt.lower()
        assert "current-round votes" not in prompt  # explicit exclusion in independence line

    def test_round_outcome_enum_includes_cancelled(self):
        assert RoundOutcome.CANCELLED.value == "CANCELLED"
