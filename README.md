# 🧠 Guess Master

### Multi-Agent AI Decision Making Under Risk

**Guess Master** is a multi-agent AI game where multiple autonomous personas analyze the same offer, make independent decisions, and collectively determine whether you should take the risk.

What begins as a simple tower-building game becomes a platform for experimenting with **LLM-powered agents, behavioral personas, memory, adaptation, deliberation, relationships, and large-scale simulations.**

> **The AI makes the decisions. Python makes the rules.**

---

## 🎮 How It Works

Each round, you receive an offer between **1 and 100**.

Five AI personas evaluate the offer:

| Agent | Personality      | Approach                               |
| :---: | ---------------- | -------------------------------------- |
|   📊  | **Analyst**      | Quantitative and expected-value driven |
|   🎲  | **Gambler**      | Aggressive and reward-seeking          |
|  🛡️  | **Conservative** | Risk-averse and score-preserving       |
|   ⚡   | **Impulsive**    | Intuitive and spontaneous              |
|   ♟️  | **Strategist**   | Long-term and risk-adjusted            |

Each agent independently chooses:

### 🟢 ADD

Take the risk and add the offer to the tower.

### 🔴 REJECT

Reject the offer and end the run.

The majority decision determines what happens.

```text
                  OFFER
                    │
                    ▼
          ┌───────────────────┐
          │    AI PERSONAS    │
          └─────────┬─────────┘
                    │
        ┌───────────┼───────────┐
        ▼           ▼           ▼
     Analyst     Gambler    Conservative
        │           │           │
        └───────────┼───────────┘
                    │
                    ▼
              MAJORITY VOTE
                    │
             ┌──────┴──────┐
             ▼             ▼
           ADD           REJECT
             │             │
             ▼             ▼
         BUST ROLL      RUN ENDS
             │
       ┌─────┴─────┐
       ▼           ▼
     SAFE         BUST
       │           │
       ▼           ▼
   SCORE +       SCORE = 0
    OFFER
```

The objective:

> **Build the highest tower possible without getting greedy.**

---

# ✨ Why Guess Master?

Most AI game projects ask an LLM for a response and directly use that response.

Guess Master takes a different approach.

### The LLM handles reasoning.

### The application handles truth.

The model decides:

```text
ADD / REJECT
Confidence
Reasoning
```

Python decides:

```text
Majority
Bust probability
Score
Round progression
Game state
```

This separation makes the system much more reliable and gives the project a proper **agent architecture** rather than simply wrapping an LLM in a game.

---

# 🧩 Feature Overview

| Category             | Features                                                          |
| -------------------- | ----------------------------------------------------------------- |
| 🎭 **Agents**        | Five core personas, generated personas, configurable agent counts |
| 🤖 **LLM**           | Local Ollama inference, structured responses, model validation    |
| 🧠 **Memory**        | Bounded round history and contextual agent memory                 |
| 📈 **Adaptation**    | Dynamic risk tolerance based on previous outcomes                 |
| 💬 **Deliberation**  | Two-stage independent voting + group deliberation                 |
| 🔗 **Relationships** | Trust, distrust, respect and dismissal between agents             |
| 🧪 **Simulation**    | Automated multi-agent experiments with configurable parameters    |
| 📊 **Analytics**     | Behavioral statistics and performance metrics                     |
| 🛡️ **Reliability**  | Validation, timeouts, failure-safe round handling                 |
| 🌐 **Interface**     | CLI game + browser-based Tower Votes                              |
| 🧪 **Testing**       | Dedicated pytest test suite                                       |

---

# 🤖 AI System

## Local LLMs with Ollama

Guess Master uses **Ollama** for local model inference.

This means the game can run without sending persona decisions to an external API.

Example configuration:

```env
OLLAMA_HOST=http://localhost:11434
OLLAMA_MODEL=qwen2.5:3b
OLLAMA_TIMEOUT_SECONDS=180
OLLAMA_KEEP_ALIVE=10m
```

The Ollama integration handles:

