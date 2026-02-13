# cfb_model – College Football Betting System

[![Project Status: Alpha](https://www.repostatus.org/badges/latest/alpha.svg)](https://www.repostatus.org/#alpha)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)

An end-to-end machine learning pipeline for college football betting that predicts point spreads and over/unders using opponent-adjusted features and rigorous experimentation workflows.

---

## 🎯 Project Status

**V2 Modeling Workflow:** 🛑 **PAUSED** for infrastructure refactoring (as of Feb 2026)

The project is currently undergoing infrastructure modernization:
- Migrating from external drive to cloud storage (Cloudflare R2)
- Modernizing AI assistant tooling (AGENTS.md, .agent/, .codex/)
- Consolidating documentation structure

**Modeling will resume after refactoring completes** (estimated: Phase 6 completion)

For current project status, see [`REFACTORING_PLAN.md`](./REFACTORING_PLAN.md)

---

## 📚 Documentation

**Start here:**
- **[AGENTS.md](./AGENTS.md)** - Entry point for AI assistants (critical rules, workflows, troubleshooting)
- **[docs/guide.md](./docs/guide.md)** - Documentation hub for humans
- **[.codex/QUICKSTART.md](./.codex/QUICKSTART.md)** - Essential commands reference

**Key documentation:**
- [V2 Experimentation Workflow](./docs/process/experimentation_workflow.md) - 4-phase modeling process (paused)
- [12-Week Implementation Plan](./docs/process/12_week_implementation_plan.md) - Roadmap
- [Promotion Framework](./docs/process/promotion_framework.md) - 5-gate promotion system
- [Feature Catalog](./docs/modeling/features.md) - Feature definitions
- [Betting Policy](./docs/modeling/betting_policy.md) - Unit sizing rules
- [Weekly Pipeline](./docs/ops/weekly_pipeline.md) - Production workflow

---

## 🚀 Getting Started

### Prerequisites

- **Python 3.12+**
- **[uv](https://github.com/astral-sh/uv)** - Fast Python package installer
- **[Docker](https://www.docker.com/)** - For MLflow tracking UI
- **[CollegeFootballData.com](https://collegefootballdata.com) API key**

### Installation

1. **Clone the repository:**

   ```bash
   git clone https://github.com/connorkitchings/cfb_model.git
   cd cfb_model
   ```

2. **Install dependencies:**

   ```bash
   uv sync --extra dev
   ```

3. **Activate virtual environment:**

   ```bash
   source .venv/bin/activate  # macOS/Linux
   # or
   .venv\Scripts\Activate.ps1  # Windows PowerShell
   ```

4. **Configure environment variables:**

   Create `.env` file:

   ```bash
   # Required: CollegeFootballData.com API key
   CFBD_API_KEY=your_api_key_here

   # Required: Data storage location
   CFB_MODEL_DATA_ROOT=/path/to/your/data/directory
   # Note: Currently external drive, migrating to cloud storage in Phase 2
   ```

5. **Run health checks:**

   ```bash
   # Format and lint
   uv run ruff format . && uv run ruff check .

   # Run tests
   uv run pytest -q
   ```

   If these pass, you're ready!

---

## 🏗️ Project Structure

```
cfb_model/
├── AGENTS.md              # AI assistant entry point
├── .agent/                # AI assistant workspace
├── .codex/                # Quick reference guides
├── src/                   # Source code
│   ├── data/              # Data ingestion
│   ├── features/          # Feature engineering
│   ├── models/            # ML models
│   └── utils/             # Utilities
├── scripts/               # CLI scripts
│   ├── pipeline/          # Production pipeline
│   ├── analysis/          # Analysis tools
│   └── experiments/       # Research scripts
├── conf/                  # Hydra configuration
├── docs/                  # Documentation
├── tests/                 # Unit tests
├── session_logs/          # Development logs
└── artifacts/             # Outputs (git-ignored)
```

For detailed file locations, see [.codex/MAP.md](./.codex/MAP.md)

---

## 🧪 Quick Commands

### Testing

```bash
# Run all tests
uv run pytest

# Run quietly
uv run pytest -q

# Format and lint
uv run ruff format . && uv run ruff check .
```

### Model Training

```bash
# Basic training
PYTHONPATH=. uv run python src/models/train_model.py

# Run experiment
PYTHONPATH=. uv run python src/models/train_model.py experiment=spread_catboost_baseline_v1

# Hyperparameter optimization
PYTHONPATH=. uv run python src/models/train_model.py mode=optimize
```

### MLflow Tracking

```bash
# Start MLflow UI
MLFLOW_PORT=5050 docker compose -f docker/mlops/docker-compose.yml up mlflow

# Access at http://localhost:5050
```

For complete command reference, see [.codex/QUICKSTART.md](./.codex/QUICKSTART.md)

---

## 🤖 AI-Assisted Development

This project is designed for AI-assisted development with clear guardrails:

**For AI assistants:**
1. Read [AGENTS.md](./AGENTS.md) first - Contains critical rules
2. Verify data root configuration before any data operations
3. Review recent session logs (`session_logs/` last 3 days)
4. Propose plan before implementing
5. Create session log at end of work

**For humans:**
- AI assistants can help with code, but humans control git operations
- All commits must be manually approved
- Betting policy cannot be modified by AI

See [AGENTS.md](./AGENTS.md) for complete guidelines.

---

## 🧑‍💻 Contributing

Contributions are welcome! Before submitting a PR:

1. Read [AGENTS.md](./AGENTS.md) for project conventions
2. Run quality checks: `uv run ruff format . && uv run ruff check . && uv run pytest -q`
3. Create session log in `session_logs/YYYY-MM-DD/NN.md`
4. Update relevant documentation

For major changes, open an issue first to discuss approach.

---

## 📞 Contact & Support

- **Issues:** [GitHub Issues](https://github.com/connorkitchings/cfb_model/issues)
- **Discussions:** [GitHub Discussions](https://github.com/connorkitchings/cfb_model/discussions)

---

## 📄 License

This project is licensed under the MIT License - see the [LICENSE](./LICENSE) file for details.

---

## ⚠️ Disclaimer

This is a research and educational project. It does not guarantee profit or future performance. You are responsible for how you use any outputs. Sports betting involves risk - never bet more than you can afford to lose.

---

_Last Updated: 2026-02-13_
_Currently undergoing Phase 3 refactoring - see REFACTORING_PLAN.md_
