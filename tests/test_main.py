"""Tests for Multi-Personality Number Game V0."""

from __future__ import annotations

import random

import pytest

from game.history import GameHistory
from main import (
    GameState,
    apply_add_outcome,
    apply_reject_outcome,
    calculate_bust_probability,
    collect_votes,
    count_majority,
    process_round,
    validate_offer,
)


class TestMajorityVoteAggregation:
    def test_add_majority_when_three_add(self):
        from main import PersonaVote

        votes = [
            PersonaVote("A", "📊", "ADD", 0.8, "yes"),
            PersonaVote("B", "📊", "ADD", 0.7, "yes"),
            PersonaVote("C", "📊", "ADD", 0.6, "yes"),
            PersonaVote("D", "📊", "REJECT", 0.9, "no"),
            PersonaVote("E", "📊", "REJECT", 0.5, "no"),
        ]
        assert count_majority(votes) == "ADD"

    def test_reject_majority_when_three_reject(self):
        from main import PersonaVote

        votes = [
            PersonaVote("A", "🛡️", "REJECT", 0.8, "no"),
            PersonaVote("B", "🛡️", "REJECT", 0.7, "no"),
            PersonaVote("C", "🛡️", "REJECT", 0.6, "no"),
            PersonaVote("D", "🛡️", "ADD", 0.9, "yes"),
            PersonaVote("E", "🛡️", "ADD", 0.5, "yes"),
        ]
        assert count_majority(votes) == "REJECT"

    def test_reject_on_two_two_with_fifth_reject(self):
        from main import PersonaVote

        votes = [
            PersonaVote("A", "🎲", "ADD", 0.8, "yes"),
            PersonaVote("B", "🎲", "ADD", 0.7, "yes"),
            PersonaVote("C", "🎲", "REJECT", 0.6, "no"),
            PersonaVote("D", "🎲", "REJECT", 0.9, "no"),
            PersonaVote("E", "🎲", "REJECT", 0.5, "no"),
        ]
        assert count_majority(votes) == "REJECT"

    def test_collect_votes_returns_five_personas(self):
        history = GameHistory()
        votes = collect_votes(offer=50, score=0, round_num=1, history=history)
        assert len(votes) == 5
        names = {v.name for v in votes}
        assert names == {"Analyst", "Gambler", "Conservative", "Impulsive", "Strategist"}

    def test_persona_votes_are_deterministic(self):
        history = GameHistory()
        first = collect_votes(offer=30, score=10, round_num=2, history=history)
        second = collect_votes(offer=30, score=10, round_num=2, history=history)
        assert first == second


class TestScoreUpdateAfterSafeAdd:
    def test_safe_add_increments_score_and_round(self):
        rng_no_bust = _RngAlwaysAbove(0.99)
        state = GameState(score=20, round=3)
        history = GameHistory()
        state, votes, majority = process_round(
            state, offer=50, rng=rng_no_bust, history=history
        )
        assert majority == "ADD"
        assert state.game_over is False
        assert state.score == 70
        assert state.round == 4

    def test_apply_add_outcome_safe(self):
        rng = _RngAlwaysAbove(0.99)
        busted, new_score = apply_add_outcome(offer=25, score=40, rng=rng)
        assert busted is False
        assert new_score == 65


class TestBustEndsGameWithZeroScore:
    def test_bust_sets_zero_final_score(self):
        rng = _RngAlwaysBelow(0.01)
        state = GameState(score=100, round=5)
        history = GameHistory()
        state, _, majority = process_round(
            state, offer=80, rng=rng, history=history
        )
        assert majority == "ADD"
        assert state.game_over is True
        assert state.final_score == 0
        assert state.score == 0

    def test_apply_add_outcome_bust(self):
        rng = _RngAlwaysBelow(0.01)
        busted, new_score = apply_add_outcome(offer=50, score=200, rng=rng)
        assert busted is True
        assert new_score == 0


class TestRejectCashOut:
    def test_reject_preserves_score(self):
        from main import PersonaVote

        votes = [
            PersonaVote("A", "🛡️", "REJECT", 0.8, "no"),
            PersonaVote("B", "🛡️", "REJECT", 0.7, "no"),
            PersonaVote("C", "🛡️", "REJECT", 0.6, "no"),
            PersonaVote("D", "🛡️", "ADD", 0.9, "yes"),
            PersonaVote("E", "🛡️", "ADD", 0.5, "yes"),
        ]
        assert count_majority(votes) == "REJECT"
        assert apply_reject_outcome(150) == 150

    def test_process_round_reject_ends_game(self):
        rng = random.Random(0)
        state = GameState(score=75, round=2)
        history = GameHistory()
        state, votes, majority = process_round(
            state, offer=10, rng=rng, history=history
        )
        assert majority == "REJECT"
        assert state.game_over is True
        assert state.final_score == 75


class TestInputValidation:
    @pytest.mark.parametrize(
        "raw,expected_ok,expected_offer,expected_err",
        [
            ("50", True, 50, None),
            ("1", True, 1, None),
            ("100", True, 100, None),
            ("0", False, None, "Offer must be an integer from 1 to 100."),
            ("101", False, None, "Offer must be an integer from 1 to 100."),
            ("abc", False, None, "'abc' is not a valid integer."),
            ("", False, None, "Offer cannot be empty."),
            ("q", False, None, "quit"),
            ("QUIT", False, None, "quit"),
            (" 42 ", True, 42, None),
        ],
    )
    def test_validate_offer(self, raw, expected_ok, expected_offer, expected_err):
        ok, offer, err = validate_offer(raw)
        assert ok == expected_ok
        assert offer == expected_offer
        assert err == expected_err


class TestBustProbability:
    def test_formula_low_offer(self):
        assert calculate_bust_probability(1) == pytest.approx(0.02 + 1 / 240)

    def test_formula_at_max_offer(self):
        assert calculate_bust_probability(100) == pytest.approx(0.02 + 100 / 240)

    def test_formula_capped_at_seventy_percent(self):
        assert calculate_bust_probability(200) == pytest.approx(0.70)


class _RngAlwaysAbove:
    """Returns values strictly above threshold on every call."""

    def __init__(self, threshold: float) -> None:
        self._threshold = threshold

    def random(self) -> float:
        return min(1.0, self._threshold + 0.001)


class _RngAlwaysBelow:
    """Returns values strictly below threshold on every call."""

    def __init__(self, threshold: float) -> None:
        self._threshold = threshold

    def random(self) -> float:
        return max(0.0, self._threshold - 0.001)
