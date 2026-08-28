"""Local browser game for the Multi-Personality Number Game.

The browser layer is deliberately thin: all voting and game rules continue to
live in the existing engine modules used by the CLI.
"""

from __future__ import annotations

import argparse
import json
import random
import threading
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from flask import Flask, jsonify, render_template, request

from agents.personas import collect_mock_votes
from agents.service import AgentService, AgentVoteError
from ai.config import OllamaConfigError, load_ollama_config
from ai.ollama_client import (
    OllamaClient,
    OllamaConnectionError,
    OllamaModelError,
    OllamaResponseError,
)
from game.engine import GameState, PersonaVote, process_round
from game.history import GameHistory, build_completed_round_record, resolve_round_outcome
from game.rules import calculate_bust_probability, validate_offer


RUNS_PATH = Path("data") / "tower-runs.json"
MAX_SAVED_RUNS = 20
TOP_RUNS_DISPLAY = 5


def _make_ollama_service() -> AgentService:
    config = load_ollama_config()
    client = OllamaClient(
        host=config.host,
        timeout=config.timeout_seconds,
        keep_alive=config.keep_alive,
    )
    client.verify_connection()
    client.verify_model(config.model)
    service = AgentService(client, model=config.model)
    service.warmup()
    return service


def _vote_payload(vote: PersonaVote) -> dict[str, Any]:
    return {
        "name": vote.name,
        "emoji": vote.emoji,
        "decision": vote.decision,
        "confidence": vote.confidence,
        "reason": vote.reason,
    }


class TowerGame:
    """A single local play session backed by the established engine."""

    def __init__(self, *, mock: bool, agent_service: AgentService | None) -> None:
        self.mock = mock
        self.agent_service = agent_service
        self.lock = threading.Lock()
        self.reset()

    @property
    def mode_label(self) -> str:
        if self.mock:
            return "Mock personas"
        assert self.agent_service is not None
        return f"Ollama · {self.agent_service.model}"

    def reset(self) -> None:
        self.state = GameState()
        self.history = GameHistory()
        self.rng = random.Random()
        self.saved = False

    def status(self) -> dict[str, Any]:
        return {
            "score": self.state.score,
            "round": self.state.round,
            "game_over": self.state.game_over,
            "final_score": self.state.final_score,
            "mode": self.mode_label,
            "previous_runs": top_runs(TOP_RUNS_DISPLAY),
        }

    def _collector(self):
        if self.mock:
            return collect_mock_votes
        assert self.agent_service is not None
        return self.agent_service.collect_votes

    def submit_offer(self, raw_offer: object) -> tuple[dict[str, Any], int]:
        with self.lock:
            if self.state.game_over:
                return {
                    "error": "This run is over. Start a new tower to play again.",
                    "game_over": True,
                    "score": self.state.score,
                    "round": self.state.round,
                    "final_score": self.state.final_score,
                }, 409

            ok, offer, error = validate_offer(str(raw_offer or ""))
            if not ok or offer is None:
                return {"error": error or "Enter an offer from 1 to 100."}, 400

            score_before = self.state.score
            round_before = self.state.round
            bust_probability = calculate_bust_probability(offer)
            try:
                self.state, votes, majority = process_round(
                    self.state,
                    offer,
                    self.rng,
                    self.history,
                    self._collector(),
                )
            except AgentVoteError as exc:
                return {
                    "cancelled": True,
                    "error": exc.message,
                    "persona": exc.persona_name,
                    "score": self.state.score,
                    "round": self.state.round,
                }, 503

            outcome = resolve_round_outcome(
                majority,
                game_over=self.state.game_over,
                score_after=self.state.score,
            )
            self.history.add_completed_round(
                build_completed_round_record(
                    round_number=round_before,
                    offer=offer,
                    score_before=score_before,
                    score_after=self.state.score if outcome != "CASH_OUT" else score_before,
                    bust_probability=bust_probability,
                    votes=votes,
                    majority_decision=majority,
                    outcome=outcome,
                )
            )

            if self.state.game_over:
                self._save_run(outcome, peak_score=max(score_before, self.state.score))

            return {
                "offer": offer,
                "score_before": score_before,
                "score": self.state.score,
                "round": self.state.round,
                "majority": majority,
                "bust_probability": bust_probability,
                "bust_roll_applied": majority == "ADD",
                "outcome": outcome,
                "game_over": self.state.game_over,
                "final_score": self.state.final_score,
                "votes": [_vote_payload(vote) for vote in votes],
                "previous_runs": top_runs(TOP_RUNS_DISPLAY),
            }, 200

    def _save_run(self, outcome: str, *, peak_score: int) -> None:
        if self.saved:
            return
        record = {
            "id": datetime.now(UTC).strftime("%Y%m%d%H%M%S%f"),
            "finished_at": datetime.now(UTC).isoformat(),
            "final_score": self.state.final_score if self.state.final_score is not None else self.state.score,
            "peak_score": peak_score,
            "rounds": len(self.history.rounds),
            "outcome": outcome,
        }
        runs = [record, *load_runs()][:MAX_SAVED_RUNS]
        RUNS_PATH.parent.mkdir(parents=True, exist_ok=True)
        RUNS_PATH.write_text(json.dumps(runs, indent=2), encoding="utf-8")
        self.saved = True


