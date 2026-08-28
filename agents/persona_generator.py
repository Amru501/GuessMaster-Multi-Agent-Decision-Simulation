"""Generate additional personas from controlled trait combinations."""

from __future__ import annotations

import random

from agents.profiles import PERSONA_PROFILES, PersonaProfile
from agents.simulation_config import DEFAULT_SIMULATION_SEED, validate_agent_count

OBJECTIVES: tuple[str, ...] = (
    "Maximize long-run score through disciplined risk management",
    "Capture upside quickly even when variance is high",
    "Preserve accumulated score unless upside is clearly favorable",
    "Balance steady growth with occasional calculated risks",
    "Exit safely when marginal gains no longer justify bust exposure",
    "Seek asymmetric payoffs where reward outweighs modeled bust risk",
    "Protect capital first, then pursue incremental score gains",
    "Exploit favorable offers before variance erodes opportunity",
)

DECISION_PHILOSOPHIES: tuple[str, ...] = (
    "Favor ADD when expected value clearly exceeds bust risk; otherwise REJECT.",
    "Default to REJECT unless bust probability is comfortably low.",
    "Weigh offer size against current score and bust probability together.",
    "Accept moderate bust risk when the offer materially advances the score.",
    "Reject offers that fail a simple risk-adjusted value threshold.",
    "Prefer action when upside dominates; pause when downside dominates.",
    "Use risk tolerance as a guide, not a rigid formula.",
    "Treat each round as independent but respect cumulative score context.",
)

COMMUNICATION_STYLES: tuple[str, ...] = (
    "Direct and concise",
    "Cautious and measured",
    "Analytical and evidence-focused",
    "Bold and optimistic",
    "Pragmatic and tradeoff-oriented",
    "Calm and risk-aware",
    "Energetic and decisive",
    "Minimalist and fact-first",
)

ROLE_IDENTITIES: tuple[str, ...] = (
    "Generated simulation agent with a distinct risk posture",
    "Synthetic voter tuned for scaled multi-agent experiments",
    "Configurable persona exploring a fixed trait combination",
    "Experimental agent derived from seeded trait sampling",
)

BEHAVIORAL_TENDENCIES: tuple[tuple[str, ...], ...] = (
    ("References bust probability in reasons", "States confidence explicitly"),
    ("Highlights offer value relative to score", "Uses short decisive phrasing"),
    ("Compares upside and downside before voting", "Avoids vague hedging"),
    ("Cites risk tolerance when explaining votes", "Keeps reasons under two sentences"),
)

ANTI_PATTERNS: tuple[tuple[str, ...], ...] = (
    ("Ignoring bust probability entirely", "Claiming to know the majority outcome"),
    ("Blindly copying other personas", "Inventing vote counts or game results"),
    ("Overly long analysis chains", "Emotional language without substance"),
    ("Refusing to pick ADD or REJECT", "Changing rules or score outside the vote"),
)

GENERATED_EMOJIS: tuple[str, ...] = (
    "🤖",
    "🧩",
    "🔬",
    "🎯",
    "📈",
    "📉",
    "🧠",
    "🔍",
    "⚙️",
    "🧪",
    "📡",
    "🛰️",
    "💡",
    "🧭",
    "🔖",
)


def generate_persona(agent_number: int, rng: random.Random) -> PersonaProfile:
    """Create one generated profile from seeded trait combinations."""
    risk_tolerance = round(rng.uniform(0.12, 0.88), 2)
    objective = rng.choice(OBJECTIVES)
    decision_philosophy = rng.choice(DECISION_PHILOSOPHIES)
    communication_style = rng.choice(COMMUNICATION_STYLES)
    role_identity = rng.choice(ROLE_IDENTITIES)
    tendencies = list(rng.choice(BEHAVIORAL_TENDENCIES))
    anti_patterns = list(rng.choice(ANTI_PATTERNS))
    emoji = GENERATED_EMOJIS[(agent_number - 6) % len(GENERATED_EMOJIS)]
    name = f"Agent-{agent_number:02d}"

    return PersonaProfile(
        name=name,
        emoji=emoji,
        role_identity=role_identity,
        objective=objective,
        risk_tolerance=risk_tolerance,
        decision_philosophy=decision_philosophy,
        behavioral_tendencies=tendencies,
        communication_style=communication_style,
        anti_patterns=anti_patterns,
    )


def build_agent_roster(agent_count: int, seed: int | None = None) -> tuple[PersonaProfile, ...]:
    """Return the core five personas plus generated ones when agent_count > 5."""
    validate_agent_count(agent_count)
    if agent_count == len(PERSONA_PROFILES):
        return PERSONA_PROFILES

    rng = random.Random(seed if seed is not None else DEFAULT_SIMULATION_SEED)
    roster = list(PERSONA_PROFILES)
    for agent_number in range(len(PERSONA_PROFILES) + 1, agent_count + 1):
        roster.append(generate_persona(agent_number, rng))
    return tuple(roster)
