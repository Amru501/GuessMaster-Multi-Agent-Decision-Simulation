"""Tests for V8 scaled simulation and persona generation."""

from __future__ import annotations

import random
from pathlib import Path

import pytest

from agents.metrics import AgentCallMetrics
from agents.persona_generator import build_agent_roster, generate_persona
from agents.profiles import PERSONA_PROFILES
from agents.service import AgentService
from agents.simulation_config import (
    MAX_AGENT_COUNT,
    MIN_AGENT_COUNT,
    SimulationConfigError,
    validate_agent_count,
    validate_max_concurrency,
)
from ai.ollama_client import OllamaClient
from game.engine import GameState, PersonaVote, process_round
from game.history import GameHistory
from game.rules import count_majority
from game.simulation import generate_simulated_offer, run_simulation
from main import build_vote_collectors, validate_scaling_options


class TestGeneratedPersonaValidity:
    def test_core_five_unchanged_at_default_count(self):
        roster = build_agent_roster(5, seed=99)
        assert roster == PERSONA_PROFILES

    def test_generated_profiles_are_valid(self):
        rng = random.Random(7)
        profile = generate_persona(6, rng)
        assert profile.name == "Agent-06"
        assert 0.0 <= profile.risk_tolerance <= 1.0
        assert profile.objective
        assert profile.decision_philosophy
        assert profile.communication_style
        assert len(profile.behavioral_tendencies) >= 1
        assert len(profile.anti_patterns) >= 1

    def test_roster_includes_core_plus_generated(self):
        roster = build_agent_roster(7, seed=11)
        assert len(roster) == 7
        assert [p.name for p in roster[:5]] == [p.name for p in PERSONA_PROFILES]
        assert roster[5].name == "Agent-06"
        assert roster[6].name == "Agent-07"


class TestReproducibleSeeds:
    def test_same_seed_produces_same_generated_roster(self):
        first = build_agent_roster(9, seed=123)
        second = build_agent_roster(9, seed=123)
        assert first == second

    def test_different_seeds_produce_different_rosters(self):
        first = build_agent_roster(9, seed=1)
        second = build_agent_roster(9, seed=2)
        assert first[:5] == second[:5]
        assert first[5:] != second[5:]

    def test_simulated_offers_are_reproducible(self):
        rng_a = random.Random(42)
        rng_b = random.Random(42)
        offers_a = [generate_simulated_offer(rng_a) for _ in range(10)]
        offers_b = [generate_simulated_offer(rng_b) for _ in range(10)]
        assert offers_a == offers_b


class TestAgentCountValidation:
    @pytest.mark.parametrize("count", [4, 6, 10, 52])
    def test_even_or_out_of_range_rejected(self, count):
        with pytest.raises(SimulationConfigError):
            validate_agent_count(count)

    @pytest.mark.parametrize("count", [5, 7, 21, 51])
    def test_valid_odd_counts_accepted(self, count):
        validate_agent_count(count)

    def test_validate_scaling_options_even_count_message(self):
        with pytest.raises(SimulationConfigError, match="must be odd"):
            validate_scaling_options(agent_count=6, max_concurrency=1, round_limit=None)

    def test_minimum_and_maximum_bounds(self):
        validate_agent_count(MIN_AGENT_COUNT)
        validate_agent_count(MAX_AGENT_COUNT)
        with pytest.raises(SimulationConfigError, match="at least"):
            validate_agent_count(MIN_AGENT_COUNT - 1)
        with pytest.raises(SimulationConfigError, match="cannot exceed"):
            validate_agent_count(MAX_AGENT_COUNT + 1)


