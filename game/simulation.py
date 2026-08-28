"""Non-interactive automated game simulation."""

from __future__ import annotations

import random
import time
from dataclasses import dataclass
from typing import Callable, Optional

from agents.metrics import AgentCallMetrics, display_simulation_metrics
from agents.persona_generator import build_agent_roster
from agents.profiles import PersonaProfile
from agents.service import AgentVoteError
from agents.simulation_config import DEFAULT_SIMULATION_SEED
from game.engine import GameState, process_deliberation_round, process_round
from game.history import GameHistory, build_completed_round_record, resolve_round_outcome
from game.rules import calculate_bust_probability
from game.statistics import FinalOutcome, compute_game_statistics


@dataclass
class SimulationResult:
    rounds_attempted: int
    rounds_completed: int
    final_outcome: FinalOutcome
    final_score: int
    stopped_by_round_limit: bool
    metrics: AgentCallMetrics


def generate_simulated_offer(rng: random.Random) -> int:
    return rng.randint(1, 100)


def run_simulation(
    *,
    agent_count: int = 5,
    seed: int = DEFAULT_SIMULATION_SEED,
    round_limit: int | None = None,
    rng: random.Random | None = None,
    offer_rng: random.Random | None = None,
    mock: bool = False,
    deliberate: bool = False,
    adaptive: bool = False,
    vote_collector: Callable | None = None,
    deliberation_collector: Callable | None = None,
    history_file: str | None = None,
    stats_file: str | None = None,
    save_history_fn=None,
    save_stats_fn=None,
    stdout=print,
    metrics: AgentCallMetrics | None = None,
    profiles: tuple[PersonaProfile, ...] | None = None,
) -> SimulationResult:
    """Run until bust, cash-out, or round limit. Deterministic with seeded RNGs."""
    roster = profiles or build_agent_roster(agent_count, seed=seed)
    rng = rng or random.Random(seed)
    offer_rng = offer_rng or random.Random(seed + 1)
    state = GameState()
    history = GameHistory()
    last_round_outcome: Optional[str] = None
    rounds_attempted = 0
    rounds_completed = 0
    stopped_by_round_limit = False
    call_metrics = metrics or AgentCallMetrics(
        agent_count=len(roster),
        max_concurrency=1,
    )

    assert vote_collector is not None

    while not state.game_over:
        if round_limit is not None and rounds_attempted >= round_limit:
            stopped_by_round_limit = True
            break

        offer = generate_simulated_offer(offer_rng)
        rounds_attempted += 1
        score_before = state.score
        round_before = state.round
        bust_prob = calculate_bust_probability(offer)
        round_started = time.perf_counter()

        try:
            if deliberate:
                assert deliberation_collector is not None
                state, initial_votes, votes, majority = process_deliberation_round(
                    state,
                    offer,
                    rng,
                    history,
                    collect_deliberation_fn=deliberation_collector,
                )
            else:
                state, votes, majority = process_round(
                    state,
                    offer,
                    rng,
                    history,
                    collect_votes_fn=vote_collector,
                )
                initial_votes = None
        except AgentVoteError:
            call_metrics.record_round_latency(time.perf_counter() - round_started)
            break

        call_metrics.record_round_latency(time.perf_counter() - round_started)
        outcome = resolve_round_outcome(
            majority, game_over=state.game_over, score_after=state.score
        )
        last_round_outcome = outcome
        history.add_completed_round(
            build_completed_round_record(
                round_number=round_before,
                offer=offer,
                score_before=score_before,
                score_after=state.score if outcome != "CASH_OUT" else score_before,
                bust_probability=bust_prob,
                votes=votes,
                majority_decision=majority,
                outcome=outcome,
                initial_votes=initial_votes,
                deliberation_mode=deliberate,
            )
        )
        rounds_completed += 1

    if stopped_by_round_limit:
        final_outcome: FinalOutcome = "NONE"
        final_score = state.score
    else:
        final_outcome = _resolve_simulation_outcome(
            game_over=state.game_over,
            last_outcome=last_round_outcome,
        )
        final_score = state.final_score if state.game_over else state.score

    statistics = compute_game_statistics(
        history,
        final_score=final_score,
        final_outcome=final_outcome,
        adaptive=adaptive,
    )

    stdout(
        f"\nSimulation complete — rounds attempted: {rounds_attempted}, "
        f"completed: {rounds_completed}, final score: {final_score}, "
        f"outcome: {final_outcome}"
    )
    if stopped_by_round_limit:
        stdout(f"Stopped after round limit ({round_limit}).")

    display_simulation_metrics(call_metrics)

    if save_history_fn and history_file:
        save_history_fn(history, history_file, statistics=statistics)
        stdout(f"Game history and statistics saved to {history_file}")
    if save_stats_fn and stats_file:
        save_stats_fn(statistics, stats_file)
        stdout(f"Statistics saved to {stats_file}")

    return SimulationResult(
        rounds_attempted=rounds_attempted,
        rounds_completed=rounds_completed,
        final_outcome=final_outcome,
        final_score=final_score,
        stopped_by_round_limit=stopped_by_round_limit,
        metrics=call_metrics,
    )


def _resolve_simulation_outcome(
    *, game_over: bool, last_outcome: Optional[str]
) -> FinalOutcome:
    if not game_over:
        return "NONE"
    if last_outcome == "BUST":
        return "BUST"
    if last_outcome == "CASH_OUT":
        return "CASH_OUT"
    return "NONE"