* Connection validation
* Model availability
* Model warm-up
* Request timeouts
* Keep-alive configuration
* Structured responses
* Response validation

---

# 🎭 Persona System

Personas are represented as structured profiles rather than simple prompt strings.

Each persona can contain:

```text
Identity
Objective
Risk Tolerance
Decision Philosophy
Behavioral Tendencies
Communication Style
Anti-patterns
```

This allows the same underlying LLM to behave as different decision-making agents.

For example:

```text
GAMBLER
High risk tolerance
        ↓
More likely to ADD

CONSERVATIVE
Low risk tolerance
        ↓
More likely to REJECT
```

The persona system is completely separate from the game engine, making new personalities easy to add.

---

# 🧠 Agent Memory

Agents can use information from previously completed rounds.

Memory is intentionally **bounded** to prevent uncontrolled context growth.

A future decision can receive information such as:

```text
Previous Offer: 25
Decision: ADD
Result: SAFE_ADD
Score: 25
```

Importantly, current-round agent decisions remain isolated during normal independent voting.

---

# 📈 Adaptive Agents

Adaptive mode allows agents to modify their effective risk tolerance based on previous outcomes.

```text
          ADD + SAFE
              │
              ▼
      Risk tolerance ↑


           ADD + BUST
              │
              ▼
      Risk tolerance ↓


             REJECT
              │
              ▼
          No change
```

Adaptation is bounded within a defined range.

The original persona profile remains unchanged.

### This is not model training.

No weights are updated and no reinforcement learning occurs.

The system simply modifies the context supplied to the LLM.

Enable it with:

```bash
python main.py --adaptive
```

---

# 💬 Multi-Agent Deliberation

Normal mode:

```text
Offer
 ↓
Independent Votes
 ↓
Majority
```

Deliberation mode:

```text
Offer
 ↓
Independent Votes
 ↓
Shared Deliberation
 ↓
Final Votes
 ↓
Majority
```

Enable with:

```bash
python main.py --deliberate
```

This allows experiments around:

* Consensus
* Group influence
* Minority opinions
* Decision changes
* Groupthink
* Collective risk-taking

Only the **final votes** determine the game outcome.

---

# 🔗 Persona Relationships

Agents can also have relationships with one another.

Supported relationship types include:

```text
TRUSTS
DISTRUSTS
RESPECTS
DISMISSES
```

For example:

```text
Analyst ───── respects ─────► Strategist

Gambler ─── distrusts ──────► Conservative
```

Relationships influence the context agents receive during deliberation.

They do **not** modify:

* Majority calculation
* Bust probability
* Score
* Game rules

This keeps social influence separate from deterministic game mechanics.

Enable with:

```bash
python main.py --deliberate --relationships
```

---

# 👥 Generated Personas

The system can generate additional agents using controlled combinations of behavioral traits.

Generated personas can vary by:

* Risk tolerance
* Objective
* Philosophy
* Communication style
* Behavioral tendencies
* Anti-patterns

This allows the system to move beyond the original five-agent setup.

Agent counts can be configured for simulation experiments while maintaining valid majority voting.

---

# 🧪 Simulation Framework

Guess Master isn't limited to manually playing the game.

It includes an automated simulation layer for running controlled experiments.

Simulation parameters can include:

| Parameter          | Purpose                                    |
| ------------------ | ------------------------------------------ |
| Agent count        | Test different group sizes                 |
| Seed               | Reproduce experiments                      |
| Round limit        | Control simulation length                  |
| Mock / LLM         | Compare deterministic and LLM agents       |
| Deliberation       | Test independent vs social decision-making |
| Adaptation         | Test evolving risk behavior                |
| Generated personas | Create larger populations                  |
| History            | Preserve previous round context            |
| Metrics            | Measure performance and behavior           |

Example:

```bash
python main.py --simulate --mock --agent-count 11 --seed 42
```

This turns Guess Master into a small **multi-agent experimentation platform** rather than only a game.

---

# 📊 Statistics & Analytics

The system records behavioral statistics such as:

