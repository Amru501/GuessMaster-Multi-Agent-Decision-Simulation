"""Round history and bounded memory models."""

from __future__ import annotations

import json
from enum import Enum
from typing import Literal

from pydantic import BaseModel, Field

Decision = Literal["ADD", "REJECT"]
StoredOutcome = Literal["SAFE_ADD", "BUST", "CASH_OUT"]


class RoundOutcome(str, Enum):
    SAFE_ADD = "SAFE_ADD"
    BUST = "BUST"
    CASH_OUT = "CASH_OUT"
    CANCELLED = "CANCELLED"


class VoteRecord(BaseModel):
    name: str
    emoji: str
    decision: Decision
    confidence: float
    reason: str


class CompletedRoundRecord(BaseModel):
    round_number: int
    offer: int
    score_before: int
    score_after: int
    bust_probability: float
    votes: list[VoteRecord]
    majority_decision: Decision
    outcome: StoredOutcome
    initial_votes: list[VoteRecord] | None = None
    deliberation_mode: bool = False


class GameHistory(BaseModel):
    rounds: list[CompletedRoundRecord] = Field(default_factory=list)

    def add_completed_round(self, record: CompletedRoundRecord) -> None:
        self.rounds.append(record)

    def successful_rounds(self) -> list[CompletedRoundRecord]:
        return [r for r in self.rounds if r.outcome == RoundOutcome.SAFE_ADD.value]

    def bounded_summary(self, limit: int = 3) -> str:
        """Compact summary of the latest successful (SAFE_ADD) rounds for prompts."""
        recent = self.successful_rounds()[-limit:]
        if not recent:
            return "No prior completed rounds."
        lines = [
            (
                f"Round {r.round_number}: offer {r.offer}, majority {r.majority_decision}, "
                f"outcome {r.outcome}, score after {r.score_after}"
            )
            for r in recent
        ]
        return "\n".join(lines)

    def to_json(self) -> str:
        return json.dumps(self.model_dump(), indent=2)

    @classmethod
    def from_json(cls, raw: str) -> GameHistory:
        return cls.model_validate_json(raw)


def votes_to_records(votes) -> list[VoteRecord]:
    return [
        VoteRecord(
            name=v.name,
            emoji=v.emoji,
            decision=v.decision,
            confidence=v.confidence,
            reason=v.reason,
        )
        for v in votes
    ]


def resolve_round_outcome(
    majority: Decision, *, game_over: bool, score_after: int
) -> StoredOutcome:
    if majority == "REJECT":
        return RoundOutcome.CASH_OUT.value
    if game_over and score_after == 0:
        return RoundOutcome.BUST.value
    return RoundOutcome.SAFE_ADD.value


def build_completed_round_record(
    *,
    round_number: int,
    offer: int,
    score_before: int,
    score_after: int,
    bust_probability: float,
    votes,
    majority_decision: Decision,
    outcome: StoredOutcome,
    initial_votes=None,
    deliberation_mode: bool = False,
) -> CompletedRoundRecord:
    return CompletedRoundRecord(
        round_number=round_number,
        offer=offer,
        score_before=score_before,
        score_after=score_after,
        bust_probability=bust_probability,
        votes=votes_to_records(votes),
        majority_decision=majority_decision,
        outcome=outcome,
        initial_votes=votes_to_records(initial_votes) if initial_votes else None,
        deliberation_mode=deliberation_mode,
    )
