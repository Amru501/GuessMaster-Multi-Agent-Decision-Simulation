"""Bounded risk-tolerance adaptation from completed round history."""

from __future__ import annotations

from pydantic import BaseModel, Field

from agents.profiles import PERSONA_PROFILES, PersonaProfile, get_profile
from game.history import GameHistory, RoundOutcome

ADJUSTMENT_PER_SAFE_ADD = 0.03
ADJUSTMENT_PER_BUST = -0.03
MIN_ADJUSTMENT = -0.15
MAX_ADJUSTMENT = 0.15


class PersonaRiskAdaptation(BaseModel):
    name: str
    base_risk_tolerance: float
    adjustment: float = Field(ge=MIN_ADJUSTMENT, le=MAX_ADJUSTMENT)
    effective_risk_tolerance: float = Field(ge=0.0, le=1.0)


def clamp_adjustment(value: float) -> float:
    return max(MIN_ADJUSTMENT, min(MAX_ADJUSTMENT, value))


def compute_raw_adjustment(history: GameHistory, persona_name: str) -> float:
    """Sum transparent deltas from completed rounds; REJECT votes are ignored."""
    raw = 0.0
    for record in history.rounds:
        vote = next((v for v in record.votes if v.name == persona_name), None)
        if vote is None or vote.decision != "ADD":
            continue
        if record.outcome == RoundOutcome.SAFE_ADD.value:
            raw += ADJUSTMENT_PER_SAFE_ADD
        elif record.outcome == RoundOutcome.BUST.value:
            raw += ADJUSTMENT_PER_BUST
    return raw


def compute_persona_adaptation(
    history: GameHistory, profile: PersonaProfile
) -> PersonaRiskAdaptation:
    adjustment = round(clamp_adjustment(compute_raw_adjustment(history, profile.name)), 2)
    effective = round(max(0.0, min(1.0, profile.risk_tolerance + adjustment)), 2)
    return PersonaRiskAdaptation(
        name=profile.name,
        base_risk_tolerance=profile.risk_tolerance,
        adjustment=adjustment,
        effective_risk_tolerance=effective,
    )


def compute_all_adaptations(history: GameHistory) -> dict[str, PersonaRiskAdaptation]:
    return {
        profile.name: compute_persona_adaptation(history, profile)
        for profile in PERSONA_PROFILES
    }


def get_persona_adaptation(history: GameHistory, persona_name: str) -> PersonaRiskAdaptation:
    return compute_persona_adaptation(history, get_profile(persona_name))