* Completed rounds
* Final score
* Final outcome
* Average offer
* ADD count
* REJECT count
* ADD percentage
* REJECT percentage
* Average confidence
* Majority alignment
* ADD decisions before SAFE outcomes
* ADD decisions before BUST outcomes
* Adaptive risk changes

These metrics describe **agent behavior**, rather than assuming there is always one objectively correct decision.

---

# ⚡ Performance Monitoring

Agent inference performance can be tracked using call metrics.

Tracked information includes:

```text
Successful calls
Failed calls
Total latency
Average call latency
Round latency
Agent count
Concurrency configuration
```

This makes it possible to study the cost of increasing the number of agents.

For example:

```text
5 agents
   ↓
11 agents
   ↓
21 agents
   ↓
51 agents
```

---

# 🛡️ Reliability & Failure Handling

LLM applications can fail independently of game logic.

Guess Master handles failures without corrupting the game state.

```text
LLM Failure
     │
     ▼
Round Cancelled
     │
     ▼
State Preserved
     │
     ▼
Player Can Retry
```

The system does **not** silently turn an API failure into an arbitrary AI decision.

Structured outputs are also validated before being consumed by the game engine.

---

# 🌐 Tower Votes

Guess Master includes a browser-based version called:

## Tower Votes

The browser interface turns the game into a visual tower-building experience.

The interface allows players to:

* Enter offers
* Watch AI decisions
* See majority results
* Build their tower
* Track their score
* Play multiple runs
* Compare previous runs

Run the browser version with mock agents:

```bash
python web_app.py --mock
```

Or use Ollama:

```bash
python web_app.py
```

Then open:

```text
http://127.0.0.1:5050
```

---

# 🏗️ Architecture

Guess Master is organized into several independent layers.

```text
┌─────────────────────────────────────────┐
│             USER INTERFACE              │
│                                         │
│        CLI              Web App         │
└────────────────────┬────────────────────┘
                     │
                     ▼
┌─────────────────────────────────────────┐
│              GAME ENGINE                │
│                                         │
│   State • Rules • Voting • History      │
└────────────────────┬────────────────────┘
                     │
                     ▼
┌─────────────────────────────────────────┐
│             AGENT SYSTEM                │
│                                         │
│ Personas • Memory • Adaptation          │
│ Deliberation • Relationships             │
│ Persona Generation                       │
└────────────────────┬────────────────────┘
                     │
                     ▼
┌─────────────────────────────────────────┐
│             LLM LAYER                   │
│                                         │
│             Ollama                      │
└─────────────────────────────────────────┘
```

### Core principle

```text
LLM
 ↓
Decision
 ↓
Validation
 ↓
Game Engine
 ↓
Deterministic Outcome
```

---

# 📁 Project Structure

```text
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
```

---

# 🚀 Getting Started

## Requirements

