"""Agent vote collection via local Ollama."""

from __future__ import annotations

import threading
import time
from concurrent.futures import ThreadPoolExecutor, as_completed

from agents.adaptation import compute_persona_adaptation
from agents.deliberation import DeliberationRoundResult, build_deliberation_brief
from agents.deliberation_prompts import build_deliberation_prompt
from agents.metrics import AgentCallMetrics
from agents.profiles import PERSONA_PROFILES, PersonaProfile, build_persona_prompt
from agents.relationships import (
    DEFAULT_RELATIONSHIP_GRAPH,
    RelationshipGraph,
    build_relationship_context,
)
from ai.ollama_client import OllamaClient, OllamaResponseError
from game.engine import PersonaVote
from game.history import GameHistory
from game.rules import calculate_bust_probability


class AgentVoteError(Exception):
    """Raised when a persona vote cannot be obtained."""

    def __init__(self, persona_name: str, message: str, *, stage: str = "vote") -> None:
        self.persona_name = persona_name
        self.message = message
        self.stage = stage
        super().__init__(f"{persona_name}: {message}")


class AgentService:
    def __init__(
        self,
        ollama_client: OllamaClient,
        model: str,
        temperature: float = 0.4,
        adaptive: bool = False,
        relationships: bool = False,
        relationship_graph: RelationshipGraph | None = None,
        profiles: tuple[PersonaProfile, ...] | None = None,
        max_concurrency: int = 1,
        metrics: AgentCallMetrics | None = None,
    ) -> None:
        self._client = ollama_client
        self._model = model
        self._temperature = temperature
        self._adaptive = adaptive
        self._relationships = relationships
        self._relationship_graph = relationship_graph or DEFAULT_RELATIONSHIP_GRAPH
        self._profiles = profiles or PERSONA_PROFILES
        self._max_concurrency = max_concurrency
        self._metrics = metrics or AgentCallMetrics(
            agent_count=len(self._profiles),
            max_concurrency=max_concurrency,
        )
        self._semaphore = threading.Semaphore(max_concurrency)
        self.initial_vote_calls = 0
        self.final_vote_calls = 0

    @property
    def model(self) -> str:
        return self._model

    @property
    def adaptive(self) -> bool:
        return self._adaptive

    @property
    def relationships(self) -> bool:
        return self._relationships

    @property
    def relationship_graph(self) -> RelationshipGraph:
        return self._relationship_graph

    @property
    def profiles(self) -> tuple[PersonaProfile, ...]:
        return self._profiles

    @property
    def max_concurrency(self) -> int:
        return self._max_concurrency

    @property
    def metrics(self) -> AgentCallMetrics:
        return self._metrics

    def warmup(self) -> None:
        self._client.warmup(model=self._model)

    def _adaptation_for(self, history: GameHistory, profile: PersonaProfile):
        if not self._adaptive:
            return None
        return compute_persona_adaptation(history, profile)

    def _request_vote(self, profile: PersonaProfile, prompt: str, *, stage: str) -> PersonaVote:
        started = time.perf_counter()
        try:
            with self._semaphore:
                llm_response = self._client.chat_structured(
                    model=self._model,
                    prompt=prompt,
                    temperature=self._temperature,
                )
        except OllamaResponseError as exc:
            self._metrics.record_failure(time.perf_counter() - started)
            raise AgentVoteError(profile.name, str(exc), stage=stage) from exc
        except Exception as exc:
            self._metrics.record_failure(time.perf_counter() - started)
            raise AgentVoteError(
                profile.name,
                f"Unexpected error while fetching vote: {exc}",
                stage=stage,
            ) from exc

        self._metrics.record_success(time.perf_counter() - started)
        return PersonaVote(
            name=profile.name,
            emoji=profile.emoji,
            decision=llm_response.decision,
            confidence=round(llm_response.confidence, 2),
            reason=llm_response.reason,
        )

    def _vote_for_profile(
        self,
        profile: PersonaProfile,
        *,
        offer: int,
        score: int,
        round_num: int,
        bust_prob: float,
        history_summary: str,
        history: GameHistory,
        stage: str,
        deliberation_brief: str | None = None,
        own_initial: PersonaVote | None = None,
    ) -> PersonaVote:
        if deliberation_brief is not None and own_initial is not None:
            relationship_context = None
            if self._relationships:
                relationship_context = build_relationship_context(
                    profile.name, self._relationship_graph
                )
            prompt = build_deliberation_prompt(
                profile,
                score=score,
                round_num=round_num,
                offer=offer,
                bust_probability=bust_prob,
                history_summary=history_summary,
                deliberation_brief=deliberation_brief,
                own_initial=own_initial,
                adaptive=self._adaptive,
                risk_adaptation=self._adaptation_for(history, profile),
                relationship_context=relationship_context,
            )
        else:
            prompt = build_persona_prompt(
                profile,
                score=score,
                round_num=round_num,
                offer=offer,
                bust_probability=bust_prob,
                history_summary=history_summary,
                adaptive=self._adaptive,
                risk_adaptation=self._adaptation_for(history, profile),
            )
        return self._request_vote(profile, prompt, stage=stage)

    def _collect_votes_for_profiles(
        self,
        profiles: tuple[PersonaProfile, ...],
        offer: int,
        score: int,
        round_num: int,
        history: GameHistory,
        *,
        stage: str,
        deliberation_brief: str | None = None,
        initial_votes: list[PersonaVote] | None = None,
    ) -> list[PersonaVote]:
        bust_prob = calculate_bust_probability(offer)
        history_summary = history.bounded_summary()

        def fetch(profile: PersonaProfile) -> tuple[str, PersonaVote]:
            own_initial = None
            if initial_votes is not None:
                own_initial = next(v for v in initial_votes if v.name == profile.name)
            vote = self._vote_for_profile(
                profile,
                offer=offer,
                score=score,
                round_num=round_num,
                bust_prob=bust_prob,
                history_summary=history_summary,
                history=history,
                stage=stage,
                deliberation_brief=deliberation_brief,
                own_initial=own_initial,
            )
            return profile.name, vote

        votes_by_name: dict[str, PersonaVote] = {}
        if self._max_concurrency == 1:
            for profile in profiles:
                name, vote = fetch(profile)
                votes_by_name[name] = vote
                if stage == "initial":
                    self.initial_vote_calls += 1
                else:
                    self.final_vote_calls += 1
        else:
            with ThreadPoolExecutor(max_workers=min(len(profiles), self._max_concurrency)) as pool:
                futures = {pool.submit(fetch, profile): profile for profile in profiles}
                for future in as_completed(futures):
                    name, vote = future.result()
                    votes_by_name[name] = vote
                    if stage == "initial":
                        self.initial_vote_calls += 1
                    else:
                        self.final_vote_calls += 1

        return [votes_by_name[profile.name] for profile in profiles]

    def _collect_initial_votes(
        self, offer: int, score: int, round_num: int, history: GameHistory
    ) -> list[PersonaVote]:
        return self._collect_votes_for_profiles(
            self._profiles,
            offer,
            score,
            round_num,
            history,
            stage="initial",
        )

    def collect_votes(
        self, offer: int, score: int, round_num: int, history: GameHistory
    ) -> list[PersonaVote]:
        return self._collect_initial_votes(offer, score, round_num, history)

    def collect_deliberation_votes(
        self, offer: int, score: int, round_num: int, history: GameHistory
    ) -> DeliberationRoundResult:
        initial_votes = self._collect_initial_votes(offer, score, round_num, history)
        brief = build_deliberation_brief(initial_votes)
        final_votes = self._collect_votes_for_profiles(
            self._profiles,
            offer,
            score,
            round_num,
            history,
            stage="final",
            deliberation_brief=brief,
            initial_votes=initial_votes,
        )
        return DeliberationRoundResult(
            initial_votes=initial_votes,
            final_votes=final_votes,
        )
