"""Multi-Personality Number Game — CLI entry point."""

from __future__ import annotations

import argparse
import json
import random
import sys
import time
from functools import partial
from pathlib import Path
from typing import Callable, Optional

from agents.deliberation import build_deliberation_brief, vote_changed
from agents.metrics import AgentCallMetrics, display_simulation_metrics
from agents.mock_factory import (
    collect_mock_deliberation_for_roster,
    collect_mock_votes_for_roster,
)
from agents.persona_generator import build_agent_roster
from agents.personas import collect_mock_deliberation_votes, collect_mock_votes
from agents.profiles import PERSONA_PROFILES, PersonaProfile
from agents.relationships import (
    DEFAULT_RELATIONSHIP_GRAPH,
    RelationshipGraph,
    build_relationship_context,
    export_relationship_graph,
)
from agents.service import AgentService, AgentVoteError
from agents.simulation_config import (
    DEFAULT_AGENT_COUNT,
    DEFAULT_MAX_CONCURRENCY,
    DEFAULT_SIMULATION_SEED,
    SimulationConfigError,
    validate_agent_count,
    validate_max_concurrency,
    validate_round_limit,
)
from ai.config import OllamaConfig, OllamaConfigError, load_ollama_config
from ai.ollama_client import OllamaClient, OllamaConnectionError, OllamaModelError, OllamaResponseError
from game.engine import (
    GameState,
    PersonaVote,
    process_deliberation_round,
    process_round as _process_round,
)
from game.history import GameHistory, build_completed_round_record, resolve_round_outcome
from game.rules import calculate_bust_probability, validate_offer
from game.simulation import run_simulation
from game.statistics import FinalOutcome, GameStatistics, compute_game_statistics

# Re-exports for tests and backward compatibility
from game.rules import (  # noqa: F401
    apply_add_outcome,
    apply_reject_outcome,
    calculate_bust_probability,
    count_majority,
)

collect_votes = collect_mock_votes


def process_round(
    state: GameState,
    offer: int,
    rng: random.Random,
    history: GameHistory,
    collect_votes_fn: Callable[[int, int, int, GameHistory], list[PersonaVote]] | None = None,
):
    collector = collect_votes_fn or collect_mock_votes
    return _process_round(state, offer, rng, history, collector)


def prepare_ollama_service(
    config: OllamaConfig,
    *,
    adaptive: bool = False,
    relationships: bool = False,
    profiles: tuple[PersonaProfile, ...] | None = None,
    max_concurrency: int = DEFAULT_MAX_CONCURRENCY,
    metrics: AgentCallMetrics | None = None,
) -> AgentService:
    client = OllamaClient(
        host=config.host,
        timeout=config.timeout_seconds,
        keep_alive=config.keep_alive,
    )
    client.verify_connection()
    client.verify_model(config.model)
    roster = profiles or PERSONA_PROFILES
    service = AgentService(
        client,
        model=config.model,
        adaptive=adaptive,
        relationships=relationships,
        profiles=roster,
        max_concurrency=max_concurrency,
        metrics=metrics,
    )

    print("Warming up local model…")
    try:
        service.warmup()
    except OllamaResponseError as exc:
        print(f"Error: Warm-up failed: {exc}", file=sys.stderr)
        sys.exit(1)

    print("Model ready.")
    return service


def format_vote(vote: PersonaVote) -> str:
    pct = int(round(vote.confidence * 100))
    return f"  {vote.emoji} {vote.name}: {vote.decision} ({pct}% confidence) — {vote.reason}"


def display_round_header(state: GameState) -> None:
    print(f"\n--- Round {state.round} | Score: {state.score} ---")


def display_votes(votes: list[PersonaVote], *, title: str = "Persona votes") -> None:
    print(f"\n{title}:")
    for vote in votes:
        print(format_vote(vote))


