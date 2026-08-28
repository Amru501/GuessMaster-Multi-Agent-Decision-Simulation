"""Deterministic mock voters for arbitrary agent rosters."""

from __future__ import annotations

from agents.deliberation import DeliberationRoundResult
from agents.personas import (
    _collect_initial_mock_votes as _collect_core_mock_votes,
    _mock_final_vote,
)
from agents.profiles import PERSONA_PROFILES, PersonaProfile
from game.engine import PersonaVote
from game.history import GameHistory
from game.rules import calculate_bust_probability

_CORE_NAMES = {p.name for p in PERSONA_PROFILES}


def _generated_mock_vote(
    profile: PersonaProfile,
    offer: int,
    bust_prob: float,
    score: int,
    round_num: int,
) -> PersonaVote:
    signal = (
        round_num * 7919
        + offer * 997
        + score * 101
        + sum(ord(c) for c in profile.name)
    ) % 1000
    threshold = profile.risk_tolerance * 1000
    adjusted = threshold + offer * 2 - bust_prob * 400
    decision = "ADD" if signal < adjusted else "REJECT"
    confidence = round(min(0.99, 0.35 + abs(signal - adjusted) / 1000), 2)
    reason = (
        f"{profile.communication_style}: {decision} on offer {offer} "
        f"(risk tol {profile.risk_tolerance:.2f})."
    )
    return PersonaVote(profile.name, profile.emoji, decision, confidence, reason)


def _generated_mock_final_vote(
    profile: PersonaProfile,
    initial: PersonaVote,
    all_initial: list[PersonaVote],
    offer: int,
    score: int,
    round_num: int,
) -> PersonaVote:
    add_count = sum(1 for vote in all_initial if vote.decision == "ADD")
    majority_add = add_count > len(all_initial) / 2
    flip_signal = (round_num * 17 + offer * 11 + len(profile.name)) % 7 == 0
    if flip_signal and initial.decision == "ADD" and not majority_add:
        decision = "REJECT"
        reason = "Deliberation cooled enthusiasm after weak ADD support."
    elif flip_signal and initial.decision == "REJECT" and majority_add:
        decision = "ADD"
        reason = "Deliberation shifted view toward the ADD coalition."
    else:
        decision = initial.decision
        reason = f"Final vote unchanged: {decision}."
    confidence = round(min(0.99, initial.confidence + 0.04), 2)
    return PersonaVote(profile.name, profile.emoji, decision, confidence, reason)


def collect_mock_votes_for_roster(
    profiles: tuple[PersonaProfile, ...],
    offer: int,
    score: int,
    round_num: int,
    history: GameHistory | None = None,
) -> list[PersonaVote]:
    bust_prob = calculate_bust_probability(offer)
    if profiles == PERSONA_PROFILES:
        from agents.personas import collect_mock_votes

        return collect_mock_votes(offer, score, round_num, history)

    votes: list[PersonaVote] = []
    core_by_name = {v.name: v for v in _collect_core_mock_votes(offer, score, round_num)}
    for profile in profiles:
        if profile.name in _CORE_NAMES:
            votes.append(core_by_name[profile.name])
        else:
            votes.append(
                _generated_mock_vote(profile, offer, bust_prob, score, round_num)
            )
    return votes


def collect_mock_deliberation_for_roster(
    profiles: tuple[PersonaProfile, ...],
    offer: int,
    score: int,
    round_num: int,
    history: GameHistory | None = None,
) -> DeliberationRoundResult:
    if profiles == PERSONA_PROFILES:
        from agents.personas import collect_mock_deliberation_votes

        return collect_mock_deliberation_votes(offer, score, round_num, history)

    initial = collect_mock_votes_for_roster(
        profiles, offer, score, round_num, history
    )
    final: list[PersonaVote] = []
    for profile, vote in zip(profiles, initial, strict=True):
        if profile.name in _CORE_NAMES:
            final.append(_mock_final_vote(vote, initial, offer, score, round_num))
        else:
            final.append(
                _generated_mock_final_vote(
                    profile, vote, initial, offer, score, round_num
                )
            )
    return DeliberationRoundResult(initial_votes=initial, final_votes=final)
