"""Tests for V7 persona relationship graph."""

from __future__ import annotations

import json
from pathlib import Path

import pytest
from pydantic import ValidationError

from agents.deliberation_prompts import build_deliberation_prompt
from agents.profiles import get_profile
from agents.relationships import (
    DEFAULT_RELATIONSHIP_GRAPH,
    PersonaRelationship,
    RelationshipGraph,
    build_relationship_context,
    export_relationship_graph,
)
from agents.service import AgentService
from ai.ollama_client import OllamaClient
from game.engine import PersonaVote
from game.history import GameHistory
from main import parse_args, run_game


class TestGraphValidation:
    def test_default_graph_is_valid(self):
        assert len(DEFAULT_RELATIONSHIP_GRAPH.relationships) >= 8
        names = {r.source for r in DEFAULT_RELATIONSHIP_GRAPH.relationships}
        assert names == {"Analyst", "Gambler", "Conservative", "Impulsive", "Strategist"}

    def test_unknown_source_rejected(self):
        with pytest.raises(ValidationError, match="Unknown source persona"):
            RelationshipGraph(
                relationships=[
                    PersonaRelationship(
                        source="Unknown",
                        target="Analyst",
                        relationship_type="trusts",
                        influence_weight=0.5,
                        explanation="test",
                    )
                ]
            )

    def test_unknown_target_rejected(self):
        with pytest.raises(ValidationError, match="Unknown target persona"):
            RelationshipGraph(
                relationships=[
                    PersonaRelationship(
                        source="Analyst",
                        target="Unknown",
                        relationship_type="trusts",
                        influence_weight=0.5,
                        explanation="test",
                    )
                ]
            )

    def test_self_relationship_rejected(self):
        with pytest.raises(ValidationError, match="Self-relationship"):
            RelationshipGraph(
                relationships=[
                    PersonaRelationship(
                        source="Analyst",
                        target="Analyst",
                        relationship_type="trusts",
                        influence_weight=0.5,
                        explanation="test",
                    )
                ]
            )


class TestInvalidWeights:
    @pytest.mark.parametrize("weight", [-1.1, 1.1, -2.0, 2.0])
    def test_weight_out_of_range_rejected(self, weight):
        with pytest.raises(ValidationError):
            PersonaRelationship(
                source="Analyst",
                target="Strategist",
                relationship_type="respects",
                influence_weight=weight,
                explanation="test",
            )

    @pytest.mark.parametrize("weight", [-1.0, 0.0, 1.0, 0.65, -0.55])
    def test_valid_weights_accepted(self, weight):
        rel = PersonaRelationship(
            source="Analyst",
            target="Strategist",
            relationship_type="respects",
            influence_weight=weight,
            explanation="test",
        )
        assert rel.influence_weight == weight


class TestPromptFiltering:
    def _base_prompt_kwargs(self):
        profile = get_profile("Analyst")
        own = PersonaVote("Analyst", "📊", "ADD", 0.8, "logic")
        return dict(
            profile=profile,
            score=10,
            round_num=1,
            offer=50,
            bust_probability=0.46,
            history_summary="No prior completed rounds.",
            deliberation_brief="- Gambler: REJECT (70% confidence) — too risky",
            own_initial=own,
        )

    def test_outgoing_context_only_for_source_persona(self):
        analyst_context = build_relationship_context("Analyst", DEFAULT_RELATIONSHIP_GRAPH)
        assert analyst_context is not None
        assert "Strategist" in analyst_context
        assert "Gambler" in analyst_context
        assert "Conservative" not in analyst_context

        conservative_context = build_relationship_context(
            "Conservative", DEFAULT_RELATIONSHIP_GRAPH
        )
        assert conservative_context is not None
        assert "Analyst" in conservative_context
        assert "Strategist" not in conservative_context

    def test_relationship_context_in_deliberation_prompt_when_provided(self):
        context = build_relationship_context("Analyst", DEFAULT_RELATIONSHIP_GRAPH)
        prompt = build_deliberation_prompt(
            **self._base_prompt_kwargs(),
            relationship_context=context,
        )
        assert "Your relationship context" in prompt
        assert "discount Gambler's risk-seeking arguments" in prompt

    def test_no_relationship_block_when_context_omitted(self):
        prompt = build_deliberation_prompt(**self._base_prompt_kwargs())
        assert "Your relationship context" not in prompt


