"""Tests for V4 post-game statistics."""

from __future__ import annotations

import json

import pytest

from agents.profiles import PERSONA_PROFILES
from game.history import CompletedRoundRecord, GameHistory, VoteRecord
from game.statistics import compute_game_statistics
from main import display_statistics_report, run_game, save_history_file, save_stats_file


def _vote(name: str, decision: str, confidence: float) -> VoteRecord:
    profile = next(p for p in PERSONA_PROFILES if p.name == name)
    return VoteRecord(
        name=profile.name,
        emoji=profile.emoji,
        decision=decision,
        confidence=confidence,
        reason=f"{name} voted {decision}.",
    )


def _round(
    round_number: int,
    offer: int,
    outcome: str,
    majority: str,
    votes: list[VoteRecord],
    score_before: int = 0,
    score_after: int = 0,
) -> CompletedRoundRecord:
    return CompletedRoundRecord(
        round_number=round_number,
        offer=offer,
        score_before=score_before,
        score_after=score_after,
        bust_probability=0.30,
        votes=votes,
        majority_decision=majority,
        outcome=outcome,
    )


def _known_history() -> GameHistory:
    """Two rounds with predictable persona metrics."""
    history = GameHistory()
    history.add_completed_round(
        _round(
            1,
            offer=40,
            outcome="SAFE_ADD",
            majority="ADD",
            score_before=0,
            score_after=40,
            votes=[
                _vote("Analyst", "ADD", 0.80),
                _vote("Gambler", "ADD", 0.90),
                _vote("Conservative", "REJECT", 0.70),
                _vote("Impulsive", "ADD", 0.60),
                _vote("Strategist", "REJECT", 0.50),
            ],
        )
    )
    history.add_completed_round(
        _round(
            2,
            offer=60,
            outcome="BUST",
            majority="ADD",
            score_before=40,
            score_after=0,
            votes=[
                _vote("Analyst", "ADD", 0.70),
                _vote("Gambler", "ADD", 0.85),
                _vote("Conservative", "REJECT", 0.75),
                _vote("Impulsive", "REJECT", 0.55),
                _vote("Strategist", "ADD", 0.65),
            ],
        )
    )
    return history


class TestPersonaStatistics:
    def test_analyst_metrics_from_known_history(self):
        stats = compute_game_statistics(_known_history(), final_score=0, final_outcome="BUST")
        analyst = next(p for p in stats.personas if p.name == "Analyst")

        assert analyst.rounds_voted == 2
        assert analyst.add_count == 2
        assert analyst.add_percentage == 100.0
        assert analyst.reject_count == 0
        assert analyst.reject_percentage == 0.0
        assert analyst.average_confidence == 0.75
        assert analyst.majority_alignment_rate == 100.0
        assert analyst.add_votes_before_safe_add == 1
        assert analyst.add_votes_before_bust == 1

    def test_conservative_metrics_from_known_history(self):
        stats = compute_game_statistics(_known_history(), final_score=0, final_outcome="BUST")
        conservative = next(p for p in stats.personas if p.name == "Conservative")

        assert conservative.rounds_voted == 2
        assert conservative.add_count == 0
        assert conservative.reject_count == 2
        assert conservative.reject_percentage == 100.0
        assert conservative.majority_alignment_rate == 0.0
        assert conservative.add_votes_before_safe_add == 0
        assert conservative.add_votes_before_bust == 0

    def test_strategist_metrics_from_known_history(self):
        stats = compute_game_statistics(_known_history(), final_score=0, final_outcome="BUST")
        strategist = next(p for p in stats.personas if p.name == "Strategist")

        assert strategist.rounds_voted == 2
        assert strategist.add_count == 1
        assert strategist.reject_count == 1
        assert strategist.add_percentage == 50.0
        assert strategist.reject_percentage == 50.0
        assert strategist.average_confidence == 0.57
        assert strategist.majority_alignment_rate == 50.0
        assert strategist.add_votes_before_bust == 1
        assert strategist.add_votes_before_safe_add == 0


