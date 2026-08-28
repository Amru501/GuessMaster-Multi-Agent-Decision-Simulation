"""Static persona relationship graph for deliberation influence."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Literal

from pydantic import BaseModel, Field, model_validator

from agents.profiles import PERSONA_PROFILES

RelationshipType = Literal["trusts", "distrusts", "respects", "dismisses"]

PERSONA_NAMES: frozenset[str] = frozenset(p.name for p in PERSONA_PROFILES)


class PersonaRelationship(BaseModel):
    source: str
    target: str
    relationship_type: RelationshipType
    influence_weight: float = Field(ge=-1.0, le=1.0)
    explanation: str = Field(min_length=1)


class RelationshipGraph(BaseModel):
    relationships: list[PersonaRelationship]

    @model_validator(mode="after")
    def validate_persona_names(self) -> RelationshipGraph:
        for rel in self.relationships:
            if rel.source not in PERSONA_NAMES:
                raise ValueError(f"Unknown source persona: {rel.source!r}")
            if rel.target not in PERSONA_NAMES:
                raise ValueError(f"Unknown target persona: {rel.target!r}")
            if rel.source == rel.target:
                raise ValueError(
                    f"Self-relationship not allowed: {rel.source!r} -> {rel.target!r}"
                )
        return self

    def outgoing(self, source: str) -> list[PersonaRelationship]:
        return [r for r in self.relationships if r.source == source]


DEFAULT_RELATIONSHIP_GRAPH = RelationshipGraph(
    relationships=[
        PersonaRelationship(
            source="Analyst",
            target="Strategist",
            relationship_type="respects",
            influence_weight=0.65,
            explanation="You tend to respect Strategist's long-term score reasoning.",
        ),
        PersonaRelationship(
            source="Analyst",
            target="Gambler",
            relationship_type="dismisses",
            influence_weight=-0.55,
            explanation="You tend to discount Gambler's risk-seeking arguments.",
        ),
        PersonaRelationship(
            source="Gambler",
            target="Impulsive",
            relationship_type="trusts",
            influence_weight=0.50,
            explanation="You tend to trust Impulsive's instinct when the upside feels big.",
        ),
        PersonaRelationship(
            source="Gambler",
            target="Conservative",
            relationship_type="distrusts",
            influence_weight=-0.45,
            explanation="You tend to distrust Conservative's caution as overcautious.",
        ),
        PersonaRelationship(
            source="Conservative",
            target="Analyst",
            relationship_type="trusts",
            influence_weight=0.60,
            explanation="You tend to trust Analyst's quantitative analysis.",
        ),
        PersonaRelationship(
            source="Conservative",
            target="Gambler",
            relationship_type="dismisses",
            influence_weight=-0.70,
            explanation="You tend to discount Gambler's risk-seeking arguments.",
        ),
        PersonaRelationship(
            source="Impulsive",
            target="Gambler",
            relationship_type="respects",
            influence_weight=0.40,
            explanation="You tend to respect Gambler's appetite for bold moves.",
        ),
        PersonaRelationship(
            source="Impulsive",
            target="Analyst",
            relationship_type="dismisses",
            influence_weight=-0.35,
            explanation="You tend to dismiss Analyst's slow number-crunching.",
        ),
        PersonaRelationship(
            source="Strategist",
            target="Analyst",
            relationship_type="respects",
            influence_weight=0.55,
            explanation="You tend to respect Analyst's expected-value reasoning.",
        ),
        PersonaRelationship(
            source="Strategist",
            target="Impulsive",
            relationship_type="distrusts",
            influence_weight=-0.50,
            explanation="You tend to distrust Impulsive's gut-driven swings.",
        ),
    ]
)


def build_relationship_context(source: str, graph: RelationshipGraph) -> str | None:
    """Natural-language outgoing relationship context for one persona's deliberation prompt."""
    outgoing = graph.outgoing(source)
    if not outgoing:
        return None
    lines = [f"- {rel.explanation}" for rel in outgoing]
    return (
        "Your relationship context (outgoing only — how you weigh others' arguments):\n"
        + "\n".join(lines)
    )


def export_relationship_graph(graph: RelationshipGraph, path: str) -> None:
    payload = {"version": 1, "relationships": [r.model_dump() for r in graph.relationships]}
    Path(path).write_text(json.dumps(payload, indent=2), encoding="utf-8")
