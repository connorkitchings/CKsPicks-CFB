# cfb_model – College Football Betting System

[![Project Status: Alpha](https://www.repostatus.org/badges/latest/alpha.svg)](https://www.repostatus.org/#alpha)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)

An end-to-end pipeline for ingesting college-football data, engineering predictive features,
training a betting model, and publishing weekly ATS recommendations. The project follows the Vibe
Coding System for observability, reproducibility, and AI-assisted collaboration.

For a deep dive into the methodology and guides, please see our [full documentation site](./docs/index.md).

---

## 🚀 Getting Started

### Prerequisites

- Python 3.12+
- [uv](https://github.com/astral-sh/uv)
  - macOS (Homebrew): `brew install uv`

### Installation

1. **Clone the repository:**

   ```bash
   git clone https://github.com/connorkitchings/cfb_model.git
   cd cfb_model
   ```

2. **Create and activate a virtual environment:**

   ```bash
   uv venv
   source .venv/bin/activate
   ```

3. **Install dependencies:**

```bash
uv sync --extra dev
```

For detailed usage guides (running tests, pipelines, and docs), see the
[full documentation site](./docs/index.md).

---

## 📂 Project Structure

```text
cfb_model/
├── docs/                 # Project documentation (MkDocs)
├── notebooks/            # Jupyter notebooks for exploration and analysis
├── session_logs/         # Chronological development session logs
├── scripts/              # Utility and automation scripts
├── src/
│   └── cfb_model/
│       ├── data/         # Ingestion, storage, aggregations
│       ├── flows/        # Prefect orchestration flows
│       ├── models/       # Modeling code
│       └── utils/        # Shared utilities
├── mkdocs.yml            # Documentation site config
├── prefect.yaml          # Prefect deployments/config
├── pyproject.toml        # Project metadata and dependencies
├── uv.lock               # Resolved dependency lockfile
├── LICENSE
└── README.md             # This file
```

---

## 🤝 Contributing

Contributions are welcome! Please follow the guidelines below:

- All contributions must be submitted via a pull request.
- Please use the [pull request template](./.github/pull_request_template.md).
- For a detailed guide on our review standards, see the [Development Standards & Workflow](./docs/project_org/development_standards.md).

---

## 🗄️ Storage Backend

The project uses a local, partitioned dataset. Both raw and processed data are stored in CSV format
(via `pandas`; `pyarrow` is retained for schema/interop utilities).
Ingestion scripts write idempotently per `entity/year/week/game_id` (for plays) or `entity/year`
(for other entities) and generate `manifest.json` files for validation.
See `docs/cfbd/data_ingestion.md` and `docs/project_org/project_charter.md` for details.

### Aggregations CLI

Run pre-aggregations (reads `CFB_MODEL_DATA_ROOT` from your environment or `.env`):

```bash
python3 scripts/cli.py aggregate preagg --year 2024
```

Byplay-only:

```bash
python3 scripts/cli.py aggregate byplay --year 2024
```

---

## 📞 Contact

Have a question or a suggestion? Please [open an issue](https://github.com/connorkitchings/cfb_model/issues).

---

## 📄 License

This project is licensed under the MIT License. See the [LICENSE](LICENSE) file for details.
