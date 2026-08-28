"""Deterministic game rules — no LLM or I/O."""

from __future__ import annotations

import random
from typing import TYPE_CHECKING, Literal, Optional

if TYPE_CHECKING:
    from game.engine import PersonaVote

Decision = Literal["ADD", "REJECT"]


def calculate_bust_probability(offer: int) -> float:
    """Return bust chance when ADD wins. Softer curve than early versions."""
    return min(0.70, 0.02 + offer / 240)


def validate_offer(raw: str) -> tuple[bool, Optional[int], Optional[str]]:
    """Return (ok, offer, error_message). Accepts 'q'/'quit' as exit signals."""
    stripped = raw.strip()
    if stripped.lower() in ("q", "quit"):
        return False, None, "quit"

    if not stripped:
        return False, None, "Offer cannot be empty."

    try:
        value = int(stripped)
    except ValueError:
        return False, None, f"'{stripped}' is not a valid integer."

    if value < 1 or value > 100:
        return False, None, "Offer must be an integer from 1 to 100."

    return True, value, None


def count_majority(votes: list[PersonaVote]) -> Decision:
    add_count = sum(1 for vote in votes if vote.decision == "ADD")
    reject_count = len(votes) - add_count
    # With an odd number of voters, ties cannot occur.
    if add_count > reject_count:
        return "ADD"
    return "REJECT"


def apply_add_outcome(
    offer: int, score: int, rng: random.Random
) -> tuple[bool, int]:
    """Roll bust. Returns (busted, new_score). On bust, new_score is 0."""
    bust_prob = calculate_bust_probability(offer)
    if rng.random() < bust_prob:
        return True, 0
    return False, score + offer


def apply_reject_outcome(score: int) -> int:
    return score
