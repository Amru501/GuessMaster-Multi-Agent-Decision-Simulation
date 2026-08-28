# 🧠 Guess Master

### A Multi-Agent AI Decision-Making Game

Guess Master is a multi-agent decision-making game where multiple AI personas independently analyze the same risk and vote on whether the player should **ADD** the offered value or **REJECT** it.

What starts as a simple number game becomes an experimental platform for exploring:

- Multi-agent systems
- AI personas and behavioral modeling
- Structured LLM outputs
- Agent memory
- Adaptive decision-making
- Multi-agent deliberation
- Agent relationships and influence
- Procedurally generated personas
- Large-scale simulations
- Behavioral statistics
- Local LLM inference

The AI makes the decisions. **Python makes the rules.**

---

## 🎮 The Concept

Each round, the player receives an offer between **1 and 100**.

A panel of AI personalities analyzes the offer.

For example:

| Agent | Personality | Decision Style |
|---|---|---|
| 📊 Analyst | Quantitative | Expected-value driven |
| 🎲 Gambler | Aggressive | High-risk / high-reward |
| 🛡️ Conservative | Risk-averse | Protect the current score |
| ⚡ Impulsive | Instinctive | Fast, intuition-based decisions |
| ♟️ Strategist | Long-term | Risk-adjusted thinking |

Each agent independently decides:

> **ADD** — take the risk and add the offer to the score

or

> **REJECT** — reject the offer and end the run.

The majority decision determines what happens next.

If **ADD** wins, the game performs a bust roll.

If the roll succeeds:

Current Score + Offer

If the roll fails:

💥 BUST
Final Score = 0

The goal is simple:

Build the tallest tower without getting greedy.

✨ Features
🤖 Multi-Agent AI

Instead of relying on a single AI response, Guess Master uses multiple AI personas to make decisions.

Each agent receives its own persona-specific context and produces a structured decision.

The default system uses five core personas, but the architecture supports dynamically generated agent rosters.

🎭 Behavioral Personas

Agents are represented using structured PersonaProfile objects.

A persona can define:

Identity
Objective
Risk tolerance
Decision philosophy
Behavioral tendencies
Communication style
Anti-patterns

This allows the same underlying LLM to behave like fundamentally different decision-makers.

For example:

Gambler
→ prioritizes upside
→ accepts high risk
→ more likely to ADD

Conservative
→ prioritizes score preservation
→ dislikes uncertainty
→ more likely to REJECT

This makes the system persona-driven rather than prompt-driven.

🧠 LLM Architecture

Guess Master uses Ollama for local LLM inference.

The LLM is responsible for:

Understanding the offer
Applying the persona's reasoning style
Evaluating risk
Producing a decision
Providing confidence
Explaining its reasoning

The LLM does not control the game state.

Instead, the model returns a structured response that is validated before being passed to the game engine.

Conceptually:

             ┌──────────────────┐
             │    Game Round    │
             └────────┬─────────┘
                      │
                      ▼
             ┌──────────────────┐
             │ Persona Prompts  │
             └────────┬─────────┘
                      │
        ┌─────────────┼─────────────┐
        ▼             ▼             ▼
     Analyst       Gambler      Conservative
        │             │             │
        ▼             ▼             ▼
      LLM           LLM           LLM
        │             │             │
        └─────────────┼─────────────┘
                      ▼
              Structured Votes
                      │
                      ▼
             ┌──────────────────┐
             │   Game Engine    │
             └────────┬─────────┘
                      │
             ┌────────┴────────┐
             ▼                 ▼
          Majority          Game Rules
             │                 │
             └────────┬────────┘
                      ▼
                 Game State
🛡️ LLM vs Game Logic

One of the core design principles of Guess Master is:

LLMs propose. Deterministic code disposes.

The AI can say:

{
  "decision": "ADD",
  "confidence": 0.82,
  "reason": "The potential reward justifies the moderate risk."
}

But it cannot directly modify:

Score
Bust probability
Round number
Majority result
Game-over state

Python remains the source of truth for the game.