* Python **3.10+**
* [Ollama](https://ollama.com/)
* A compatible local LLM
* pip

---

## 1. Clone

```bash
git clone https://github.com/Amru501/guess-master.git
cd guess-master
```

---

## 2. Create a Virtual Environment

### Windows

```bash
python -m venv .venv
.venv\Scripts\activate
```

### macOS / Linux

```bash
python3 -m venv .venv
source .venv/bin/activate
```

---

## 3. Install Dependencies

```bash
pip install -r requirements.txt
```

---

## 4. Configure Ollama

Install Ollama and download a model.

Example:

```bash
ollama pull qwen2.5:3b
```

Create `.env` from `.env.example`.

### Windows

```bash
copy .env.example .env
```

### macOS / Linux

```bash
cp .env.example .env
```

Configure:

```env
OLLAMA_HOST=http://localhost:11434
OLLAMA_MODEL=qwen2.5:3b
OLLAMA_TIMEOUT_SECONDS=180
OLLAMA_KEEP_ALIVE=10m
```

---

# ▶️ Running the Game

## Basic Game

```bash
python main.py
```

Uses the configured local LLM.

---

## Mock Mode

```bash
python main.py --mock
```

Runs without Ollama.

Useful for:

* Development
* Testing
* Debugging
* Demonstrations
* Reproducible experiments

---

## Adaptive Mode

```bash
python main.py --adaptive
```

---

## Deliberation

```bash
python main.py --deliberate
```

---

## Deliberation + Relationships

```bash
python main.py --deliberate --relationships
```

---

## Verbose Mode

```bash
python main.py --verbose
```

---

## View History

```bash
python main.py --show-history
```

---

## Save History

```bash
python main.py --history-file game-history.json
```

---

## Save Statistics

```bash
python main.py --stats-file game-stats.json
```

---

## Export Relationship Graph

```bash
python main.py --export-graph persona-graph.json
```

---

# 🧪 Testing

Run the complete test suite:

```bash
pytest
```

Verbose:

```bash
pytest -v
```

The test suite covers:

* Game rules
* Game engine
* Persona profiles
* LLM integration
* History
* Statistics
* Adaptation
* Deliberation
* Relationships
* Simulation
* CLI behavior
* Web application

LLM functionality can be mocked, so tests do not require a live Ollama server.

---

# 🔬 Development Evolution

Guess Master was developed incrementally, with each version introducing another layer of the multi-agent system.

|  Version | Development                              |
| :------: | ---------------------------------------- |
|  **V0**  | Five deterministic personas              |
|  **V1**  | Local Ollama-powered agents              |
| **V1.1** | Reliability and structured LLM responses |
|  **V2**  | Reusable persona profiles                |
|  **V3**  | Bounded memory and history               |
|  **V4**  | Behavioral statistics                    |
|  **V5**  | Adaptive risk tolerance                  |
|  **V6**  | Multi-agent deliberation                 |
|  **V7**  | Persona relationship graph               |
|  **V8**  | Generated personas and simulations       |
|  **Web** | Tower Votes browser interface            |

---

# ⚠️ Limitations

Guess Master is an exploration of multi-agent AI systems, not a claim that each persona represents an independent intelligence.

### Shared Model

Multiple agents may use the same underlying LLM.

Behavioral diversity comes primarily from:

* Persona configuration
* Prompt context
* Memory
* Adaptation
* Relationships

### Deliberation Changes Independence

Independent mode keeps current-round decisions isolated.

Deliberation mode intentionally allows agents to see the group's initial decisions.

### Adaptation Isn't Training

Adaptive behavior changes prompt context rather than model parameters.

No weights are updated during gameplay.

### Generated Agents Aren't Separate Models

Generated personas are different behavioral configurations using the same inference infrastructure.

### Local Inference Has Hardware Costs

Performance depends on:

* CPU
* GPU
* RAM
* Model size
* Quantization
* Number of agents
* Concurrency

---

# 🚧 Future Development

Possible future directions include:

* Persistent long-term agent memory
* Cross-game learning
* Larger-scale simulations
* Experiment dashboards
* Agent behavior visualization
* Alternative voting mechanisms
* Weighted voting
* Agent-specific learning
* Evolving relationship networks
* Improved concurrent inference
* Additional local model backends
* Comparative model evaluation
* Agent tournaments

---

# 🎯 What Guess Master Demonstrates

Guess Master brings together several practical AI engineering concepts in one system:

```text
                  MULTI-AGENT SYSTEM
                         │
        ┌────────────────┼────────────────┐
        ▼                ▼                ▼
     Personas          Memory        Relationships
        │                │                │
        └────────────────┼────────────────┘
                         ▼
                     LLMs
                         │
                         ▼
                  Structured Output
                         │
                         ▼
                  Deterministic Engine
                         │
            ┌────────────┼────────────┐
            ▼            ▼            ▼
        Gameplay     Simulation    Statistics
```

The project demonstrates how LLMs can be integrated into a larger software system while keeping **state, rules, validation, and outcomes deterministic**.

---

# 👨‍💻 Author

**Amru501**

GitHub:

https://github.com/Amru501/guess-master

---

## 📄 License

No license is currently specified for this repository.

If the project is intended to be distributed or used as an open-source project, an appropriate license should be added.