class TestGameSummaryStatistics:
    def test_game_summary_from_known_history(self):
        stats = compute_game_statistics(_known_history(), final_score=0, final_outcome="BUST")

        assert stats.completed_rounds == 2
        assert stats.final_outcome == "BUST"
        assert stats.final_score == 0
        assert stats.average_offer == 50.0
        assert stats.add_majority_rounds == 2
        assert stats.reject_majority_rounds == 0
        assert stats.bust_count == 1

    def test_cash_out_summary(self):
        history = GameHistory()
        history.add_completed_round(
            _round(
                1,
                offer=20,
                outcome="CASH_OUT",
                majority="REJECT",
                score_before=50,
                score_after=50,
                votes=[_vote("Analyst", "REJECT", 0.60)],
            )
        )
        stats = compute_game_statistics(history, final_score=50, final_outcome="CASH_OUT")

        assert stats.final_outcome == "CASH_OUT"
        assert stats.final_score == 50
        assert stats.reject_majority_rounds == 1
        assert stats.bust_count == 0


class TestZeroCompletedRounds:
    def test_empty_history_produces_safe_defaults(self):
        stats = compute_game_statistics(GameHistory(), final_score=0, final_outcome="QUIT")

        assert stats.completed_rounds == 0
        assert stats.final_outcome == "QUIT"
        assert stats.average_offer == 0.0
        assert stats.add_majority_rounds == 0
        assert stats.bust_count == 0
        assert len(stats.personas) == 5
        assert all(p.rounds_voted == 0 for p in stats.personas)
        assert all(p.add_percentage == 0.0 for p in stats.personas)


class TestStatisticsPersistence:
    def test_stats_file_saves_json(self, tmp_path):
        stats = compute_game_statistics(_known_history(), final_score=0, final_outcome="BUST")
        out = tmp_path / "stats.json"
        save_stats_file(stats, str(out))
        data = json.loads(out.read_text(encoding="utf-8"))
        assert data["completed_rounds"] == 2
        assert data["personas"][0]["name"] == "Analyst"

    def test_history_file_includes_statistics(self, tmp_path):
        history = _known_history()
        stats = compute_game_statistics(history, final_score=0, final_outcome="BUST")
        out = tmp_path / "combined.json"
        save_history_file(history, str(out), statistics=stats)
        data = json.loads(out.read_text(encoding="utf-8"))
        assert len(data["rounds"]) == 2
        assert data["statistics"]["bust_count"] == 1
        assert data["statistics"]["personas"][0]["rounds_voted"] >= 0


class TestCliIntegration:
    def test_run_game_writes_stats_and_combined_history(self, tmp_path, capsys):
        history_path = tmp_path / "history.json"
        stats_path = tmp_path / "stats.json"
        inputs = iter(["50", "q"])
        rng = type("R", (), {"random": lambda self: 0.99})()

        run_game(
            mock=True,
            input_fn=lambda: next(inputs),
            history_file=str(history_path),
            stats_file=str(stats_path),
            rng=rng,
        )

        history_data = json.loads(history_path.read_text(encoding="utf-8"))
        stats_data = json.loads(stats_path.read_text(encoding="utf-8"))
        output = capsys.readouterr().out

        assert "statistics" in history_data
        assert history_data["statistics"]["completed_rounds"] == 1
        assert stats_data["completed_rounds"] == 1
        assert "Post-Game Statistics" in output
        assert "Behavioral patterns only" in output
        assert "success rate" not in output.lower()

    def test_display_statistics_handles_zero_rounds(self, capsys):
        stats = compute_game_statistics(GameHistory(), final_score=0, final_outcome="QUIT")
        display_statistics_report(stats)
        output = capsys.readouterr().out
        assert "Completed rounds: 0" in output
        assert "no votes recorded" in output.lower()