class TestConcurrencyConfiguration:
    def test_max_concurrency_must_be_positive(self):
        with pytest.raises(SimulationConfigError, match="at least 1"):
            validate_max_concurrency(0, 5)

    def test_max_concurrency_cannot_exceed_agent_count(self):
        with pytest.raises(SimulationConfigError, match="cannot exceed"):
            validate_max_concurrency(6, 5)

    def test_agent_service_respects_concurrency_setting(self):
        import time

        class FakeClient:
            active = 0
            peak = 0

            def chat(self, **kwargs):
                FakeClient.active += 1
                FakeClient.peak = max(FakeClient.peak, FakeClient.active)
                time.sleep(0.02)
                FakeClient.active -= 1
                payload = '{"decision":"ADD","confidence":0.5,"reason":"ok"}'
                return type(
                    "R",
                    (),
                    {"message": type("M", (), {"content": payload})()},
                )()

            def list(self):
                return type("List", (), {"models": []})()

        FakeClient.peak = 0
        roster = build_agent_roster(7, seed=1)
        service = AgentService(
            OllamaClient(host="http://localhost:11434", client=FakeClient()),
            model="qwen2.5:3b",
            profiles=roster,
            max_concurrency=3,
        )
        service.collect_votes(50, 0, 1, GameHistory())
        assert FakeClient.peak <= 3
        assert FakeClient.peak > 1


class TestSimulationStopConditions:
    def _run_mock_sim(
        self,
        *,
        seed: int,
        round_limit: int | None,
        bust_rng: random.Random,
    ):
        roster = build_agent_roster(5, seed=seed)
        vote_collector, _ = build_vote_collectors(
            roster, mock=True, agent_service=None
        )
        return run_simulation(
            agent_count=5,
            seed=seed,
            round_limit=round_limit,
            rng=bust_rng,
            offer_rng=random.Random(seed + 1),
            mock=True,
            vote_collector=vote_collector,
            stdout=lambda *_args, **_kwargs: None,
            profiles=roster,
        )

    def test_round_limit_stops_simulation(self):
        roster = build_agent_roster(5, seed=1)

        def always_add(offer, score, round_num, history):
            return [
                PersonaVote(p.name, p.emoji, "ADD", 0.9, "always add")
                for p in roster
            ]

        class AlwaysSafeRng:
            def random(self):
                return 0.99

        vote_collector = always_add
        result = run_simulation(
            agent_count=5,
            seed=1,
            round_limit=3,
            rng=AlwaysSafeRng(),
            offer_rng=random.Random(10),
            mock=True,
            vote_collector=vote_collector,
            stdout=lambda *_args, **_kwargs: None,
            profiles=roster,
        )
        assert result.stopped_by_round_limit is True
        assert result.rounds_attempted == 3
        assert result.final_outcome == "NONE"

    def test_cash_out_ends_simulation(self):
        result = self._run_mock_sim(
            seed=5,
            round_limit=50,
            bust_rng=random.Random(1),
        )
        assert result.final_outcome in {"CASH_OUT", "BUST", "NONE"}
        if result.final_outcome == "CASH_OUT":
            assert result.stopped_by_round_limit is False

    def test_majority_aggregation_with_scaled_roster(self):
        roster = build_agent_roster(7, seed=3)
        vote_collector, _ = build_vote_collectors(
            roster, mock=True, agent_service=None
        )
        state = GameState()
        history = GameHistory()
        state, votes, majority = process_round(
            state, offer=50, rng=random.Random(0), history=history, collect_votes_fn=vote_collector
        )
        assert len(votes) == 7
        assert majority == count_majority(votes)


class TestSimulationPersistence:
    def test_simulation_saves_history(self, tmp_path: Path):
        roster = build_agent_roster(5, seed=1)
        vote_collector, _ = build_vote_collectors(
            roster, mock=True, agent_service=None
        )
        history_path = tmp_path / "sim.json"
        run_simulation(
            agent_count=5,
            seed=1,
            round_limit=2,
            mock=True,
            vote_collector=vote_collector,
            history_file=str(history_path),
            save_history_fn=lambda h, p, **kw: Path(p).write_text("saved", encoding="utf-8"),
            stdout=lambda *_args, **_kwargs: None,
            profiles=roster,
            metrics=AgentCallMetrics(agent_count=5, max_concurrency=1),
        )
        assert history_path.exists()
