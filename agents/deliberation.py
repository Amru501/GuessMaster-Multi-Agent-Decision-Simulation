"""Two-stage deliberation support."""

from __future__ import annotations

from dataclasses import dataclass

from game.engine import PersonaVote


@dataclass(frozen=True)
class DeliberationRoundResult:
    initial_votes: list[PersonaVote]
    final_votes: list[PersonaVote]


def build_deliberation_brief(initial_votes: list[PersonaVote]) -> str:
    """Shared brief of all initial votes for the deliberation stage."""
    lines = []
    for vote in initial_votes:
        pct = int(round(vote.confidence * 100))
        lines.append(
            f"- {vote.name}: {vote.decision} ({pct}% confidence) — {vote.reason}"
        )
    return "\n".join(lines)


def vote_changed(initial: PersonaVote, final: PersonaVote) -> bool:
    return initial.decision != final.decision
