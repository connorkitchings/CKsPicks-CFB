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
   uv sync
   ```

For detailed usage guides (running tests, pipelines, and docs), see the
[full documentation site](./docs/index.md).

---

## 📂 Project Structure

<details>
<summary>Click to expand</summary>

```text
cfb_model/
├── .github/              # GitHub Actions workflows and templates
├── data/                 # Raw and processed data (not committed)
├── docs/                 # Simplified project documentation
├── models/               # Trained model artifacts (not committed)
├── notebooks/            # Jupyter notebooks for exploration and analysis
├── reports/              # Generated reports and figures
├── scripts/              # Utility and automation scripts
├── session_logs/         # Chronological development session logs
├── src/                  # Project source code
│   ├── cfb_model/        # Project source code
│       ├── data/         # Raw and processed data scripts
│       ├── flows/        # Prefect orchestration flows
│       ├── models/       # Trained model artifacts (not committed)
│       ├── utils/        # Shared utility modules
├── .dockerignore         # Files to ignore in Docker builds
├── .gitignore            # Files to ignore in Git
├── Dockerfile            # Multi-stage Dockerfile for containerization
├── mkdocs.yml            # Configuration for MkDocs
├── prefect.yaml          # Configuration for Prefect deployments
├── pyproject.toml        # Project metadata and dependencies
└── README.md             # This file
```

</details>

---

## 🤝 Contributing

Contributions are welcome! Please follow the guidelines below:

- All contributions must be submitted via a pull request.
- Please use the [pull request template](./.github/pull_request_template.md).
- For a detailed guide on our review standards, see the [Development Standards & Workflow]
  (./docs/project_org/development_standards.md).

---

## 🗄️ Storage Backend

The project uses a local, partitioned Parquet dataset (via `pyarrow`) instead of a cloud database.
Ingestion scripts write idempotently per `entity/year` and generate `manifest.json` files for
validation. See `docs/cfbd/data_ingestion.md` and `docs/project_org/project_charter.md` for details.

---

## 📞 Contact

Have a question or a suggestion? Please [open an issue](https://github.com/connorkitchings/cfb_model/issues).

---

## 📄 License

This project is licensed under the MIT License. See the [LICENSE](LICENSE) file for details.