def display_deliberation_panels(
    initial_votes: list[PersonaVote],
    final_votes: list[PersonaVote],
    *,
    verbose: bool = False,
    relationships: bool = False,
    graph: RelationshipGraph | None = None,
) -> None:
    display_votes(initial_votes, title="Initial votes (independent)")
    brief = build_deliberation_brief(initial_votes)
    print("\nDeliberation brief:")
    for line in brief.splitlines():
        print(f"  {line}")
    if verbose and relationships and graph is not None:
        print("\nActive relationship context (outgoing per persona):")
        for profile in PERSONA_PROFILES:
            context = build_relationship_context(profile.name, graph)
            if context:
                print(f"\n  {profile.emoji} {profile.name}:")
                for line in context.splitlines():
                    print(f"    {line}")
    display_votes(final_votes, title="Final votes (after deliberation)")
    print("\nVote changes:")
    initial_by_name = {v.name: v for v in initial_votes}
    for final in final_votes:
        initial = initial_by_name[final.name]
        if vote_changed(initial, final):
            print(f"  {final.emoji} {final.name}: {initial.decision} → {final.decision}")
        else:
            print(f"  {final.emoji} {final.name}: unchanged ({final.decision})")


def display_majority(majority: str) -> None:
    print(f"\nMAJORITY: {majority}")


def display_add_safe(state: GameState) -> None:
    print(f"Safe! Score updated to {state.score}.")


def display_bust() -> None:
    print("BUST — GAME OVER")
    print("Final score: 0")


def display_cash_out(score: int) -> None:
    print("GAME OVER")
    print(f"Final score: {score}")


def display_round_cancelled(
    persona_name: str, technical_error: str, state: GameState, *, stage: str = "vote"
) -> None:
    print(f"\nAgent failure: {persona_name} ({stage} stage)")
    print(f"Technical error: {technical_error}")
    print(f"Round {state.round} cancelled — score unchanged ({state.score}).")
    print("Enter a new offer or type q to quit.")


def display_game_history(history: GameHistory) -> None:
    print("\n--- Completed round history ---")
    if not history.rounds:
        print("  (none yet)")
        return
    for record in history.rounds:
        print(
            f"  Round {record.round_number}: offer {record.offer}, "
            f"score {record.score_before} → {record.score_after}, "
            f"majority {record.majority_decision}, outcome {record.outcome}"
        )


def display_statistics_report(stats: GameStatistics) -> None:
    print("\n=== Post-Game Statistics ===")
    print(
        "Behavioral patterns only — these metrics describe how each persona voted, "
        "not whether any vote was objectively correct."
    )
    print(f"\nGame summary:")
    print(f"  Completed rounds: {stats.completed_rounds}")
    print(f"  Final outcome:    {stats.final_outcome}")
    print(f"  Final score:      {stats.final_score}")
    print(f"  Average offer:    {stats.average_offer}")
    print(f"  ADD majorities:   {stats.add_majority_rounds}")
    print(f"  REJECT majorities:{stats.reject_majority_rounds}")
    print(f"  Busts:            {stats.bust_count}")

    if not stats.personas:
        print("\n  No persona voting data recorded.")
        return

    if stats.adaptive_mode:
        print("\n  (Adaptive mode — effective risk tolerance adjusted from this game's outcomes)")

    print("\nPersona voting behavior:")
    for p in stats.personas:
        if p.rounds_voted == 0:
            print(f"\n  {p.emoji} {p.name}: no votes recorded")
            if stats.adaptive_mode and p.base_risk_tolerance is not None:
                print(f"    Base risk tolerance:       {p.base_risk_tolerance:.2f}")
                print(f"    Risk adjustment:           {p.risk_tolerance_adjustment:+.2f}")
                print(f"    Effective risk tolerance:  {p.effective_risk_tolerance:.2f}")
            continue
        print(f"\n  {p.emoji} {p.name}")
        print(f"    Rounds voted:              {p.rounds_voted}")
        print(f"    ADD / REJECT:              {p.add_count} ({p.add_percentage}%) / {p.reject_count} ({p.reject_percentage}%)")
        print(f"    Average confidence:        {p.average_confidence}")
        print(f"    Majority alignment:        {p.majority_alignment_rate}%")
        print(f"    ADD before SAFE_ADD:       {p.add_votes_before_safe_add}")
        print(f"    ADD before BUST:           {p.add_votes_before_bust}")
        if stats.adaptive_mode and p.base_risk_tolerance is not None:
            print(f"    Base risk tolerance:       {p.base_risk_tolerance:.2f}")
            print(f"    Risk adjustment:           {p.risk_tolerance_adjustment:+.2f}")
            print(f"    Effective risk tolerance:  {p.effective_risk_tolerance:.2f}")


