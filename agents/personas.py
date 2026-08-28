"""Persona definitions and deterministic V0 mock voters."""

from __future__ import annotations

from agents.deliberation import DeliberationRoundResult, build_deliberation_brief
from agents.profiles import get_profile
from game.engine import PersonaVote
from game.history import GameHistory
from game.rules import calculate_bust_probability

mock_initial_vote_calls = 0
mock_final_vote_calls = 0


def _vote_analyst(offer: int, bust_prob: float, score: int, round_num: int) -> PersonaVote:
    profile = get_profile("Analyst")
    expected_gain = offer * (1 - bust_prob)
    threshold = 15.0 + score * 0.01
    if expected_gain >= threshold:
        decision = "ADD"
        confidence = min(0.95, 0.55 + (expected_gain - threshold) / 40)
        reason = f"Expected gain {expected_gain:.1f} meets logic threshold {threshold:.1f}."
    else:
        decision = "REJECT"
        confidence = min(0.95, 0.55 + (threshold - expected_gain) / 40)
        reason = f"Expected gain {expected_gain:.1f} below threshold {threshold:.1f}."
    return PersonaVote(profile.name, profile.emoji, decision, round(confidence, 2), reason)


def _vote_gambler(offer: int, bust_prob: float, score: int, round_num: int) -> PersonaVote:
    profile = get_profile("Gambler")
    if bust_prob < 0.75:
        decision = "ADD"
        confidence = min(0.99, 0.65 + (0.75 - bust_prob) * 0.45)
        reason = f"Bust risk {bust_prob:.0%} — worth the gamble for {offer} points."
    else:
        decision = "REJECT"
        confidence = min(0.95, 0.55 + (bust_prob - 0.75) * 1.8)
        reason = f"Bust risk {bust_prob:.0%} is too high even for me."
    return PersonaVote(profile.name, profile.emoji, decision, round(confidence, 2), reason)


def _vote_conservative(offer: int, bust_prob: float, score: int, round_num: int) -> PersonaVote:
    profile = get_profile("Conservative")
    if bust_prob <= 0.25:
        decision = "ADD"
        confidence = min(0.95, 0.70 + (0.25 - bust_prob) * 0.8)
        reason = f"Low bust risk {bust_prob:.0%} — safe enough to proceed."
    else:
        decision = "REJECT"
        confidence = min(0.95, 0.65 + min(0.30, bust_prob - 0.25))
        reason = f"Bust risk {bust_prob:.0%} exceeds conservative tolerance."
    return PersonaVote(profile.name, profile.emoji, decision, round(confidence, 2), reason)


def _vote_impulsive(offer: int, bust_prob: float, score: int, round_num: int) -> PersonaVote:
    profile = get_profile("Impulsive")
    impulse = (round_num * 7919 + offer * 997 + score * 101) % 100
    if impulse < 55:
        decision = "ADD"
        reason = f"Gut says go — impulse score {impulse}/100."
    else:
        decision = "REJECT"
        reason = f"Gut says stop — impulse score {impulse}/100."
    confidence = round(0.40 + (impulse % 45) / 100, 2)
    return PersonaVote(profile.name, profile.emoji, decision, confidence, reason)


def _vote_strategist(offer: int, bust_prob: float, score: int, round_num: int) -> PersonaVote:
    profile = get_profile("Strategist")
    risk_adjusted = offer * (1 - bust_prob) - score * bust_prob * 0.1
    if risk_adjusted >= 10:
        decision = "ADD"
        confidence = min(0.92, 0.55 + (risk_adjusted - 10) / 35)
        reason = (
            f"Risk-adjusted value {risk_adjusted:.1f} favors adding "
            f"(score {score}, offer {offer})."
        )
    else:
        decision = "REJECT"
        confidence = min(0.92, 0.55 + (10 - risk_adjusted) / 35)
        reason = f"Risk-adjusted value {risk_adjusted:.1f} — protect score {score}."
    return PersonaVote(profile.name, profile.emoji, decision, round(confidence, 2), reason)


_MOCK_VOTERS = (
    _vote_analyst,
    _vote_gambler,
    _vote_conservative,
    _vote_impulsive,
    _vote_strategist,
)


def _collect_initial_mock_votes(
    offer: int, score: int, round_num: int
) -> list[PersonaVote]:
    bust_prob = calculate_bust_probability(offer)
    return [voter(offer, bust_prob, score, round_num) for voter in _MOCK_VOTERS]


def _mock_final_vote(
    initial: PersonaVote,
    all_initial: list[PersonaVote],
    offer: int,
    score: int,
    round_num: int,
) -> PersonaVote:
    """Deterministic deliberation final vote — may differ from initial."""
    add_count = sum(1 for v in all_initial if v.decision == "ADD")
    name = initial.name

    if name == "Analyst":
        decision = initial.decision
        reason = f"After deliberation, logic still supports {decision}."
    elif name == "Gambler":
        if initial.decision == "REJECT" and add_count >= 3:
            decision = "ADD"
            reason = "Deliberation hype — joining the ADD camp."
        elif initial.decision == "ADD" and add_count <= 1:
            decision = "REJECT"
            reason = "Deliberation cooled my gamble instinct."
        else:
            decision = initial.decision
            reason = f"Still feeling {decision} after hearing others."
    elif name == "Conservative":
        decision = initial.decision
        reason = f"Deliberation confirms cautious {decision}."
    elif name == "Impulsive":
        flip = (round_num * 13 + offer * 7 + score + ord(name[0])) % 5 == 0
        decision = "REJECT" if initial.decision == "ADD" and flip else initial.decision
        if flip and initial.decision == "ADD":
            reason = "Second thoughts — flipping to REJECT."
        else:
            reason = f"Gut still says {decision}."
    elif name == "Strategist":
        if initial.decision == "ADD" and add_count <= 2:
            decision = "REJECT"
            reason = "Deliberation revealed weak ADD support — protecting score."
        elif initial.decision == "REJECT" and add_count >= 4:
            decision = "ADD"
            reason = "Strong ADD coalition after deliberation."
        else:
            decision = initial.decision
            reason = f"Strategic read unchanged: {decision}."
    else:
        decision = initial.decision
        reason = initial.reason

    confidence = round(min(0.99, initial.confidence + 0.05), 2)
    return PersonaVote(initial.name, initial.emoji, decision, confidence, reason)


def collect_mock_votes(
    offer: int, score: int, round_num: int, history: GameHistory | None = None
) -> list[PersonaVote]:
    global mock_initial_vote_calls
    mock_initial_vote_calls += 5
    return _collect_initial_mock_votes(offer, score, round_num)


def collect_mock_deliberation_votes(
    offer: int, score: int, round_num: int, history: GameHistory | None = None
) -> DeliberationRoundResult:
    global mock_initial_vote_calls, mock_final_vote_calls
    initial = _collect_initial_mock_votes(offer, score, round_num)
    mock_initial_vote_calls += 5
    final = [
        _mock_final_vote(v, initial, offer, score, round_num) for v in initial
    ]
    mock_final_vote_calls += 5
    return DeliberationRoundResult(initial_votes=initial, final_votes=final)


def reset_mock_vote_counters() -> None:
    global mock_initial_vote_calls, mock_final_vote_calls
    mock_initial_vote_calls = 0
    mock_final_vote_calls = 0
