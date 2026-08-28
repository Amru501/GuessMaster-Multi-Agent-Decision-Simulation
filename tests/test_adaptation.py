"""Tests for V5 bounded adaptive personalities."""

from __future__ import annotations

import copy

import pytest

from agents.adaptation import (
    ADJUSTMENT_PER_BUST,
    ADJUSTMENT_PER_SAFE_ADD,
    MAX_ADJUSTMENT,
    MIN_ADJUSTMENT,
    compute_all_adaptations,
    compute_persona_adaptation,
    compute_raw_adjustment,
)
from agents.profiles import PERSONA_PROFILES, PROFILE_BY_NAME, build_persona_prompt, get_profile
from game.history import CompletedRoundRecord, GameHistory, VoteRecord


def _vote(name: str, decision: str) -> VoteRecord:
    profile = get_profile(name)
    return VoteRecord(
        name=profile.name,
        emoji=profile.emoji,
        decision=decision,
        confidence=0.7,
        reason="test",
    )


def _round(
    round_number: int,
    outcome: str,
    majority: str,
    votes: list[VoteRecord],
) -> CompletedRoundRecord:
    return CompletedRoundRecord(
        round_number=round_number,
        offer=40,
        score_before=0,
        score_after=40 if outcome == "SAFE_ADD" else 0,
        bust_probability=0.30,
        votes=votes,
        majority_decision=majority,
        outcome=outcome,
    )


class TestAdaptationRules:
    def test_safe_add_increases_add_voter_tolerance(self):
        history = GameHistory()
        history.add_completed_round(
            _round(
                1,
                "SAFE_ADD",
                "ADD",
                [_vote("Analyst", "ADD"), _vote("Gambler", "REJECT")],
            )
        )
        analyst = compute_persona_adaptation(history, get_profile("Analyst"))
        gambler = compute_persona_adaptation(history, get_profile("Gambler"))

        assert analyst.adjustment == pytest.approx(ADJUSTMENT_PER_SAFE_ADD)
        assert analyst.effective_risk_tolerance == pytest.approx(0.45 + ADJUSTMENT_PER_SAFE_ADD)
        assert gambler.adjustment == 0.0
        assert gambler.effective_risk_tolerance == pytest.approx(0.85)

    def test_bust_decreases_add_voter_tolerance(self):
        history = GameHistory()
        history.add_completed_round(
            _round(
                1,
                "BUST",
                "ADD",
                [_vote("Gambler", "ADD"), _vote("Conservative", "REJECT")],
            )
        )
        gambler = compute_persona_adaptation(history, get_profile("Gambler"))

        assert gambler.adjustment == pytest.approx(ADJUSTMENT_PER_BUST)
        assert gambler.effective_risk_tolerance == pytest.approx(0.85 + ADJUSTMENT_PER_BUST)

    def test_reject_votes_do_not_change_adjustment(self):
        history = GameHistory()
        history.add_completed_round(
            _round(
                1,
                "BUST",
                "ADD",
                [_vote("Conservative", "REJECT")],
            )
        )
        conservative = compute_persona_adaptation(history, get_profile("Conservative"))
        assert conservative.adjustment == 0.0
        assert conservative.effective_risk_tolerance == 0.15

    def test_cash_out_round_does_not_adapt(self):
        history = GameHistory()
        history.add_completed_round(
            _round(
                1,
                "CASH_OUT",
                "REJECT",
                [_vote("Analyst", "ADD"), _vote("Strategist", "REJECT")],
            )
        )
        analyst = compute_persona_adaptation(history, get_profile("Analyst"))
        assert analyst.adjustment == 0.0


class TestAdaptationBounds:
    def test_adjustment_clamped_at_max(self):
        history = GameHistory()
        for i in range(10):
            history.add_completed_round(
                _round(i + 1, "SAFE_ADD", "ADD", [_vote("Gambler", "ADD")])
            )
        gambler = compute_persona_adaptation(history, get_profile("Gambler"))
        assert gambler.adjustment == MAX_ADJUSTMENT
        assert compute_raw_adjustment(history, "Gambler") > MAX_ADJUSTMENT

    def test_adjustment_clamped_at_min(self):
        history = GameHistory()
        for i in range(10):
            history.add_completed_round(
                _round(i + 1, "BUST", "ADD", [_vote("Gambler", "ADD")])
            )
        gambler = compute_persona_adaptation(history, get_profile("Gambler"))
        assert gambler.adjustment == MIN_ADJUSTMENT

    def test_effective_tolerance_clamped_to_unit_interval(self):
        history = GameHistory()
        for _ in range(10):
            history.add_completed_round(
                _round(1, "BUST", "ADD", [_vote("Conservative", "ADD")])
            )
        conservative = compute_persona_adaptation(history, get_profile("Conservative"))
        assert conservative.effective_risk_tolerance >= 0.0
        assert conservative.effective_risk_tolerance <= 1.0


class TestBaseProfilesImmutable:
    def test_base_profiles_not_mutated_after_adaptation(self):
        before = copy.deepcopy([p.model_dump() for p in PERSONA_PROFILES])
        history = GameHistory()
        history.add_completed_round(
            _round(1, "BUST", "ADD", [_vote("Analyst", "ADD")])
        )
        compute_all_adaptations(history)
        after = [p.model_dump() for p in PERSONA_PROFILES]
        assert before == after


class TestDisabledMode:
    def test_empty_history_zero_adjustment(self):
        adaptation = compute_persona_adaptation(GameHistory(), get_profile("Analyst"))
        assert adaptation.adjustment == 0.0
        assert adaptation.effective_risk_tolerance == adaptation.base_risk_tolerance

    def test_prompt_without_adaptive_uses_base_tolerance(self):
        profile = get_profile("Analyst")
        prompt = build_persona_prompt(
            profile,
            score=0,
            round_num=1,
            offer=50,
            bust_probability=0.46,
            adaptive=False,
        )
        assert "Your risk tolerance: 0.45" in prompt
        assert "Effective risk tolerance" not in prompt
        assert "adjusted" not in prompt.lower()

    def test_prompt_with_adaptive_shows_effective_tolerance(self):
        profile = get_profile("Analyst")
        history = GameHistory()
        history.add_completed_round(
            _round(1, "SAFE_ADD", "ADD", [_vote("Analyst", "ADD")])
        )
        adaptation = compute_persona_adaptation(history, profile)
        prompt = build_persona_prompt(
            profile,
            score=50,
            round_num=2,
            offer=40,
            bust_probability=0.38,
            adaptive=True,
            risk_adaptation=adaptation,
        )
        assert "Base risk tolerance: 0.45" in prompt
        assert "Effective risk tolerance:" in prompt
        assert "adjusted +0.03 from recent completed outcomes" in prompt

    def test_statistics_adaptive_fields_only_when_enabled(self):
        from game.statistics import compute_game_statistics

        history = GameHistory()
        history.add_completed_round(
            _round(1, "SAFE_ADD", "ADD", [_vote("Analyst", "ADD")])
        )
        fixed = compute_game_statistics(history, final_score=40, final_outcome="QUIT", adaptive=False)
        adaptive = compute_game_statistics(history, final_score=40, final_outcome="QUIT", adaptive=True)

        assert fixed.adaptive_mode is False
        assert fixed.personas[0].risk_tolerance_adjustment is None
        assert adaptive.adaptive_mode is True
        assert adaptive.personas[0].risk_tolerance_adjustment == pytest.approx(0.03)