class TestFeatureFlagBehavior:
    def test_agent_service_omits_relationships_when_disabled(self):
        prompts: list[str] = []

        class FakeClient:
            def chat(self, **kwargs):
                prompts.append(kwargs["messages"][0]["content"])
                payload = json.dumps(
                    {"decision": "ADD", "confidence": 0.5, "reason": "ok"}
                )
                return type(
                    "R",
                    (),
                    {"message": type("M", (), {"content": payload})()},
                )()

            def list(self):
                return type("List", (), {"models": []})()

        service = AgentService(
            OllamaClient(host="http://localhost:11434", client=FakeClient()),
            model="qwen2.5:3b",
            relationships=False,
        )
        service.collect_deliberation_votes(50, 0, 1, GameHistory())
        final_prompts = prompts[5:]
        assert all("Your relationship context" not in p for p in final_prompts)

    def test_agent_service_includes_relationships_when_enabled(self):
        prompts: list[str] = []

        class FakeClient:
            def chat(self, **kwargs):
                prompts.append(kwargs["messages"][0]["content"])
                payload = json.dumps(
                    {"decision": "ADD", "confidence": 0.5, "reason": "ok"}
                )
                return type(
                    "R",
                    (),
                    {"message": type("M", (), {"content": payload})()},
                )()

            def list(self):
                return type("List", (), {"models": []})()

        service = AgentService(
            OllamaClient(host="http://localhost:11434", client=FakeClient()),
            model="qwen2.5:3b",
            relationships=True,
        )
        service.collect_deliberation_votes(50, 0, 1, GameHistory())
        analyst_final = prompts[5]
        conservative_final = prompts[7]
        assert "Your relationship context" in analyst_final
        assert "Strategist" in analyst_final
        assert "Your relationship context" in conservative_final
        assert "You tend to trust Analyst's quantitative analysis." in conservative_final
        assert "You tend to discount Gambler's risk-seeking arguments." in conservative_final

    def test_relationships_without_deliberate_shows_inactive_message(self, capsys):
        inputs = iter(["q"])
        run_game(
            mock=True,
            relationships=True,
            deliberate=False,
            input_fn=lambda: next(inputs),
        )
        combined = capsys.readouterr().out
        assert "relationship influence is inactive" in combined

    def test_verbose_shows_relationship_context_only_with_flags(self, capsys):
        inputs = iter(["50", "q"])
        run_game(
            mock=True,
            deliberate=True,
            relationships=True,
            verbose=True,
            input_fn=lambda: next(inputs),
        )
        combined = capsys.readouterr().out
        assert "Active relationship context" in combined
        assert "discount Gambler's risk-seeking arguments" in combined

    def test_verbose_without_relationships_hides_context(self, capsys):
        inputs = iter(["50", "q"])
        run_game(
            mock=True,
            deliberate=True,
            relationships=False,
            verbose=True,
            input_fn=lambda: next(inputs),
        )
        combined = capsys.readouterr().out
        assert "Active relationship context" not in combined


class TestJsonExport:
    def test_export_graph_writes_valid_json(self, tmp_path: Path):
        path = tmp_path / "graph.json"
        export_relationship_graph(DEFAULT_RELATIONSHIP_GRAPH, str(path))
        data = json.loads(path.read_text(encoding="utf-8"))
        assert data["version"] == 1
        assert len(data["relationships"]) == len(DEFAULT_RELATIONSHIP_GRAPH.relationships)
        first = data["relationships"][0]
        assert "source" in first
        assert "target" in first
        assert "relationship_type" in first
        assert "influence_weight" in first
        assert "explanation" in first

    def test_export_graph_cli_flag(self, tmp_path: Path, capsys):
        path = tmp_path / "exported.json"
        from main import main

        main(["--export-graph", str(path)])
        assert path.exists()
        combined = capsys.readouterr().out
        assert "Relationship graph saved" in combined

    def test_parse_args_export_graph(self):
        args = parse_args(["--export-graph", "out.json"])
        assert args.export_graph == "out.json"
