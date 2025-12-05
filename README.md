# cfb_model – College Football Betting System

[![Project Status: Alpha](https://www.repostatus.org/badges/latest/alpha.svg)](https://www.repostatus.org/#alpha)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)

An end-to-end pipeline for ingesting college-football data, engineering opponent-adjusted features,
training models for spread and total edges, and publishing weekly ATS recommendations.

The project follows the **Vibe Coding** conventions for observability, reproducibility, and
AI-assisted collaboration. It is designed so that humans and AI agents can safely iterate on the
codebase, keep documentation in sync, and never lose critical experiment history.

For a deeper dive into methodology and project docs, see:

- **[📖 Documentation Guide](./docs/guide.md)** — Single source of truth for all project documentation
- [AI Assistant Protocols](./CLAUDE.md) — Session management and AI collaboration guidelines

### Quick Links

- [Weekly Pipeline](./docs/ops/weekly_pipeline.md) — Production workflow
- [Modeling Baseline](./docs/modeling/baseline.md) — Current models and architecture
- [Feature Catalog](./docs/modeling/features.md) — Feature engineering reference
- [ML Workflow](./docs/process/ml_workflow.md) — Train/Test/Deploy standards
- [Decision Log](./docs/decisions/decision_log.md) — Major decisions and rationale

> **Note**: The repository was reorganized on 2025-12-04. All documentation is now accessible from [docs/guide.md](./docs/guide.md).

---

## 🚀 Getting Started

### Prerequisites

- Python 3.12+
- [uv](https://github.com/astral-sh/uv) for env and packaging
- [Docker](https://www.docker.com/) for local experiment tracking and services
- A valid [CollegeFootballData.com](https://collegefootballdata.com) API key

### Installation

1. **Clone the repository**

   ```bash
   git clone https://github.com/connorkitchings/cfb_model.git
   cd cfb_model
   ```

2. **Create and sync the virtual environment**

   ```bash
   uv sync --extra dev
   ```

   This installs runtime and dev dependencies defined in `pyproject.toml` into a `.venv/` managed by
   `uv`.

3. **Activate the environment**

   On macOS/Linux:

   ```bash
   source .venv/bin/activate
   ```

   On Windows (PowerShell):

   ```powershell
   .venv\Scripts\Activate.ps1
   ```

4. **Configure environment variables**

   Copy the example environment file if present and edit it:

   ```bash
   cp .env.example .env
   ```

   At minimum, set:

   - `CFBD_API_KEY` – your collegefootballdata.com API key
   - `CFB_MODEL_DATA_ROOT` – absolute path to your local data directory, for example:

     ```bash
     CFB_MODEL_DATA_ROOT=/Users/<you>/cfb_model_data
     ```

   Other optional settings are documented in `development_standards.md` and the relevant docs.

### Quick Smoke Tests

After installation and env configuration, run quick checks:

```bash
uv run ruff format . && uv run ruff check .
uv run pytest -q
```

If these pass, you are ready to run the pipelines.

---

## 🧱 Project Layout

High-level directory structure (subject to change as the project evolves):

```text
.
├── src/                    # Library code (features, models, pipelines, utilities)
│   ├── config/             # Configuration (paths, experiments, champion models)
│   ├── data/               # Data access and ingestion
│   ├── features/           # Feature engineering pipelines
│   ├── models/             # Training, evaluation, and prediction logic
│   ├── inference/          # Prediction and reporting (predict.py, report.py)
│   ├── training/           # Training workflows (train.py)
│   └── utils/              # Utilities (MLflow, local storage, etc.)
├── scripts/                # CLI entrypoints and organized utilities
│   ├── pipeline/           # Production pipeline scripts
│   ├── analysis/           # Analysis and validation scripts
│   ├── experiments/        # Research and optimization scripts
│   ├── debug/              # Debugging tools
│   ├── utils/              # Helper scripts
│   └── cli.py              # Main CLI entry point
├── docs/                   # Project documentation (charter, roadmap, guides, etc.)
├── session_logs/           # Chronological development session logs
├── artifacts/              # Consolidated outputs (git-ignored)
│   ├── mlruns/             # MLflow tracking data
│   ├── outputs/            # Generated reports and predictions
│   └── models/             # Saved model artifacts
├── tests/                  # Unit and integration tests
├── AI_GUIDE.md             # Front door instructions for AI agents and humans
├── AGENTS.md               # Agent roles, handoffs, and guardrails
├── pyproject.toml          # Project metadata, dependencies, and tooling config
└── README.md               # You are here
```

For more detail on the docs structure and knowledge base, see `docs/kb_overview.md`.

---

## 📊 Data, Features, and Pipelines

The project builds season-long data products and weekly modeling inputs from public sources such as
collegefootballdata.com.

Key documents:

- `docs/weekly_pipeline.md` – describes the weekly end-to-end run
- `docs/feature_engineering_plan.md` and `docs/advanced_feature_engineering_overview.md`
- `docs/feature_catalog.md` – authoritative mapping from feature families to concrete columns
- `docs/points_for_model.md` – specification for spread/total modeling
- `docs/data_partition_cleanup_summary.md` – decisions about data partitioning and filtering

### Core Flow (High Level)

1. **Raw ingest**
   Fetch play-by-play, drives, games, and team data and normalize it into local tables under
   `CFB_MODEL_DATA_ROOT`.

2. **Aggregation and feature engineering**
   Build drive-level, game-level, and season-level stats, including opponent-adjusted features and
   rolling windows. The goal is to create rich **team-week** feature rows with clearly named
   offensive and defensive columns.

3. **Points-for modeling**
   Train models that predict points scored and points allowed for each team in each matchup, then
   transform these into edges vs. market spreads and totals. Details live in `docs/points_for_model.md`.

4. **Bet selection and sizing**
   Convert model edges into candidate bets and stake sizes subject to the rules in
   `docs/betting_policy.md`. Policy is a hard constraint; models may propose edges, but the policy
   decides which bets, if any, are valid.

5. **Publishing**
   Save weekly artifacts (predictions, bet slates, diagnostics) under `artifacts/` and, when
   appropriate, export cleaned outputs for websites or dashboards.

### Future Direction: Probabilistic Power Ratings

In addition to the current points-for modeling, the project has a planned future track for
**probabilistic power ratings**:

- Maintain team-level ratings (overall, offense, defense, pace) as **distributions**, not just point
  estimates.
- Use these ratings as:

  - A more interpretable backbone for spread and total projections
  - A way to compare team strength across weeks and seasons on a schedule-adjusted basis
  - A potential foundation for moneyline or derivative market modeling

This work is in a **research-only** phase and will be fully specified in its own PRD before
implementation begins.

---

## 🧪 Modeling, Experiments, and MLOps

The project uses **Hydra** for configuration management, **Optuna** for hyperparameter optimization, and **MLflow** for experiment tracking and model registry.

### Quick Start

**Train a model:**

```bash
PYTHONPATH=. uv run python src/models/train_model.py
```

**Run hyperparameter optimization:**

```bash
PYTHONPATH=. uv run python src/models/train_model.py mode=optimize
```

**Run a pre-configured experiment:**

```bash
PYTHONPATH=. uv run python src/models/train_model.py experiment=spread_catboost_baseline_v1
```

### Core Principles

- **Hydra-first:** All experiments are launched via Hydra configs in `conf/experiment/`
- **Reproducibility:** Every model gets a standardized ID encoding model type, features, tuning, and data version
- **Tracking:** MLflow automatically logs all runs, metrics, and model artifacts
- **Registry:** Models are registered to MLflow with proper versioning and staging (Development → Staging → Production)

For detailed instructions, see [MLOps and Experimentation Guide](docs/guides/mlops_experimentation.md).

---

Each experiment produces a unique run under `artifacts/` and/or the tracking service. Runs are
never overwritten.

- **Rich metadata:**
  Each run logs, at minimum:

  - `run_id`
  - `git_sha`
  - `hydra_config_path`
  - `dataset_snapshot_id`
  - `feature_set_id`
  - `model_name`
  - `seed`
  - Evaluation metrics

- **Feature-set discipline:**
  Changes to feature selection or transformations must update a `feature_set_id` and be reflected in
  the feature catalog and decision log when they affect “production” modeling.

- **Local-only tracking by default:**
  Long-running services (tracking UIs, dashboards) are expected to run via Docker locally and are
  not tied to any external SaaS tools by default.

  To review MLflow runs or any future dashboards, start the Dockerized stack from the repo root:

  ```bash
  MLFLOW_PORT=5050 docker compose -f docker/mlops/docker-compose.yml up mlflow
  ```

  Override `MLFLOW_PORT` if `5000` is in use. The tracker serves at
  `http://localhost:${MLFLOW_PORT:-5000}` backed by `artifacts/mlruns/`, ensuring all experiment
  reviews stay inside the repo-local artifacts tree.

For concrete run commands and config patterns, see `docs/points_for_model.md`,
`docs/advanced_feature_engineering_overview.md`, `docs/weekly_pipeline.md`, and
`docs/operations/mlflow_mcp.md` (MCP hookup for MLflow dashboards).

### Metric Definitions

To avoid ambiguity, this project uses the following standard definitions:

- **Straight-Up (SU) Win Accuracy:** The percentage of games where the model correctly predicted the winning team, regardless of the betting line.
- **Against-The-Spread (ATS) Accuracy:** The percentage of games where the model correctly predicted the winner after adjusting for the spread (e.g., Home Score + Spread > Away Score).
- **Betting Win Rate:** The ATS accuracy specifically for the subset of games where the model flagged a "betable" edge (i.e., edge > threshold).

---

## 🎲 Betting Policy and Safety

This repository includes logic for generating suggested bets based on model outputs. It does **not**
guarantee profit or future performance.

Key points:

- The canonical policy lives in `docs/betting_policy.md`.
- Any bet suggestions produced by code must:

  - Obey bankroll, unit sizing, and exposure rules.
  - Respect minimum sample sizes and stability checks.

- The **Bets & Policy Checker** agent (described in `AGENTS.md`) is responsible for applying this
  policy. It cannot change the policy, only enforce it.

You are responsible for how (and whether) you use any outputs in real-world contexts. Treat this as
a research and tooling project first.

---

## 🤖 AI and Agent Workflows

This project is explicitly designed to be used with AI coding tools (Gemini, ChatGPT, LM Studio, and
others) under tight guardrails.

Core docs:

- `AI_GUIDE.md` – “front door” for agents and humans; defines read order and expectations.
- `AGENTS.md` – defines agent roles (Navigator, Researcher, DataOps, Feature Engineer, Modeler,
  Bets Checker, Docs Scribe, Guardian), handoffs, and session rules.
- `docs/ai_session_templates.md` – kickoff and closing templates for AI-assisted sessions.
- `docs/development_standards.md` – expectations for style, testing, and documentation.

High-level rules:

- Every AI session starts with a **planning prompt**, not immediate code changes.
- Every session that changes code or docs ends with:

  - A `session_logs/YYYY-MM-DD/NN.md` entry.
  - A suggestion to run tests and checks.
  - A reminder to commit and push changes.

Humans remain in control of git operations, policy changes, and any real-world betting decisions.

---

## 🧑‍💻 Contributing

Contributions (issues, PRs, discussion) are welcome, especially on:

- Data quality and ingestion improvements
- New feature engineering ideas and diagnostics
- Model architectures and evaluation criteria
- MLOps, Hydra configs, and experiment management
- Documentation clarity and examples

Before opening a PR:

1. Read `docs/development_standards.md`.

2. Run:

   ```bash
   uv run ruff format . && uv run ruff check .
   uv run pytest -q
   ```

3. Update documentation (README, points-for model, feature catalog, decision log) as needed.

For major changes (e.g., new model families, power-rating frameworks), open an issue or draft PR
first to discuss design and impact.

---

## 📞 Contact

Have a question or a suggestion? Please [open an issue](https://github.com/connorkitchings/cfb_model/issues).

---

## 📄 License

This project is licensed under the MIT License. See the [LICENSE](LICENSE) file for details.
