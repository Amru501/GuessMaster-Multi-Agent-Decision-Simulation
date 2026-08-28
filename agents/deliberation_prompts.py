"""Deliberation-stage persona prompts."""

from __future__ import annotations

import json
from typing import TYPE_CHECKING

from agents.profiles import (
    PERSONA_PROFILES,
    PersonaProfile,
    _bullet_list,
    _history_section,
    _risk_tolerance_section,
)
from game.engine import PersonaVote
from models.schemas import PersonaLLMResponse

if TYPE_CHECKING:
    from agents.adaptation import PersonaRiskAdaptation


def build_deliberation_prompt(
    profile: PersonaProfile,
    *,
    score: int,
    round_num: int,
    offer: int,
    bust_probability: float,
    history_summary: str,
    deliberation_brief: str,
    own_initial: PersonaVote,
    adaptive: bool = False,
    risk_adaptation: PersonaRiskAdaptation | None = None,
    relationship_context: str | None = None,
) -> str:
    bust_pct = bust_probability * 100
    schema = PersonaLLMResponse.model_json_schema()
    schema_json = json.dumps(schema, indent=2)
    history_block = _history_section(profile, history_summary)
    risk_block = _risk_tolerance_section(
        profile, adaptive=adaptive, risk_adaptation=risk_adaptation
    )
    own_pct = int(round(own_initial.confidence * 100))
    relationship_block = ""
    if relationship_context:
        relationship_block = f"\n{relationship_context}\n"

    return f"""You are {profile.name} {profile.emoji}.

Role / identity:
{profile.role_identity}

Your objective:
{profile.objective}

{risk_block}
Decision philosophy:
{profile.decision_philosophy}

Behavioral tendencies:
{_bullet_list(profile.behavioral_tendencies)}

Communication style:
{profile.communication_style}

Things you avoid:
{_bullet_list(profile.anti_patterns)}

Deliberation stage — you already cast an initial independent vote:
- Your initial vote: {own_initial.decision} ({own_pct}% confidence) — {own_initial.reason}

All personas' initial votes (for reference only):
{deliberation_brief}
{relationship_block}
Critically evaluate the arguments above. You may keep or change your vote, but do NOT
blindly follow the majority or peer pressure. Decide in character as {profile.name}.

Do not calculate the vote count, majority, or game outcome. Submit your FINAL vote only.
{history_block}
Game state (unchanged):
- Current score: {score}
- Round: {round_num}
- Offer: {offer}
- Bust probability if ADD wins: {bust_pct:.1f}%

Rules reminder:
- REJECT means the player cashes out with the current score ({score}).
- ADD means the offer may be added to the score, but there is a {bust_pct:.1f}% chance
  of busting and losing everything (final score becomes 0).

Return ONLY a JSON object matching this schema (no markdown, no extra text):
{schema_json}

Required fields:
- decision: "ADD" or "REJECT"
- confidence: float from 0.0 to 1.0
- reason: short non-empty string explaining your FINAL vote
"""
