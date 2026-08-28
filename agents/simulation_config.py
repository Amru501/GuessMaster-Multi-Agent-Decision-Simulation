"""Validation for scaled simulation and agent-count configuration."""

from __future__ import annotations

MIN_AGENT_COUNT = 5
MAX_AGENT_COUNT = 51
DEFAULT_AGENT_COUNT = 5
DEFAULT_MAX_CONCURRENCY = 1
DEFAULT_SIMULATION_SEED = 42


class SimulationConfigError(Exception):
    """Invalid simulation or scaling configuration."""


def validate_agent_count(agent_count: int) -> None:
    if agent_count < MIN_AGENT_COUNT:
        raise SimulationConfigError(
            f"--agent-count must be at least {MIN_AGENT_COUNT} (got {agent_count})."
        )
    if agent_count > MAX_AGENT_COUNT:
        raise SimulationConfigError(
            f"--agent-count cannot exceed {MAX_AGENT_COUNT} (got {agent_count}). "
            "Local hardware and model speed determine practical limits."
        )
    if agent_count % 2 == 0:
        raise SimulationConfigError(
            f"--agent-count must be odd to avoid majority ties (got {agent_count}). "
            "Try an odd value such as "
            f"{agent_count - 1 if agent_count > MIN_AGENT_COUNT else agent_count + 1} "
            f"or {agent_count + 1}."
        )


def validate_max_concurrency(max_concurrency: int, agent_count: int) -> None:
    if max_concurrency < 1:
        raise SimulationConfigError(
            f"--max-concurrency must be at least 1 (got {max_concurrency})."
        )
    if max_concurrency > agent_count:
        raise SimulationConfigError(
            f"--max-concurrency ({max_concurrency}) cannot exceed --agent-count "
            f"({agent_count})."
        )


def validate_round_limit(round_limit: int | None) -> None:
    if round_limit is None:
        return
    if round_limit < 1:
        raise SimulationConfigError(
            f"--round-limit must be at least 1 (got {round_limit})."
        )
