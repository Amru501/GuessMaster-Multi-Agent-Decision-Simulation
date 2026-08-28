from __future__ import annotations

import random
from dataclasses import dataclass
from typing import Callable, Literal, Optional

from game.history import GameHistory
from game.rules import (
    apply_add_outcome,
    apply_reject_outcome,
    count_majority,
)

Decision = Literal["ADD", "REJECT"]


@dataclass(frozen=True)
class PersonaVote:
    name: str
    emoji: str
    decision: Decision
    confidence: float
    reason: str


@dataclass
class GameState:
    score: int = 0
    round: int = 1
    game_over: bool = False
    final_score: Optional[int] = None


CollectVotesFn = Callable[[int, int, int, GameHistory], list[PersonaVote]]
CollectDeliberationFn = Callable[[int, int, int, GameHistory], "DeliberationRoundResult"]


def _apply_majority_outcome(
    state: GameState,
    offer: int,
    rng: random.Random,
    majority: Decision,
) -> GameState:
    if majority == "REJECT":
        state.game_over = True
        state.final_score = apply_reject_outcome(state.score)
        return state

    busted, new_score = apply_add_outcome(offer, state.score, rng)
    if busted:
        state.game_over = True
        state.score = 0
        state.final_score = 0
    else:
        state.score = new_score
        state.round += 1
    return state


def process_round(
    state: GameState,
    offer: int,
    rng: random.Random,
    history: GameHistory,
    collect_votes_fn: CollectVotesFn,
) -> tuple[GameState, list[PersonaVote], Decision]:
    """Run one round of voting and apply the majority outcome."""
    votes = collect_votes_fn(offer, state.score, state.round, history)
    majority = count_majority(votes)
    state = _apply_majority_outcome(state, offer, rng, majority)
    return state, votes, majority


def process_deliberation_round(
    state: GameState,
    offer: int,
    rng: random.Random,
    history: GameHistory,
    collect_deliberation_fn: CollectDeliberationFn,
) -> tuple[GameState, list[PersonaVote], list[PersonaVote], Decision]:
    """Run deliberation (initial + final votes); majority uses final votes only."""
    from agents.deliberation import DeliberationRoundResult

    result: DeliberationRoundResult = collect_deliberation_fn(
        offer, state.score, state.round, history
    )
    majority = count_majority(result.final_votes)
    state = _apply_majority_outcome(state, offer, rng, majority)
    return state, result.initial_votes, result.final_votes, majority