This prevents unpredictable LLM output from corrupting the game mechanics.

🗳️ Majority Voting

Once the agents have voted, the game engine counts their decisions.

With five agents:

ADD      █████  3
REJECT   ███    2

Result:

MAJORITY → ADD

The voting system is deterministic and independent from the LLM.

The system also enforces odd agent counts when scaling the number of agents, preventing majority ties.

🧠 Agent Memory

Agents can receive a bounded summary of previous completed rounds.

This gives the personas limited game history without giving them unlimited context.

For example:

Previous Round:
Offer: 20
Decision: ADD
Result: SAFE_ADD
Score: 20

Current Round:
Offer: 35

The system intentionally keeps memory bounded to prevent unnecessary context growth.

Agent memory is also separated from current-round decision making.

📈 Adaptive Personalities

Guess Master includes an optional adaptive mode.

Enable it with:

python main.py --adaptive

Agents can gradually adjust their effective risk tolerance based on previous outcomes.

For example:

ADD + SAFE_ADD
        ↓
Risk tolerance increases

ADD + BUST
        ↓
Risk tolerance decreases

REJECT
        ↓
No change

Adaptation is bounded so that agents don't become permanently extreme.

The original persona profile remains immutable; adaptation modifies only the effective risk tolerance during the game.

Important

This is not model training.

The LLM weights are never changed.

The system modifies the context given to the model.

💬 Multi-Agent Deliberation

Guess Master can optionally use a two-stage decision process.

Enable it with:

python main.py --deliberate

Instead of:

Agent → Vote

the system becomes:

Initial Votes
      ↓
Group Deliberation
      ↓
Final Votes
      ↓
Majority Decision

Agents can reconsider their original position after seeing the group's initial decisions.

This makes it possible to experiment with questions such as:

Do agents converge?
Does a strong majority influence minority agents?
Does deliberation improve outcomes?
Does deliberation create groupthink?
How does consensus affect risk-taking?
🔗 Persona Relationships

Guess Master also supports relationships between agents.

Enable them with:

python main.py --deliberate --relationships

Agents can have relationships such as:

TRUSTS
DISTRUSTS
RESPECTS
DISMISSES

Relationships can influence how agents interpret other agents during deliberation.

For example:

Analyst
    ↓ respects
Strategist

Gambler
    ↓ distrusts
Conservative

The relationship system affects agent context, not the underlying voting mathematics.

👥 Dynamic Persona Generation

The system is not limited to five hard-coded agents.

Additional personas can be procedurally generated using combinations of controlled traits.

Generated personas can vary in:

Risk tolerance
Objective
Decision philosophy
Communication style
Behavioral tendencies
Anti-patterns

The simulation system supports configurable agent counts while enforcing valid voting configurations.

This allows experiments with larger groups such as:

5 agents
11 agents
21 agents
51 agents
🧪 Simulation Mode

Guess Master includes a non-interactive simulation system for running experiments without manually playing every round.

Simulation parameters can include:

Agent count
Random seed
Round limit
Mock vs LLM agents
Deliberation
Adaptive behavior
Generated personas
History
Statistics
Performance metrics

Example:

python main.py --simulate --mock --agent-count 11 --seed 42

This makes the project useful not only as a game, but also as a small multi-agent experimentation framework.

📊 Behavioral Statistics

After a game or simulation, the system can collect statistics such as:

Completed rounds
Final score
Final outcome
Average offer
ADD count
REJECT count
ADD percentage
REJECT percentage
Average confidence
Majority alignment
ADD decisions before SAFE_ADD
ADD decisions before BUST
Adaptive risk changes

These statistics describe agent behavior, rather than pretending there is a universal "correct" AI decision.

⚡ Performance Metrics

LLM calls can be instrumented using AgentCallMetrics.

Tracked information includes:

Successful calls
Failed calls
Total latency
Average persona-call latency
Round latency
Number of agents
Configured concurrency

This makes it possible to evaluate the performance cost of scaling the multi-agent system.

🛡️ Failure-Safe Execution

LLM applications can fail for reasons unrelated to game logic.

