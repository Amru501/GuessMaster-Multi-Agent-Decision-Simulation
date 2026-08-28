# Multi-Personality Number Game

A terminal-based number game where five distinct personas vote on each offer you make. **V1** uses local [Ollama](https://ollama.com/) for independent LLM votes; **V0 mock mode** remains available for offline play and tests.

## Prerequisites

1. **Python 3.10+**
2. **Ollama** installed and running locally  
   - Download: https://ollama.com/download  
   - Start the Ollama app or run `ollama serve`
3. **A local model** pulled and available, for example:

   ```bash
   ollama pull qwen2.5:3b
   ```

## Setup

```bash
python -m venv .venv

# Windows
.venv\Scripts\activate

# macOS / Linux
source .venv/bin/activate

pip install -r requirements.txt
```

Copy the example environment file and set your model:

```bash
copy .env.example .env
```

Edit `.env`:

```env
OLLAMA_HOST=http://localhost:11434
OLLAMA_MODEL=qwen2.5:3b
OLLAMA_TIMEOUT_SECONDS=180
OLLAMA_KEEP_ALIVE=10m
```

| Variable | Required | Default | Description |
|----------|----------|---------|-------------|
| `OLLAMA_HOST` | No | `http://localhost:11434` | Ollama server URL |
| `OLLAMA_MODEL` | **Yes** | — | Installed local model name |
| `OLLAMA_TIMEOUT_SECONDS` | No | `180` | HTTP timeout per request (must be positive) |
| `OLLAMA_KEEP_ALIVE` | No | `10m` | How long Ollama keeps the model loaded in memory |

No API key is required — everything runs against your local Ollama instance.

## Run

**Normal mode** (Ollama LLM personas):

```bash
python main.py
```

On first launch, the game verifies Ollama is reachable, confirms the model is installed, then prints `Warming up local model…` and sends a small structured request. This loads the model into memory so the first real persona vote is less likely to time out on a cold start. When warm-up succeeds you will see `Model ready.`

**Mock mode** (deterministic V0 personas, no Ollama needed):

```bash
python main.py --mock
```

## Play the browser game

`Tower Votes` is a local browser game layered on top of the same Python game
engine. Each accepted offer adds that many animated slabs to your tower. A bust
collapses the tower; a REJECT cashes it out. When a run ends, the stage zooms
out to compare the completed tower with recent local runs.

Install the updated requirements once:

```bash
pip install -r requirements.txt
```

Start with deterministic mock personas:

```bash
python web_app.py --mock
```

Or start the real local-Ollama panel:

```bash
python web_app.py
```

Then open [http://127.0.0.1:5050](http://127.0.0.1:5050). Completed runs are stored
locally in `data/tower-runs.json` (gitignored). The UI shows your **best five**
runs ranked by tower height; zero-slab runs are hidden.

**Show history during play:**

```bash
python main.py --show-history
```

**Save history to JSON when the game ends:**

```bash
python main.py --history-file game-history.json
```

**Save statistics only:**

```bash
python main.py --stats-file game-stats.json
```

```bash
python main.py --adaptive
```

When `--history-file` is used, the saved JSON includes both raw round history and calculated statistics.

Use `--mock` when Ollama is not installed, not running, or you want fast offline play without waiting for model inference.

### Agent failures during a round

If a persona call fails mid-round (timeout, malformed response, etc.), the game:

- Shows which persona failed and the technical error
- Cancels the round without changing your score
- Returns you to the same round so you can retry or quit

No vote is invented and the failure does not count as a rejection, bust, or game over.

## Test

Tests mock or inject the Ollama client and never require a running Ollama instance:

```bash
pytest
```

Verbose output:

```bash
pytest -v
```

## Game Rules

- The game starts with **score = 0** and **round = 1**.
- Each round, enter an integer **offer from 1 to 100** (or type `q` / `quit` to exit).
- Each offer has a bust probability:

  `bust_probability = min(0.70, 0.02 + number / 240)`

- Five personas independently vote **ADD** or **REJECT**:
  - **Analyst** 📊 — moderate, logic-based
  - **Gambler** 🎲 — aggressive, risk-seeking
  - **Conservative** 🛡️ — risk-averse
  - **Impulsive** ⚡ — instinct-driven
  - **Strategist** ♟️ — balances score, offer value, and risk

- The Python engine counts votes; **ADD** or **REJECT** wins by strict majority (ties are impossible with five voters). The LLM never calculates the majority or modifies game state.
- If **ADD** has the majority:
  - A bust roll is made using the bust probability.
  - **Safe:** the offer is added to your score, the round increments, and play continues.
  - **Bust:** game over with **final score = 0**.
- If **REJECT** has the majority:
  - You cash out with your **current score** as the final score.

## Project Layout

```
main.py              CLI entry point (--mock / Ollama mode)
agents/
  profiles.py        PersonaProfile definitions and prompt builder
  adaptation.py    Bounded risk-tolerance adaptation from history
  deliberation.py  Deliberation brief and round result types
  deliberation_prompts.py  Final-vote prompt builder
  relationships.py Static persona relationship graph (V7)
  persona_generator.py  Seeded trait-based persona generation (V8)
  simulation_config.py  Agent-count and concurrency validation (V8)
  mock_factory.py    Mock voters for arbitrary rosters (V8)
  metrics.py         Simulation latency metrics (V8)
  personas.py        V0 mock voters (use shared profiles)
  service.py         Ollama calls and vote conversion
ai/
  config.py          .env configuration loading and validation
  ollama_client.py   Only module that imports ollama
game/
  engine.py          Game state and round processing
  history.py         Round records, outcomes, bounded memory
  statistics.py      Post-game behavioral metrics
  simulation.py      Non-interactive simulation runner (V8)
  rules.py           Bust math, validation, majority counting
models/
  schemas.py         Pydantic LLM response schema
tests/
```

## Version Notes

**V0** used five deterministic mock personas. Use `python main.py --mock` to play that mode.

**V1** replaces mock voting with five independent Ollama calls — one per persona — while keeping the same game rules, majority logic, and bust behavior in Python.

**V1.1** adds configurable timeouts and keep-alive, first-run model warm-up, round cancellation on agent failures, and tighter Ollama request limits (`num_predict`) for reliable short JSON responses.

**V2** replaces one-line persona descriptions with explicit **PersonaProfile** behavioral profiles (objective, risk tolerance, philosophy, tendencies, communication style, and anti-patterns). Prompts are assembled from these fields so each persona receives a rich, consistent identity. Mock mode uses the same profile definitions for names and emojis.

## Persona Modeling

Each persona is defined by a reusable `PersonaProfile` rather than a single hard-coded instruction string. Profiles include identity, objective, risk tolerance (0.0–1.0), decision philosophy, behavioral tendencies, communication style, and anti-patterns. The prompt builder turns these fields into an independent vote prompt for each call.

Different persona behavior does **not** require different underlying models. The same local model (e.g. `qwen2.5:3b`) can play every role because behavior is shaped by the profile and prompt, not by separate fine-tuned weights. Each persona still receives its own isolated call with no visibility into other votes.

## Round History and Agent Memory (V3)

Each game keeps an in-memory **GameHistory** of completed rounds. A round is recorded only after it finishes successfully — technical failures that cancel a round are **not** stored.

Every completed record includes the round number, offer, scores before/after, bust probability, all persona votes (with reasons), majority decision, and outcome (`SAFE_ADD`, `BUST`, or `CASH_OUT`).

**Bounded prompt memory:** before each vote, personas receive a compact summary of the latest **3 successful (`SAFE_ADD`) rounds** only — offer, majority, outcome, and score after. They never see other personas' current-round votes. The **Strategist** prompt explicitly instructs use of this history to protect or pursue long-term score; other personas receive the same facts but decide in character.

Use `--show-history` to print completed rounds during a game. Use `--history-file path.json` to save readable JSON when the game ends. Prior games are not loaded automatically.

Example saved history (includes statistics when using `--history-file`):

```json
{
  "rounds": [
    {
      "round_number": 1,
      "offer": 50,
      "score_before": 0,
      "score_after": 50,
      "bust_probability": 0.4666666666666667,
      "votes": [
        {
          "name": "Analyst",
          "emoji": "📊",
          "decision": "ADD",
          "confidence": 0.82,
          "reason": "Expected gain meets threshold."
        }
      ],
      "majority_decision": "ADD",
      "outcome": "SAFE_ADD"
    }
  ],
  "statistics": {
    "completed_rounds": 1,
    "final_outcome": "QUIT",
    "final_score": 50,
    "average_offer": 50.0,
    "add_majority_rounds": 1,
    "reject_majority_rounds": 0,
    "bust_count": 0,
    "personas": []
  }
}
```

**V3** adds round history, bounded agent memory in prompts, `--show-history`, and `--history-file`.

## Post-Game Statistics (V4)

When a game ends, the CLI prints a **post-game statistics report**. Metrics are derived from completed round history and describe **behavioral patterns**, not objective correctness — there is no “success rate” and votes are never labeled good or bad.

**Per persona:** rounds voted, ADD/REJECT counts and percentages, average confidence, majority-alignment rate, ADD votes before `SAFE_ADD`, ADD votes before `BUST`.

**Game summary:** completed rounds, final outcome, final score, average offer, ADD-majority count, REJECT-majority count, bust count.

Use `--stats-file path.json` to save statistics alone. Games with zero completed rounds produce empty metrics safely.

## Bounded Adaptive Personalities (V5)

Use `--adaptive` to enable **optional** risk-tolerance adjustment during a single game. Base `PersonaProfile` definitions are **immutable**; adaptation affects LLM prompts only, never Python game rules.

**Transparent adjustment rules** (from completed rounds only — not cancelled technical failures):

| Event | Effect on persona |
|-------|-------------------|
| Voted **ADD** on a **SAFE_ADD** round | Risk tolerance **+0.03** |
| Voted **ADD** on a **BUST** round | Risk tolerance **−0.03** |
| Voted **REJECT** | No change (REJECT does not imply causing the outcome) |
| **CASH_OUT** round | No change |

Total adjustment is clamped to **−0.15 … +0.15**. Effective risk tolerance = base + adjustment (clamped to 0.0–1.0).

When enabled, prompts show base and effective risk tolerance with the adjustment explained. Post-game statistics include adjustment fields. Default behavior (without `--adaptive`) uses fixed base profiles.

**Limitations:** adaptation is deterministic, in-memory, per-game only, and does not prove a persona was objectively right or wrong — it only reflects recent voting experience.

## Optional Deliberation Mode (V6)

Use `--deliberate` to enable a **two-stage voting experiment** that is separate from normal independent play:

```bash
python main.py --deliberate
python main.py --mock --deliberate
```

**Warning:** Deliberation **removes vote independence**. Personas see each other's initial votes before casting a final vote. This is a controlled comparison experiment — not the same game as default mode. Results from deliberation runs should not be directly compared to independent-voting runs without acknowledging that difference.

**Round flow (deliberation only):**

1. Each persona casts an **initial independent vote** (same V1/V2 prompt flow as normal mode).
2. Python collects all initial votes and builds a shared **deliberation brief** (name, decision, confidence, reason).
3. Each persona receives the brief plus its own game state and submits one **final vote**.
4. Python counts **only final votes** for the majority. The LLM never calculates vote counts or outcomes.

The CLI shows initial votes, the deliberation brief, final votes, vote-change summary, and final majority. Completed history records store both `initial_votes` and final `votes` when deliberation is enabled.

Technical failure at **either** stage cancels the round with no score change — same as V1.1 independent mode. Normal mode (without `--deliberate`) is unchanged: one vote per persona per round.

## Persona Relationship Graph (V7)

Use `--relationships` with `--deliberate` to add an **experimental influence layer** during final deliberation only. Relationships do **not** change Python vote counting, bust math, or any game rules — they appear only as optional context in final deliberation prompts.

```bash
python main.py --deliberate --relationships
python main.py --mock --deliberate --relationships --verbose
python main.py --export-graph persona-graph.json
```

**Warning:** This is an experimental social-influence layer on top of deliberation (which already removes independence). Use it to study how stated inter-persona attitudes might shift final votes — not as a neutral baseline.

`--relationships` alone has no effect; both `--deliberate` and `--relationships` must be active. Use `--verbose` to print each persona's outgoing relationship context during deliberation rounds.

Each relationship edge includes a source persona, target persona, type (`trusts`, `distrusts`, `respects`, `dismisses`), influence weight (−1.0 … 1.0), and a short explanation shown in prompts. Each persona receives **only its outgoing edges**, e.g. “You tend to trust Analyst's quantitative analysis.”

The graph is **static** for now — relationships do not evolve during play.

### Static relationship map

```
                 ┌─────────────┐
                 │  Strategist │
                 └──────▲──┬───┘
            respects     │ distrusts
                 ┌───────┘ └───────┐
           ┌─────┴─────┐     ┌─────┴─────┐
           │  Analyst  │     │ Impulsive │
           └─────▲──┬──┘     └─────▲──┬──┘
      trusts      │ dismisses  respects│ dismisses
           ┌──────┴───┐         ┌─────┴─────┐
           │Conservative│     │  Gambler  │
           └──────▲─────┘     └─────▲─────┘
           dismisses│ trusts/distrusts
                    └───────────────┘
```

| Source → Target | Type | Weight | Effect in prompt |
|-----------------|------|--------|------------------|
| Analyst → Strategist | respects | +0.65 | Respect long-term score reasoning |
| Analyst → Gambler | dismisses | −0.55 | Discount risk-seeking arguments |
| Gambler → Impulsive | trusts | +0.50 | Trust bold instinct |
| Gambler → Conservative | distrusts | −0.45 | Distrust overcautious caution |
| Conservative → Analyst | trusts | +0.60 | Trust quantitative analysis |
| Conservative → Gambler | dismisses | −0.70 | Discount risk-seeking arguments |
| Impulsive → Gambler | respects | +0.40 | Respect appetite for bold moves |
| Impulsive → Analyst | dismisses | −0.35 | Dismiss slow number-crunching |
| Strategist → Analyst | respects | +0.55 | Respect expected-value reasoning |
| Strategist → Impulsive | distrusts | −0.50 | Distrust gut-driven swings |

Export the full graph as JSON with `--export-graph <path>` (no game run required).

## Scaled Simulation Experiments (V8)

The default interactive game remains **five named personas** with no CLI changes required. Use scaling flags for controlled experiments with additional generated agents.

```bash
# Default — unchanged five-persona interactive game
python main.py --mock

# 21-agent mock simulation (seeded, auto-saves history)
python main.py --mock --simulate --agent-count 21 --seed 42 --round-limit 10

# 51-agent experiment with bounded Ollama concurrency
python main.py --simulate --agent-count 51 --seed 7 --max-concurrency 2 --round-limit 5
```

### Scaling flags

| Flag | Default | Description |
|------|---------|-------------|
| `--agent-count N` | 5 | Total voters (odd, 5–51). Core five personas are always included. |
| `--seed N` | 42 in simulate | Reproducible generated personas and offer sequence. |
| `--round-limit N` | none | Stop simulation after N rounds (otherwise until bust or cash-out). |
| `--simulate` | off | Non-interactive mode with seeded offers 1–100. |
| `--max-concurrency N` | 1 | Concurrent Ollama persona calls (1 … agent-count). |

**Odd agent count required** — even values are rejected with a helpful message so majority ties cannot occur.

Additional personas are generated from controlled trait combinations (risk tolerance, objective, decision philosophy, communication style). The original Analyst, Gambler, Conservative, Impulsive, and Strategist profiles are never modified.

### Performance reporting

Simulation runs report:

- Total round latency
- Average persona-call latency
- Successful / failed call counts
- Configured agent count and concurrency

Python majority aggregation remains deterministic; concurrency affects scheduling only, not vote counting order.

### Resource warnings

This project does **not** target 100–200 agents by default. Practical limits depend on your CPU/GPU, Ollama model size, and `--max-concurrency`. Start with `--mock --simulate` to validate experiment design, then scale Ollama runs gradually (e.g. 21 → 51 agents, concurrency 1–2). Large agent counts multiply LLM calls per round and can exhaust memory or exceed timeouts.
#   g u e s s - m a s t e r  
 