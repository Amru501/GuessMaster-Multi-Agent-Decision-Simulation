"""Post-game statistics derived from completed round history."""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field

from agents.adaptation import compute_persona_adaptation
from agents.profiles import PERSONA_PROFILES, PROFILE_BY_NAME
from game.history import GameHistory, RoundOutcome

FinalOutcome = Literal["BUST", "CASH_OUT", "QUIT", "NONE"]


class PersonaStatistics(BaseModel):
    name: str
    emoji: str
    rounds_voted: int = 0
    add_count: int = 0
    add_percentage: float = 0.0
    reject_count: int = 0
    reject_percentage: float = 0.0
    average_confidence: float = 0.0
    majority_alignment_rate: float = 0.0
    add_votes_before_safe_add: int = 0
    add_votes_before_bust: int = 0
    base_risk_tolerance: float | None = None
    risk_tolerance_adjustment: float | None = None
    effective_risk_tolerance: float | None = None


class GameStatistics(BaseModel):
    completed_rounds: int = 0
    final_outcome: FinalOutcome = "NONE"
    final_score: int = 0
    average_offer: float = 0.0
    add_majority_rounds: int = 0
    reject_majority_rounds: int = 0
    bust_count: int = 0
    adaptive_mode: bool = False
    personas: list[PersonaStatistics] = Field(default_factory=list)


def _pct(part: int, total: int) -> float:
    if total == 0:
        return 0.0
    return round(part / total * 100, 2)


def compute_game_statistics(
    history: GameHistory,
    *,
    final_score: int,
    final_outcome: FinalOutcome,
    adaptive: bool = False,
) -> GameStatistics:
    """Derive behavioral metrics from completed history (not objective correctness)."""
    rounds = history.rounds
    persona_order = {p.name: p.emoji for p in PERSONA_PROFILES}

    accumulators: dict[str, dict] = {
        name: {
            "rounds_voted": 0,
            "add_count": 0,
            "reject_count": 0,
            "confidence_sum": 0.0,
            "majority_alignments": 0,
            "add_before_safe_add": 0,
            "add_before_bust": 0,
        }
        for name in persona_order
    }

    for record in rounds:
        for vote in record.votes:
            if vote.name not in accumulators:
                accumulators[vote.name] = {
                    "rounds_voted": 0,
                    "add_count": 0,
                    "reject_count": 0,
                    "confidence_sum": 0.0,
                    "majority_alignments": 0,
                    "add_before_safe_add": 0,
                    "add_before_bust": 0,
                }
                persona_order.setdefault(vote.name, vote.emoji)

            acc = accumulators[vote.name]
            acc["rounds_voted"] += 1
            acc["confidence_sum"] += vote.confidence

            if vote.decision == "ADD":
                acc["add_count"] += 1
                if record.outcome == RoundOutcome.SAFE_ADD.value:
                    acc["add_before_safe_add"] += 1
                elif record.outcome == RoundOutcome.BUST.value:
                    acc["add_before_bust"] += 1
            else:
                acc["reject_count"] += 1

            if vote.decision == record.majority_decision:
                acc["majority_alignments"] += 1

    persona_stats: list[PersonaStatistics] = []
    for name in persona_order:
        acc = accumulators.get(
            name,
            {
                "rounds_voted": 0,
                "add_count": 0,
                "reject_count": 0,
                "confidence_sum": 0.0,
                "majority_alignments": 0,
                "add_before_safe_add": 0,
                "add_before_bust": 0,
            },
        )
        voted = acc["rounds_voted"]
        adaptation_fields: dict = {}
        if adaptive and name in PROFILE_BY_NAME:
            adaptation = compute_persona_adaptation(history, PROFILE_BY_NAME[name])
            adaptation_fields = {
                "base_risk_tolerance": adaptation.base_risk_tolerance,
                "risk_tolerance_adjustment": adaptation.adjustment,
                "effective_risk_tolerance": adaptation.effective_risk_tolerance,
            }
        persona_stats.append(
            PersonaStatistics(
                name=name,
                emoji=persona_order[name],
                rounds_voted=voted,
                add_count=acc["add_count"],
                add_percentage=_pct(acc["add_count"], voted),
                reject_count=acc["reject_count"],
                reject_percentage=_pct(acc["reject_count"], voted),
                average_confidence=round(acc["confidence_sum"] / voted, 2) if voted else 0.0,
                majority_alignment_rate=_pct(acc["majority_alignments"], voted),
                add_votes_before_safe_add=acc["add_before_safe_add"],
                add_votes_before_bust=acc["add_before_bust"],
                **adaptation_fields,
            )
        )

    offers = [r.offer for r in rounds]
    average_offer = round(sum(offers) / len(offers), 2) if offers else 0.0

    return GameStatistics(
        completed_rounds=len(rounds),
        final_outcome=final_outcome,
        final_score=final_score,
        average_offer=average_offer,
        add_majority_rounds=sum(1 for r in rounds if r.majority_decision == "ADD"),
        reject_majority_rounds=sum(1 for r in rounds if r.majority_decision == "REJECT"),
        bust_count=sum(1 for r in rounds if r.outcome == RoundOutcome.BUST.value),
        adaptive_mode=adaptive,
        personas=persona_stats,
    )