def _run_slabs(run: dict[str, Any]) -> int:
    """Best tower height for a saved run (peak build, not post-bust zero)."""
    peak = run.get("peak_score")
    final = run.get("final_score", 0)
    if peak is None:
        return int(final or 0)
    return int(max(peak, final or 0))


def load_runs(*, min_slabs: int = 0) -> list[dict[str, Any]]:
    if not RUNS_PATH.exists():
        return []
    try:
        data = json.loads(RUNS_PATH.read_text(encoding="utf-8"))
        runs = data if isinstance(data, list) else []
    except (OSError, json.JSONDecodeError):
        return []
    if min_slabs > 0:
        runs = [run for run in runs if _run_slabs(run) >= min_slabs]
    return runs


def top_runs(limit: int = TOP_RUNS_DISPLAY, *, min_slabs: int = 1) -> list[dict[str, Any]]:
    """Highest slab counts first, for the comparison panel."""
    ranked = load_runs(min_slabs=min_slabs)
    ranked.sort(key=_run_slabs, reverse=True)
    return ranked[:limit]


def create_app(*, mock: bool = False, agent_service: AgentService | None = None) -> Flask:
    app = Flask(__name__)
    game = TowerGame(mock=mock, agent_service=agent_service)
    app.config["TOWER_GAME"] = game

    @app.get("/")
    def index():
        return render_template("index.html", mode=game.mode_label)

    @app.get("/api/status")
    def status():
        return jsonify(game.status())

    @app.post("/api/new-game")
    def new_game():
        with game.lock:
            game.reset()
            return jsonify(game.status())

    @app.post("/api/offer")
    def offer():
        payload = request.get_json(silent=True) or {}
        response, status_code = game.submit_offer(payload.get("offer"))
        return jsonify(response), status_code

    return app


def main() -> None:
    parser = argparse.ArgumentParser(description="Run the local Tower Votes browser game.")
    parser.add_argument("--mock", action="store_true", help="Use V0 mock personas without Ollama.")
    parser.add_argument("--port", type=int, default=5050, help="Local port (default: 5050).")
    args = parser.parse_args()

    service = None
    if not args.mock:
        print("Preparing Ollama model…")
        try:
            service = _make_ollama_service()
        except (OllamaConfigError, OllamaConnectionError, OllamaModelError, OllamaResponseError) as exc:
            raise SystemExit(f"Could not start Ollama mode: {exc}") from exc
        print("Model ready.")

    app = create_app(mock=args.mock, agent_service=service)
    print(f"Open http://127.0.0.1:{args.port} in your browser.")
    app.run(host="127.0.0.1", port=args.port, debug=False)


if __name__ == "__main__":
    main()
