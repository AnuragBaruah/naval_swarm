# SWARM Navigation and Task Allocation Simulator (NAV_SWARM30)

This repository contains a decentralized multi-agent swarm simulation framework used to evaluate task allocation, communication efficiency, convergence, and robustness under constraints such as limited bandwidth, packet loss, agent failures, and heterogeneous capabilities.

The system follows a **fully distributed execution model**:
- No central coordinator
- No shared global state
- Agents act only on local state and received messages

---

## 1. File and Folder Structure

```
C:.
|   baseline_results.csv
|   my_results_cold_start_mode.csv
|   my_results_warm_start_mode.csv
|   README.md
|   run_all.py
|
\---nav_swarm30
    |   evaluator.py
    |   visualiser_evaluator.py
    |
    +---baselines
    |       greedy_cbba.py
    |
    +---images
    |       backgound.png
    |       crown.png
    |       dead.png
    |       skull.png
    |
    +---scenarios
    |       S1.json
    |       S2.json
    |       S3.json
    |       S4.json
    |       S5.json
    |       S6.json
    |       S7.json
    |
    +---teams
    |   |   team_BF30ED.py
    |   |
    |   \---__pycache__
    |           team_BF30ED.cpython-312.pyc
    |           team_BF30ED.cpython-313.pyc
    |
    \---__pycache__
            evaluator.cpython-312.pyc
```
---

## Design Features

### Decentralized Capability Inference
The framework implements **execution-based capability learning** that operates identically across both cold-start and warm-start modes. This ensures consistency while supporting different initialization strategies.

### Unified Runtime Logic
- No conditional logic changes between capability modes
- Same task classification, decision-making, and allocation mechanisms
- Capability awareness affects only initial agent state, not control flow

---

## 2. Technical Description of Each File

### Root Directory

#### `run_all.py`

Convenience script to run a given team implementation across **all benchmark scenarios (S1–S7)**.

- Dynamically loads `evaluator.py`
- Executes simulations sequentially
- Aggregates results into a CSV file
- Computes average score

---

#### `baseline_results.csv`

Precomputed benchmark results from baseline agents (e.g., greedy CBBA).

---

#### `my_results_cold_start_mode.csv`

Results generated when agents start **without prior capability knowledge**.

---

#### `my_results_warm_start_mode.csv`

Results generated when agents start **with preloaded capability knowledge**.

---

### `nav_swarm30/`

#### `evaluator.py`

Core **headless simulation engine**.

**Responsibilities:**
- Initializes agents and tasks from scenario JSON
- Simulates motion, communication, failures, and task servicing
- Enforces communication bandwidth and packet loss
- Tracks convergence, leader election, distance traveled, and bytes used
- Computes final normalized score

**Used for:**
- Batch evaluation
- Benchmarking
- CSV result generation

---

#### `visualiser_evaluator.py`

Extension of `evaluator.py` with **real-time Pygame visualization**.

**Additional features:**
- Agent motion rendering with direction arrows
- Task visualization with deadlines and capability labels
- Leader visualization (crown icon)
- Agent failure visualization (skull icon)
- Pause/resume support via keyboard

**Used for:**
- Debugging agent behavior
- Demonstrations
- Qualitative analysis

---

### `nav_swarm30/baselines/`

#### `greedy_cbba.py`

Baseline agent implementing a **greedy Consensus-Based Bundle Algorithm (CBBA)**-style policy.

**Used as:**
- Performance baseline
- Comparison reference

---

### `nav_swarm30/teams/`

#### `team_BF30ED.py`

Custom team agent implementation.

**Key features:**
- Fully decentralized task claiming and release
- Leader election via local bidding
- Capability discovery via exploration
- Safeguards against task starvation
- Robust handling of packet loss
- Dynamic queue reordering based on cost and deadlines
- 

This file defines the mandatory `Agent` class with a `step()` function.

---

### `nav_swarm30/scenarios/`

#### `S1.json` – `S7.json`

Scenario definitions.

Each scenario specifies:
- World bounds
- Number of agents
- Agent speed
- Communication limits (kbps, packet loss)
- Task locations, deadlines, values, and service times
- Capability requirements
- Failure injection rules
- Leader election requirements

---

### `nav_swarm30/images/`

Assets used only by the visualizer:
- Background
- Leader crown
- Agent death markers

---

## 3. Capability Awareness Modes

The framework supports two initialization regimes for agent capability knowledge:

**Cold-Start Mode** (`pre_set_capability_mode = False`)
- Agents begin with no prior knowledge of their own or others' capabilities
- Capability information is learned exclusively through task execution outcomes
- Tasks with unknown capability requirements are treated as exploratory candidates
- Capability discovery is incremental during operation

**Warm-Start Mode** (`pre_set_capability_mode = True`)
- Agents are initialized with prior capability knowledge from the scenario
- Each agent knows its own true capabilities and inferred non-capabilities of others
- Tasks can be immediately classified as executable or non-executable
- Same execution-based update mechanism remains active

**Key Design Principle:** Both modes use identical control logic, decision-making mechanisms, and task allocation algorithms. The capability awareness mode affects only the initial belief state, not runtime execution paths.

---

## Configuration

### Global Variables

#### `pre_set_capability_mode`
Located in: `nav_swarm30/teams/team_BF30ED.py`

- `True`: Warm-start mode (agents know capabilities upfront)
- `False`: Cold-start mode (agents learn capabilities through execution)

This flag is evaluated only during agent construction and does not alter runtime logic.

---

## 4. How to Run

### 4.1 Run All Scenarios (Headless Evaluation)

From the root directory:

```bash
python run_all.py --team nav_swarm30/teams/team_BF30ED.py --out results.csv
```

### 4.2 Comparing Cold-Start vs Warm-Start Results

Generate results for both modes:

**Cold-start: agents learn capabilities through execution**
```bash
python run_all.py --team nav_swarm30/teams/team_BF30ED.py --out results_cold_start.csv
```
**Warm-start: agents initialized with capability knowledge**
```bash
python run_all.py --team nav_swarm30/teams/team_BF30ED.py --out results_warm_start.csv
```

### 4.3 Run a Single Scenario (Headless Evaluation)

From the root directory:

```bash
python nav_swarm30/evaluator.py \
  --scenario nav_swarm30/scenarios/S3.json \
  --team nav_swarm30/teams/team_BF30ED.py \
  --log summary.json
```

### 4.4 Run with Visualisation (Pygame)

```bash
python nav_swarm30/visualiser_evaluator.py \
  --scenario nav_swarm30/scenarios/S3.json \
  --team nav_swarm30/teams/team_BF30ED.py
```

**Keyboard controls:**
- `SPACE`: Pause/Resume
- `ESC`: Exit

---

## 5. Dependencies

### Required Python Version

Python 3.8+

### Required Libraries

Install via pip:

```bash
pip install pygame
```
