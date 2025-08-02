# Vibe Coding Data Science Template

Welcome to the Vibe Coding Data Science Template! This repository provides a
production-ready, highly automated foundation for data science and machine
learning projects. It is built on the principles of the Vibe Coding System,
emphasizing observability, reproducibility, and efficient AI-assisted
collaboration.

This template is not just another collection of files; it's a **system** designed to accelerate
data science projects by solving common pain points out-of-the-box. It enforces best practices
in a lightweight, automated way so you can focus on building, not boilerplate.

For a deep dive into the methodology and guides, please see our
[full documentation site](./docs/index.md).

---

## 🚀 Getting Started

For a complete guide on setting up your local development environment, please see the
[Getting Started Guide](./docs/getting_started.md).

For detailed usage guides (running tests, docs, pipelines), please see our
[full documentation site](./docs/index.md).

---

## 📂 Project Structure

```text
.vibe-coding-template/
├── .github/              # GitHub Actions workflows and templates
├── data/                 # Raw and processed data (not committed)
├── docs/                 # Simplified project documentation
├── models/               # Trained model artifacts (not committed)
├── notebooks/            # Jupyter notebooks for exploration and analysis
├── reports/              # Generated reports and figures
├── scripts/              # Utility and automation scripts
├── session_logs/         # Chronological development session logs
├── src/                  # Project source code
│   ├── flows/            # Prefect orchestration flows
│   └── utils/            # Shared utility modules
├── .dockerignore         # Files to ignore in Docker builds
├── .gitignore            # Files to ignore in Git
├── .pre-commit-config.yaml # Configuration for pre-commit hooks
├── Dockerfile            # Multi-stage Dockerfile for containerization
├── mkdocs.yml            # Configuration for MkDocs
├── prefect.yaml          # Configuration for Prefect deployments
├── pyproject.toml        # Project metadata and dependencies
└── README.md             # This file
```

---

## 🤝 Contributing

Contributions are welcome! Please follow the guidelines below:

- All contributions must be submitted via a pull request.
- Please use the [pull request template](./.github/pull_request_template.md).
- For a detailed guide on our review standards, see the [Development Standards & Workflow](./docs/development_standards.md).

---

## 📄 License

This project is licensed under the MIT License. See the [LICENSE](LICENSE) file for details.