def save_history_file(
    history: GameHistory,
    path: str,
    statistics: Optional[GameStatistics] = None,
) -> None:
    payload = history.model_dump()
    if statistics is not None:
        payload["statistics"] = statistics.model_dump()
    Path(path).write_text(json.dumps(payload, indent=2), encoding="utf-8")


def save_stats_file(statistics: GameStatistics, path: str) -> None:
    Path(path).write_text(
        json.dumps(statistics.model_dump(), indent=2),
        encoding="utf-8",
    )


def resolve_final_outcome(*, game_over: bool, last_outcome: Optional[str], quit_early: bool) -> FinalOutcome:
    if quit_early:
        return "QUIT"
    if not game_over:
        return "NONE"
    if last_outcome == "BUST":
        return "BUST"
    if last_outcome == "CASH_OUT":
        return "CASH_OUT"
    return "NONE"


def prompt_offer() -> str:
    return input("Enter offer (1–100, or q to quit): ")


def validate_scaling_options(
    *,
    agent_count: int,
    max_concurrency: int,
    round_limit: int | None,
) -> None:
    validate_agent_count(agent_count)
    validate_max_concurrency(max_concurrency, agent_count)
    validate_round_limit(round_limit)


def build_vote_collectors(
    roster: tuple[PersonaProfile, ...],
    *,
    mock: bool,
    agent_service: AgentService | None,
) -> tuple[Callable, Callable | None]:
    if mock:
        vote_collector = partial(collect_mock_votes_for_roster, roster)
        deliberation_collector = partial(collect_mock_deliberation_for_roster, roster)
        return vote_collector, deliberation_collector
    assert agent_service is not None
    return agent_service.collect_votes, agent_service.collect_deliberation_votes


