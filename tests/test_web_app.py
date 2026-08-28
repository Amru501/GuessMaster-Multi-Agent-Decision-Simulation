"""API checks for the local Tower Votes browser game."""

from __future__ import annotations

import json

import web_app


def make_client(monkeypatch, tmp_path):
    monkeypatch.setattr(web_app, "RUNS_PATH", tmp_path / "tower-runs.json")
    app = web_app.create_app(mock=True)
    app.config["TESTING"] = True
    return app.test_client()


def test_status_starts_a_mock_game(monkeypatch, tmp_path):
    client = make_client(monkeypatch, tmp_path)

    response = client.get("/api/status")

    assert response.status_code == 200
    assert response.json["score"] == 0
    assert response.json["round"] == 1
    assert response.json["game_over"] is False
    assert response.json["mode"] == "Mock personas"


def test_offer_validation_returns_json_error(monkeypatch, tmp_path):
    client = make_client(monkeypatch, tmp_path)

    response = client.post("/api/offer", json={"offer": 101})

    assert response.status_code == 400
    assert "Offer must" in response.json["error"]


def test_mock_round_returns_full_vote_panel(monkeypatch, tmp_path):
    client = make_client(monkeypatch, tmp_path)

    response = client.post("/api/offer", json={"offer": 10})

    assert response.status_code == 200
    assert response.json["majority"] in {"ADD", "REJECT"}
    assert response.json["outcome"] in {"SAFE_ADD", "BUST", "CASH_OUT"}
    assert len(response.json["votes"]) == 5
    assert {"name", "emoji", "decision", "confidence", "reason"} <= set(
        response.json["votes"][0]
    )
    assert "bust_roll_applied" in response.json
    assert response.json["bust_roll_applied"] == (response.json["majority"] == "ADD")


def test_reject_majority_skips_bust_roll(monkeypatch, tmp_path):
    client = make_client(monkeypatch, tmp_path)

    response = client.post("/api/offer", json={"offer": 10})

    assert response.status_code == 200
    if response.json["majority"] == "REJECT":
        assert response.json["bust_roll_applied"] is False
        assert response.json["outcome"] == "CASH_OUT"


def test_new_game_resets_the_session(monkeypatch, tmp_path):
    client = make_client(monkeypatch, tmp_path)
    client.post("/api/offer", json={"offer": 10})

    response = client.post("/api/new-game")

    assert response.status_code == 200
    assert response.json["score"] == 0
    assert response.json["round"] == 1
    assert response.json["game_over"] is False


def test_offer_after_game_over_returns_409_with_flag(monkeypatch, tmp_path):
    client = make_client(monkeypatch, tmp_path)
    ended = False
    for offer in range(1, 101):
        response = client.post("/api/offer", json={"offer": offer})
        if response.status_code == 200 and response.json.get("game_over"):
            ended = True
            break
    assert ended, "expected a mock round to finish the run"

    response = client.post("/api/offer", json={"offer": 10})
    assert response.status_code == 409
    assert response.json["game_over"] is True
    assert "error" in response.json


def test_previous_runs_hide_zero_slab_towers(monkeypatch, tmp_path):
    runs_path = tmp_path / "tower-runs.json"
    monkeypatch.setattr(web_app, "RUNS_PATH", runs_path)
    runs_path.parent.mkdir(parents=True, exist_ok=True)
    runs_path.write_text(
        json.dumps(
            [
                {"final_score": 0, "peak_score": 0, "outcome": "BUST"},
                {"final_score": 42, "peak_score": 42, "outcome": "CASH_OUT"},
                {"final_score": 0, "peak_score": 15, "outcome": "BUST"},
            ]
        ),
        encoding="utf-8",
    )

    visible = web_app.load_runs(min_slabs=1)

    assert len(visible) == 2
    assert all(web_app._run_slabs(run) >= 1 for run in visible)


def test_top_runs_returns_best_five_in_order(monkeypatch, tmp_path):
    runs_path = tmp_path / "tower-runs.json"
    monkeypatch.setattr(web_app, "RUNS_PATH", runs_path)
    runs_path.write_text(
        json.dumps(
            [
                {"final_score": 10, "peak_score": 10},
                {"final_score": 50, "peak_score": 50},
                {"final_score": 0, "peak_score": 0},
                {"final_score": 30, "peak_score": 30},
                {"final_score": 80, "peak_score": 80},
                {"final_score": 20, "peak_score": 20},
                {"final_score": 60, "peak_score": 60},
            ]
        ),
        encoding="utf-8",
    )

    top = web_app.top_runs(5)

    assert [web_app._run_slabs(run) for run in top] == [80, 60, 50, 30, 20]
