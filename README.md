# CKsPicks-CFB – College Football Betting System

[![Project Status: Alpha](https://www.repostatus.org/badges/latest/alpha.svg)](https://www.postatus.org/#alpha)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)

An end-to-end machine learning pipeline for college football betting that predicts point spreads and over/unders, displayed as weekly leans in a Vercel web app.

---

## 🎯 Project Status

**Dual-stack monorepo (Python pipeline + Next.js web app).**

- **ML pipeline** (root): Python 3.12, Hydra, MLflow, CatBoost/XGBoost. Cloud-backed by Cloudflare R2.
- **Web app** (`web/`): Next.js 16 / React 19 / Tailwind v4. Reads from Neon Postgres. Deploys to Vercel.
- **2026 MVP:** Web app showing every FBS game with the model's spread + total lean. Display only — no auth or bet tracking (post-MVP).

For the full data-flow diagram and weekly workflow, see [`docs/ops/weekly_pipeline.md`](./docs/ops/weekly_pipeline.md).

---

## 📚 Documentation

**Start here:**

- **[AGENTS.md](./AGENTS.md)** - Entry point for AI assistants (critical rules, workflows, troubleshooting)
- **[web/README.md](./web/README.md)** - Web app local-dev guide
- **[docs/ops/weekly_pipeline.md](./docs/ops/weekly_pipeline.md)** - How predictions flow from Python → Postgres → Vercel
- **[docs/guide.md](./docs/guide.md)** - Documentation hub for humans
- **[.codex/QUICKSTART.md](./.codex/QUICKSTART.md)** - Python commands reference

**Key documentation:**

- [Feature Catalog](./docs/modeling/features.md) - Feature definitions
- [Betting Policy](./docs/modeling/betting_policy.md) - Unit sizing rules
- [V2 Experimentation Workflow](./docs/process/experimentation_workflow.md) - 4-phase modeling process

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
   git clone https://github.com/connorkitchings/CKsPicks-CFB.git
   cd CKsPicks-CFB
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
CKsPicks-CFB/
├── AGENTS.md              # AI assistant entry point (dual-stack guide)
├── .agent/                # AI assistant workspace
├── .codex/                # Quick reference guides (Python)
├── src/                   # Python source code (pipeline)
│   ├── data/              # Data ingestion
│   ├── features/          # Feature engineering
│   ├── models/            # ML models
│   └── utils/             # Utilities
├── scripts/
│   └── pipeline/
│       ├── generate_weekly_bets.py    # Predictions → CSV
│       ├── publish_to_db.py           # CSV → Neon Postgres
│       ├── score_to_db.py             # Results → Postgres + stats
│       └── publish_picks.py           # Email publisher (legacy channel)
├── conf/                  # Hydra configuration
├── docs/                  # Documentation
├── tests/                 # Python unit tests
├── web/                   # Next.js app (Vercel deploy target)
├── Logos/                 # Team logos (synced into web/ at build)
└── session_logs/          # Development logs
```

For detailed file locations, see [.codex/MAP.md](./.codex/MAP.md). For the web app, see [web/README.md](./web/README.md).

---

## 🧪 Quick Commands

### Python (pipeline)

```bash
# Run tests
make test                       # or: PYTHONPATH=.:src uv run pytest tests/ -q

# Format + lint
make format && make lint

# Train
PYTHONPATH=. uv run python -m cks_picks_cfb.train

# Generate predictions then publish to Postgres
make db-publish YEAR=2026 WEEK=1
```

### Web app

```bash
make web-dev                    # cd web && npm run dev
make web-build                  # cd web && npm run build (also syncs logos)
make web-typecheck
```

### MLflow Tracking

```bash
MLFLOW_PORT=5050 docker compose -f docker/mlops/docker-compose.yml up mlflow
# Access at http://localhost:5050
```

For complete command references, see [.codex/QUICKSTART.md](./.codex/QUICKSTART.md) (Python) and [web/README.md](./web/README.md) (Next.js).

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

_Last Updated: 2026-07-06_
_2026 reorg: Python pipeline + Next.js web app (Vercel) + Neon Postgres_
