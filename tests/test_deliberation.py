"""Tests for V6 optional two-stage deliberation."""

from __future__ import annotations

import random

import pytest

from agents.deliberation import DeliberationRoundResult
from agents.personas import (
    collect_mock_deliberation_votes,
    collect_mock_votes,
    reset_mock_vote_counters,
)
from agents.service import AgentVoteError
from game.engine import PersonaVote, process_deliberation_round, process_round
from game.history import GameHistory, build_completed_round_record
from game.rules import count_majority
from main import run_game


class TestIndependentModeVoteCount:
    def test_one_vote_stage_per_persona(self):
        reset_mock_vote_counters()
        state = __import__("main").GameState()
        history = GameHistory()
        rng = random.Random(0)

        process_round(state, offer=50, rng=rng, history=history, collect_votes_fn=collect_mock_votes)

        from agents.personas import mock_final_vote_calls, mock_initial_vote_calls

        assert mock_initial_vote_calls == 5
        assert mock_final_vote_calls == 0


class TestDeliberationModeVoteStages:
    def test_two_vote_stages_per_persona(self):
        reset_mock_vote_counters()
        state = __import__("main").GameState()
        history = GameHistory()
        rng = random.Random(0)

        process_deliberation_round(
            state,
            offer=50,
            rng=rng,
            history=history,
            collect_deliberation_fn=collect_mock_deliberation_votes,
        )

        from agents.personas import mock_final_vote_calls, mock_initial_vote_calls

        assert mock_initial_vote_calls == 5
        assert mock_final_vote_calls == 5


class TestFinalVotesDetermineMajority:
    def test_majority_uses_final_votes_not_initial(self):
        initial = [
            PersonaVote("Analyst", "📊", "ADD", 0.8, "a"),
            PersonaVote("Gambler", "🎲", "ADD", 0.8, "b"),
            PersonaVote("Conservative", "🛡️", "ADD", 0.8, "c"),
            PersonaVote("Impulsive", "⚡", "REJECT", 0.8, "d"),
            PersonaVote("Strategist", "♟️", "REJECT", 0.8, "e"),
        ]
        final = [
            PersonaVote("Analyst", "📊", "REJECT", 0.8, "a"),
            PersonaVote("Gambler", "🎲", "REJECT", 0.8, "b"),
            PersonaVote("Conservative", "🛡️", "REJECT", 0.8, "c"),
            PersonaVote("Impulsive", "⚡", "ADD", 0.8, "d"),
            PersonaVote("Strategist", "♟️", "ADD", 0.8, "e"),
        ]
        assert count_majority(initial) == "ADD"
        assert count_majority(final) == "REJECT"

        def fixed_deliberation(offer, score, round_num, history):
            return DeliberationRoundResult(initial_votes=initial, final_votes=final)

        state = __import__("main").GameState(score=10, round=1)
        history = GameHistory()
        rng = random.Random(0)

        state, returned_initial, returned_final, majority = process_deliberation_round(
            state,
            offer=30,
            rng=rng,
            history=history,
            collect_deliberation_fn=fixed_deliberation,
        )

        assert returned_initial == initial
        assert returned_final == final
        assert majority == "REJECT"
        assert state.game_over is True
        assert state.final_score == 10


class TestHistoryRetainsBothStages:
    def test_completed_record_stores_initial_and_final_votes(self):
        initial = [
            PersonaVote("Analyst", "📊", "ADD", 0.7, "init"),
            PersonaVote("Gambler", "🎲", "REJECT", 0.6, "init"),
            PersonaVote("Conservative", "🛡️", "ADD", 0.8, "init"),
            PersonaVote("Impulsive", "⚡", "REJECT", 0.5, "init"),
            PersonaVote("Strategist", "♟️", "ADD", 0.9, "init"),
        ]
        final = [
            PersonaVote("Analyst", "📊", "REJECT", 0.75, "final"),
            PersonaVote("Gambler", "🎲", "REJECT", 0.65, "final"),
            PersonaVote("Conservative", "🛡️", "REJECT", 0.85, "final"),
            PersonaVote("Impulsive", "⚡", "REJECT", 0.55, "final"),
            PersonaVote("Strategist", "♟️", "REJECT", 0.95, "final"),
        ]
        history = GameHistory()
        record = build_completed_round_record(
            round_number=1,
            offer=40,
            score_before=0,
            score_after=0,
            bust_probability=0.38,
            votes=final,
            majority_decision="REJECT",
            outcome="CASH_OUT",
            initial_votes=initial,
            deliberation_mode=True,
        )
        history.add_completed_round(record)

        saved = history.rounds[0]
        assert saved.deliberation_mode is True
        assert saved.initial_votes is not None
        assert len(saved.initial_votes) == 5
        assert len(saved.votes) == 5
        assert saved.votes[0].reason == "final"
        assert saved.initial_votes[0].reason == "init"


class TestCancelledRoundsOnFailure:
    def test_initial_stage_failure_cancels_without_score_change(self):
        def fail_initial(offer, score, round_num, history):
            raise AgentVoteError("Analyst", "timeout", stage="initial")

        state = __import__("main").GameState(score=25, round=2)
        history = GameHistory()
        rng = random.Random(0)

        with pytest.raises(AgentVoteError) as exc_info:
            process_deliberation_round(
                state,
                offer=50,
                rng=rng,
                history=history,
                collect_deliberation_fn=fail_initial,
            )

        assert exc_info.value.stage == "initial"
        assert state.score == 25
        assert state.round == 2
        assert not state.game_over
        assert len(history.rounds) == 0

    def test_final_stage_failure_cancels_without_score_change(self):
        def deliberation_fail_final(offer, score, round_num, history):
            collect_mock_votes(offer, score, round_num, history)
            raise AgentVoteError("Gambler", "parse error", stage="final")

        state = __import__("main").GameState(score=30, round=1)
        history = GameHistory()
        rng = random.Random(0)

        with pytest.raises(AgentVoteError) as exc_info:
            process_deliberation_round(
                state,
                offer=50,
                rng=rng,
                history=history,
                collect_deliberation_fn=deliberation_fail_final,
            )

        assert exc_info.value.stage == "final"
        assert state.score == 30
        assert state.round == 1
        assert not state.game_over

    def test_run_game_deliberation_cancels_round_on_failure(self, capsys):
        from agents.service import AgentService
        from ai.ollama_client import OllamaClient

        class FakeClient:
            def chat(self, **kwargs):
                raise RuntimeError("timeout")

            def list(self):
                return type("List", (), {"models": []})()

        client = OllamaClient(host="http://localhost:11434", client=FakeClient())
        service = AgentService(client, model="qwen2.5:3b")

        inputs = iter(["50", "q"])
        run_game(
            mock=False,
            deliberate=True,
            agent_service=service,
            input_fn=lambda: next(inputs),
        )

        combined = capsys.readouterr().out
        assert "initial stage" in combined
        assert "Round 1 cancelled" in combined
        assert "score unchanged (0)" in combined


class TestDeliberationDisplay:
    def test_run_game_mock_deliberation_shows_panels(self, capsys):
        inputs = iter(["50", "q"])
        run_game(
            mock=True,
            deliberate=True,
            input_fn=lambda: next(inputs),
        )
        combined = capsys.readouterr().out
        assert "Initial votes (independent)" in combined
        assert "Deliberation brief:" in combined
        assert "Final votes (after deliberation)" in combined
        assert "Vote changes:" in combined
        assert "MAJORITY:" in combined