For example:

Ollama unavailable
Model timeout
Invalid response
Connection failure

Guess Master does not silently convert these failures into arbitrary decisions.

If a persona call fails during a round:

LLM failure
    ↓
Round cancelled
    ↓
Game state preserved
    ↓
Player can retry

The system therefore avoids corrupting the score or inventing an AI decision when the model failed.

🧪 Mock Mode

Guess Master includes deterministic mock agents.

Run:

python main.py --mock

Mock mode is useful for:

Development
Testing
Debugging
Demonstrations
Offline usage
Reproducible simulations

This means the application does not require an LLM server just to test the game mechanics.

🌐 Browser Interface

Guess Master also includes a local browser version called:

Tower Votes

The browser interface presents the game as a visual tower-building experience.

Players can:

Enter offers
View persona decisions
See majority results
Build their tower
Track their score
Play multiple runs
Compare previous runs

Run the web version with mock agents:

python web_app.py --mock

Or use the local Ollama model:

python web_app.py

Then open:

http://127.0.0.1:5050
🏗️ Project Architecture
guess-master/
│
├── ai/
│   ├── config.py
│   └── ollama_client.py
│
├── agents/
│   ├── profiles.py
│   ├── personas.py
│   ├── service.py
│   ├── adaptation.py
│   ├── deliberation.py
│   ├── deliberation_prompts.py
│   ├── relationships.py
│   ├── persona_generator.py
│   ├── mock_factory.py
│   ├── simulation_config.py
│   └── metrics.py
│
├── game/
│   ├── engine.py
│   ├── rules.py
│   ├── history.py
│   ├── statistics.py
│   └── simulation.py
│
├── models/
│   └── schemas.py
│
├── templates/
│   └── index.html
│
├── static/
│   ├── game.css
│   └── game.js
│
├── tests/
│   ├── test_adaptation.py
│   ├── test_deliberation.py
│   ├── test_history.py
│   ├── test_llm.py
│   ├── test_main.py
│   ├── test_profiles.py
│   ├── test_relationships.py
│   ├── test_simulation.py
│   ├── test_statistics.py
│   ├── test_v11.py
│   └── test_web_app.py
│
├── main.py
├── web_app.py
├── requirements.txt
├── pytest.ini
└── .env.example
🔧 Installation
Requirements
Python 3.10+
Ollama
A compatible local LLM
pip

Ollama:

https://ollama.com/

1. Clone the repository
git clone https://github.com/Amru501/guess-master.git
cd guess-master
2. Create a virtual environment
Windows
python -m venv .venv
.venv\Scripts\activate
macOS / Linux
python3 -m venv .venv
source .venv/bin/activate
3. Install dependencies
pip install -r requirements.txt
🤖 Ollama Setup

Install Ollama and download a compatible model.

For example:

ollama pull qwen2.5:3b

Create your .env file from the example:

Windows
copy .env.example .env
macOS / Linux
cp .env.example .env

Example configuration:

OLLAMA_HOST=http://localhost:11434
OLLAMA_MODEL=qwen2.5:3b
OLLAMA_TIMEOUT_SECONDS=180
OLLAMA_KEEP_ALIVE=10m

Make sure Ollama is running before starting the game.

🎮 Usage
Basic CLI Game
python main.py

This starts the normal game using the configured Ollama model.

Mock Mode
python main.py --mock

Runs the game without Ollama.

Adaptive Mode
python main.py --adaptive

Enables adaptive risk tolerance.

Deliberation Mode
python main.py --deliberate

Enables two-stage agent deliberation.

Relationship Mode
python main.py --deliberate --relationships

Enables deliberation and persona relationships.

Verbose Mode
python main.py --verbose

Useful for seeing additional agent/game information during execution.

Show History
python main.py --show-history

Displays completed round history during gameplay.

Save Game History
python main.py --history-file game-history.json
Save Statistics
python main.py --stats-file game-stats.json
Export Relationship Graph
python main.py --export-graph persona-graph.json
🌐 Running the Web Version
Mock Mode
python web_app.py --mock
Ollama Mode
python web_app.py