def run_game(
    *,
    mock: bool = False,
    rng: Optional[random.Random] = None,
    input_fn=prompt_offer,
    agent_service: Optional[AgentService] = None,
    stdout=print,
    show_history: bool = False,
    history_file: Optional[str] = None,
    stats_file: Optional[str] = None,
    adaptive: bool = False,
    deliberate: bool = False,
    relationships: bool = False,
    verbose: bool = False,
    agent_count: int = DEFAULT_AGENT_COUNT,
    seed: int | None = None,
    max_concurrency: int = DEFAULT_MAX_CONCURRENCY,
) -> None:
    validate_scaling_options(
        agent_count=agent_count,
        max_concurrency=max_concurrency,
        round_limit=None,
    )
    roster = build_agent_roster(agent_count, seed=seed)
    rng = rng or random.Random()
    state = GameState()
    history = GameHistory()
    last_round_outcome: Optional[str] = None
    quit_early = False
    relationships_active = deliberate and relationships
    relationship_graph = DEFAULT_RELATIONSHIP_GRAPH if relationships_active else None
    call_metrics = AgentCallMetrics(
        agent_count=len(roster),
        max_concurrency=max_concurrency,
    )

    if mock:
        mode_label = "mock personas (V0)"
    else:
        if agent_service is None:
            try:
                config = load_ollama_config()
                agent_service = prepare_ollama_service(
                    config,
                    adaptive=adaptive,
                    relationships=relationships_active,
                    profiles=roster,
                    max_concurrency=max_concurrency,
                    metrics=call_metrics,
                )
            except OllamaConfigError as exc:
                print(f"Error: {exc}", file=sys.stderr)
                sys.exit(1)
            except OllamaConnectionError as exc:
                print(f"Error: {exc}", file=sys.stderr)
                sys.exit(1)
            except OllamaModelError as exc:
                print(f"Error: {exc}", file=sys.stderr)
                sys.exit(1)
        mode_label = f"Ollama ({agent_service.model})"

    vote_collector, deliberation_collector = build_vote_collectors(
        roster, mock=mock, agent_service=agent_service
    )

    if adaptive:
        mode_label += ", adaptive"
    if deliberate:
        mode_label += ", deliberate"
    if relationships:
        mode_label += ", relationships" if relationships_active else ", relationships (inactive)"
    if agent_count != DEFAULT_AGENT_COUNT:
        mode_label += f", {agent_count} agents"
    if max_concurrency > 1:
        mode_label += f", concurrency {max_concurrency}"

    stdout("Multi-Personality Number Game")
    stdout(f"Mode: {mode_label}")
    if adaptive:
        stdout("Adaptive risk tolerance enabled — personas adjust from completed outcomes.")
    if deliberate:
        stdout(
            "Deliberation enabled — personas vote twice; final votes determine the majority."
        )
    if relationships and not deliberate:
        stdout(
            "Note: --relationships requires --deliberate; relationship influence is inactive."
        )
    if relationships_active:
        stdout(
            "Relationship graph active — final deliberation prompts include outgoing influence context."
        )
    stdout(
        f"{len(roster)} personas vote on each offer. Majority ADD risks a bust roll."
    )

    def finish_game() -> None:
        final_outcome = resolve_final_outcome(
            game_over=state.game_over,
            last_outcome=last_round_outcome,
            quit_early=quit_early,
        )
        final_score = state.final_score if state.game_over else state.score
        statistics = compute_game_statistics(
            history,
            final_score=final_score,
            final_outcome=final_outcome,
            adaptive=adaptive,
        )
        display_statistics_report(statistics)
        if history_file:
            save_history_file(history, history_file, statistics=statistics)
            stdout(f"Game history and statistics saved to {history_file}")
        if stats_file:
            save_stats_file(statistics, stats_file)
            stdout(f"Statistics saved to {stats_file}")
        if call_metrics.total_calls > 0 and agent_count > DEFAULT_AGENT_COUNT:
            display_simulation_metrics(call_metrics)

    while not state.game_over:
        if show_history:
            display_game_history(history)

        display_round_header(state)
        raw = input_fn()

        ok, offer, err = validate_offer(raw)
        if err == "quit":
            stdout("Thanks for playing!")
            quit_early = True
            finish_game()
            return
        if not ok:
            stdout(f"Invalid input: {err}")
            continue

        assert offer is not None
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
                    state, offer, rng, history, collect_votes_fn=vote_collector
                )
                initial_votes = None
        except AgentVoteError as exc:
            assert state.score == score_before
            assert state.round == round_before
            assert not state.game_over
            display_round_cancelled(
                exc.persona_name, exc.message, state, stage=exc.stage
            )
            continue

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

        if deliberate and initial_votes is not None:
            display_deliberation_panels(
                initial_votes,
                votes,
                verbose=verbose,
                relationships=relationships_active,
                graph=relationship_graph,
            )
        else:
            display_votes(votes)
        display_majority(majority)

        if majority == "REJECT":
            display_cash_out(state.final_score or 0)
        elif state.game_over:
            display_bust()
        else:
            display_add_safe(state)

    finish_game()


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Multi-Personality Number Game — five personas vote on each offer."
    )
    parser.add_argument(
        "--mock",
        action="store_true",
        help="Use deterministic V0 mock personas instead of Ollama.",
    )
    parser.add_argument(
        "--show-history",
        action="store_true",
        help="Print completed round history during the game.",
    )
    parser.add_argument(
        "--history-file",
        metavar="PATH",
        help="Save completed game history and statistics as JSON when the game ends.",
    )
    parser.add_argument(
        "--stats-file",
        metavar="PATH",
        help="Save post-game statistics as JSON when the game ends.",
    )
    parser.add_argument(
        "--adaptive",
        action="store_true",
        help="Enable bounded risk-tolerance adaptation from completed outcomes.",
    )
    parser.add_argument(
        "--deliberate",
        action="store_true",
        help="Enable two-stage deliberation (initial + final votes).",
    )
    parser.add_argument(
        "--relationships",
        action="store_true",
        help="Include persona relationship context in deliberation prompts (requires --deliberate).",
    )
    parser.add_argument(
        "--verbose",
        action="store_true",
        help="Show relationship context during deliberation rounds.",
    )
    parser.add_argument(
        "--export-graph",
        metavar="PATH",
        help="Export the static persona relationship graph as JSON and exit.",
    )
    parser.add_argument(
        "--agent-count",
        type=int,
        default=DEFAULT_AGENT_COUNT,
        metavar="N",
        help=f"Total personas voting (odd, {DEFAULT_AGENT_COUNT}–51, default {DEFAULT_AGENT_COUNT}).",
    )
    parser.add_argument(
        "--seed",
        type=int,
        default=None,
        metavar="N",
        help="Seed for generated personas and simulation offers (reproducible runs).",
    )
    parser.add_argument(
        "--round-limit",
        type=int,
        default=None,
        metavar="N",
        help="Maximum rounds for --simulate mode.",
    )
    parser.add_argument(
        "--simulate",
        action="store_true",
        help="Non-interactive simulation with seeded offers until bust, cash-out, or round limit.",
    )
    parser.add_argument(
        "--max-concurrency",
        type=int,
        default=DEFAULT_MAX_CONCURRENCY,
        metavar="N",
        help="Maximum concurrent Ollama persona calls (default 1).",
    )
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> None:
    args = parse_args(argv)
    if args.export_graph:
        export_relationship_graph(DEFAULT_RELATIONSHIP_GRAPH, args.export_graph)
        print(f"Relationship graph saved to {args.export_graph}")
        return

    seed = args.seed if args.seed is not None else DEFAULT_SIMULATION_SEED
    try:
        validate_scaling_options(
            agent_count=args.agent_count,
            max_concurrency=args.max_concurrency,
            round_limit=args.round_limit,
        )
    except SimulationConfigError as exc:
        print(f"Error: {exc}", file=sys.stderr)
        sys.exit(1)

    if args.simulate:
        roster = build_agent_roster(args.agent_count, seed=seed)
        call_metrics = AgentCallMetrics(
            agent_count=len(roster),
            max_concurrency=args.max_concurrency,
        )
        agent_service = None
        if not args.mock:
            try:
                config = load_ollama_config()
                agent_service = prepare_ollama_service(
                    config,
                    adaptive=args.adaptive,
                    relationships=args.deliberate and args.relationships,
                    profiles=roster,
                    max_concurrency=args.max_concurrency,
                    metrics=call_metrics,
                )
            except OllamaConfigError as exc:
                print(f"Error: {exc}", file=sys.stderr)
                sys.exit(1)
            except OllamaConnectionError as exc:
                print(f"Error: {exc}", file=sys.stderr)
                sys.exit(1)
            except OllamaModelError as exc:
                print(f"Error: {exc}", file=sys.stderr)
                sys.exit(1)

        vote_collector, deliberation_collector = build_vote_collectors(
            roster, mock=args.mock, agent_service=agent_service
        )
        history_file = args.history_file or "simulation-history.json"
        stats_file = args.stats_file
        run_simulation(
            agent_count=args.agent_count,
            seed=seed,
            round_limit=args.round_limit,
            mock=args.mock,
            deliberate=args.deliberate,
            adaptive=args.adaptive,
            vote_collector=vote_collector,
            deliberation_collector=deliberation_collector,
            history_file=history_file,
            stats_file=stats_file,
            save_history_fn=save_history_file,
            save_stats_fn=save_stats_file,
            metrics=call_metrics,
            profiles=roster,
        )
        return

    run_game(
        mock=args.mock,
        show_history=args.show_history,
        history_file=args.history_file,
        stats_file=args.stats_file,
        adaptive=args.adaptive,
        deliberate=args.deliberate,
        relationships=args.relationships,
        verbose=args.verbose,
        agent_count=args.agent_count,
        seed=seed if args.agent_count > DEFAULT_AGENT_COUNT else None,
        max_concurrency=args.max_concurrency,
    )


if __name__ == "__main__":
    main()
