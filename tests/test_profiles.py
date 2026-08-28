"""Tests for V2 persona behavioral profiles."""

from __future__ import annotations

import pytest
from pydantic import ValidationError

from agents.profiles import (
    PERSONA_PROFILES,
    PROFILE_BY_NAME,
    PersonaProfile,
    build_persona_prompt,
)
from main import collect_mock_votes, format_vote


EXPECTED_NAMES = {"Analyst", "Gambler", "Conservative", "Impulsive", "Strategist"}


class TestProfileValidity:
    def test_all_five_profiles_defined(self):
        assert len(PERSONA_PROFILES) == 5
        assert {p.name for p in PERSONA_PROFILES} == EXPECTED_NAMES

    @pytest.mark.parametrize("profile", PERSONA_PROFILES, ids=lambda p: p.name)
    def test_required_fields_populated(self, profile: PersonaProfile):
        assert profile.name
        assert profile.emoji
        assert profile.role_identity
        assert profile.objective
        assert profile.decision_philosophy
        assert profile.communication_style
        assert len(profile.behavioral_tendencies) >= 1
        assert len(profile.anti_patterns) >= 1
        assert 0.0 <= profile.risk_tolerance <= 1.0

    def test_risk_tolerance_out_of_range_rejected(self):
        with pytest.raises(ValidationError):
            PersonaProfile(
                name="Test",
                emoji="🧪",
                role_identity="test",
                objective="test",
                risk_tolerance=1.5,
                decision_philosophy="test",
                behavioral_tendencies=["one"],
                communication_style="test",
                anti_patterns=["one"],
            )

    def test_empty_behavioral_tendencies_rejected(self):
        with pytest.raises(ValidationError):
            PersonaProfile(
                name="Test",
                emoji="🧪",
                role_identity="test",
                objective="test",
                risk_tolerance=0.5,
                decision_philosophy="test",
                behavioral_tendencies=[],
                communication_style="test",
                anti_patterns=["one"],
            )


class TestProfileUniqueness:
    def test_names_are_unique(self):
        names = [p.name for p in PERSONA_PROFILES]
        assert len(names) == len(set(names))

    def test_emojis_are_unique(self):
        emojis = [p.emoji for p in PERSONA_PROFILES]
        assert len(emojis) == len(set(emojis))

    def test_profile_by_name_lookup(self):
        for profile in PERSONA_PROFILES:
            assert PROFILE_BY_NAME[profile.name] == profile


class TestPromptConstruction:
    @pytest.mark.parametrize("profile", PERSONA_PROFILES, ids=lambda p: p.name)
    def test_prompt_includes_profile_fields(self, profile: PersonaProfile):
        prompt = build_persona_prompt(
            profile,
            score=42,
            round_num=3,
            offer=50,
            bust_probability=0.466,
        )
        assert profile.name in prompt
        assert profile.emoji in prompt
        assert profile.role_identity in prompt
        assert profile.objective in prompt
        assert f"risk tolerance: {profile.risk_tolerance:.2f}" in prompt.lower()
        assert profile.decision_philosophy in prompt
        assert profile.communication_style in prompt
        for tendency in profile.behavioral_tendencies:
            assert tendency in prompt
        for anti in profile.anti_patterns:
            assert anti in prompt

    def test_prompt_includes_game_state(self):
        profile = PERSONA_PROFILES[0]
        prompt = build_persona_prompt(
            profile,
            score=100,
            round_num=5,
            offer=75,
            bust_probability=0.675,
        )
        assert "Current score: 100" in prompt
        assert "Round: 5" in prompt
        assert "Offer: 75" in prompt
        assert "67.5%" in prompt

    def test_prompt_stresses_independence(self):
        profile = PERSONA_PROFILES[0]
        prompt = build_persona_prompt(
            profile, score=0, round_num=1, offer=10, bust_probability=0.133
        )
        assert "independently" in prompt.lower()
        assert "cannot see other personas" in prompt.lower()

    def test_prompt_includes_json_schema(self):
        profile = PERSONA_PROFILES[0]
        prompt = build_persona_prompt(
            profile, score=0, round_num=1, offer=10, bust_probability=0.133
        )
        assert '"decision"' in prompt
        assert '"confidence"' in prompt
        assert '"reason"' in prompt


class TestMockVotesUseProfiles:
    def test_mock_votes_include_profile_emojis(self):
        from game.history import GameHistory

        votes = collect_mock_votes(offer=50, score=10, round_num=1, history=GameHistory())
        for vote in votes:
            profile = PROFILE_BY_NAME[vote.name]
            assert vote.emoji == profile.emoji

    def test_format_vote_shows_emoji(self):
        profile = PROFILE_BY_NAME["Analyst"]
        from game.engine import PersonaVote

        vote = PersonaVote(profile.name, profile.emoji, "ADD", 0.8, "Looks good.")
        formatted = format_vote(vote)
        assert profile.emoji in formatted
        assert "Analyst" in formatted

    def test_risk_tolerance_ordering_reflects_persona_design(self):
        conservative = PROFILE_BY_NAME["Conservative"]
        gambler = PROFILE_BY_NAME["Gambler"]
        assert conservative.risk_tolerance < gambler.risk_tolerance