Open:

http://127.0.0.1:5050
🧪 Running Tests

Guess Master includes a pytest test suite covering the major components of the system.

Run:

pytest

For verbose output:

pytest -v

The test suite covers areas including:

Game rules
Game engine
Persona profiles
LLM integration
History
Statistics
Adaptation
Deliberation
Relationships
Persona generation
Simulation
CLI behavior
Web application behavior

LLM-dependent functionality can be mocked, allowing the test suite to run without a live Ollama model.

🧩 Design Principles
1. Deterministic Game State

The game engine is the authority on:

Score
Bust probability
Majority voting
Round progression
Game-over conditions
2. Structured AI Output

LLM responses are validated against structured schemas rather than being interpreted as arbitrary text.

This reduces the chance of malformed model output affecting the game.

3. Separation of Concerns

The project separates:

AI integration
       ↓
Agent behavior
       ↓
Game logic
       ↓
Statistics
       ↓
Interfaces

The CLI and web interface use the same underlying game concepts rather than implementing separate game rules.

4. Explicit Experimental Modes

Advanced behavior is opt-in.

The basic game remains simple, while users can progressively enable:

Adaptive behavior
       ↓
Deliberation
       ↓
Relationships
       ↓
Generated agents
       ↓
Simulation

This makes it possible to compare different multi-agent configurations.

📚 Version Evolution

The project was developed incrementally, with each stage adding a new capability.

Version	Feature
V0	Five deterministic mock personas
V1	Local Ollama-backed LLM agents
V1.1	Reliability improvements and structured LLM responses
V2	Rich reusable persona profiles
V3	Bounded game history and agent memory
V4	Behavioral statistics
V5	Adaptive risk tolerance
V6	Two-stage deliberation
V7	Persona relationship graph
V8	Generated personas, configurable agent counts and simulation
Web	Browser-based Tower Votes interface
⚠️ Limitations

Guess Master is an experimentation project rather than a claim that each persona represents a completely independent intelligence.

Shared underlying model

Multiple personas can use the same underlying LLM.

The diversity primarily comes from:

Persona profiles
Prompt construction
Context
Decision history
Relationships
Adaptation
Deliberation reduces independence

In independent mode, agents do not see other agents' current-round decisions.

In deliberation mode, agents can see the group's initial decisions.

Therefore deliberation intentionally changes the independence assumption.

Adaptation is not machine learning

Adaptive risk tolerance changes the prompt context.

It does not modify model weights.

There is no:

gradient descent
backpropagation
fine-tuning

taking place during gameplay.

Generated personas are not separate models

Generated agents are different behavioral configurations running on the same underlying inference infrastructure.

Local LLM performance depends on hardware

Response latency depends heavily on:

CPU
GPU
RAM
Model size
Quantization
Number of agents
Concurrent requests
🚀 Future Improvements

Potential future directions include:

Persistent long-term agent memory
Cross-game learning
Larger simulation experiments
Experiment dashboards
Visualization of agent behavior
More aggregation strategies
Weighted voting
Agent-specific learning
Evolving relationship networks
More advanced concurrency
Additional local LLM backends
Comparative model evaluation
Tournament-style agent competitions
🎯 What This Project Demonstrates

Guess Master demonstrates practical implementation of several modern AI engineering concepts:

                Guess Master
                     │
        ┌────────────┼────────────┐
        ▼            ▼            ▼
    LLM APIs     Agent Design   Game Engine
        │            │            │
        ▼            ▼            ▼
 Structured       Personas     Deterministic
   Output        + Memory         Rules
        │            │            │
        └────────────┼────────────┘
                     ▼
              Multi-Agent System
                     │
          ┌──────────┼──────────┐
          ▼          ▼          ▼
     Deliberation Adaptation Relationships
          │          │          │
          └──────────┼──────────┘
                     ▼
               Simulation
                     │
                     ▼
                Statistics

The project combines LLM reasoning with deterministic software engineering, rather than allowing an LLM to control the entire application.
