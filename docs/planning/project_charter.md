# Project Charter

This document defines the project goals, scope, and technical context for the **cfb_model** project.
It is derived from the [Initial Session Prompt](../process/first_prompt.md) and will be updated
as the project evolves.

> 📚 For a high-level entry point and links to all documentation, see the project README on GitHub
> or the docs home page.

## Project Overview

**Project Name:** cfb_model

**Project Vision:** To develop a college football betting system that predicts point spreads and
over/unders for FBS games using historical play-by-play data, providing weekly betting
recommendations through a web interface.

**Technical Goal:** Build an automated data pipeline and regression model to generate and display
weekly betting picks with a win rate consistently exceeding the 52.4% break-even threshold.

**Repository:** [https://github.com/connorkitchings/cfb_model.git](https://github.com/connorkitchings/cfb_model.git)

## Users & User Stories

### Primary Persona

**Target User:** A data-savvy sports bettor who wants to move beyond simple heuristics and use
quantitative analysis to find an edge against sportsbook lines.

- **Role:** Analytical Sports Bettor
- **Pain Points:** Manual data collection is time-consuming; it's difficult to systematically
  identify value across dozens of games; most public analysis lacks statistical rigor.
- **Goals:** Access automated, data-driven betting recommendations; understand the key factors
  driving each prediction; save time and improve betting ROI.

### Core User Stories

**Story 1:** As an analytical sports bettor, I want to view weekly, model-driven spread predictions
for all FBS games so that I can quickly identify bets where the model's prediction has a significant
edge over the consensus line.

- Priority: Must-have

**Story 2:** As an analytical sports bettor, I want to see the top 3 statistical reasons (SHAP
features) for each recommendation so that I can understand the model's logic and bet with greater
confidence.

- Priority: Should-have

**Story 3:** As an analytical sports bettor, I want a web interface that clearly shows the model's
edge, implied win probability, and recommended stake size so that I can easily decide which games
to bet.

- Priority: Must-have

**Story 4:** As the project owner, I want a fully automated weekly pipeline that ingests data,
trains models, and publishes outputs with minimal manual intervention so that I can focus on
improving features and models.

- Priority: Must-have

## Goals & Non-Goals

### Goals

1. **Weekly Picks:** Generate weekly spread and totals predictions for FBS games, with edge
   calculations against consensus lines.
2. **Transparency:** Provide clear explanations of why the model likes a given side, including key
   features and uncertainty measures.
3. **Automation:** Minimize manual work by automating data ingestion, preprocessing, model training,
   evaluation, and prediction generation.
4. **Reproducibility:** Ensure all data and model steps are versioned, testable, and reproducible
   across machines.
5. **MLOps Discipline:** Use Hydra-driven, Docker-backed experiment tracking so that no experiments
   are lost when parameters or feature sets change.

### Non-Goals (Initial Phases)

- Real-time in-game betting or live line tracking.
- Support for non-FBS divisions.
- Full-blown user management, authentication flows, or multi-tenant accounts (beyond a simple
  password gate for personal use).

## Scope

### In Scope

- Ingesting historical play-by-play and game data via the CollegeFootballData.com API.
- Building a structured local dataset of plays, drives, games, teams, and team-week summaries.
- Engineering opponent-adjusted features at the team-week level.
- Training regression models to predict points scored and allowed, and deriving spread and total
  predictions from those.
- Implementing a basic betting policy (stake sizing, exposure limits) and enforcing it in
  recommendation logic.
- Providing a password-protected Streamlit-based web UI for viewing weekly recommendations.

### Out of Scope (Initial)

- Automated integration with sportsbooks or betting APIs.
- Real-time price/line shopping across multiple books.
- Complex portfolio-level optimization (Kelly across multiple correlated bets).

## Product Scope

### Functional Scope

The system will:

1. Use a weekly, semi-automated run to ingest and update data from the
   CollegeFootballData.com API for the 2014-2024 seasons (excluding 2020).
2. Engineer team-week features (offensive, defensive, situational) including opponent-adjusted
   variants.
3. Train models that predict points scored and allowed for each team in upcoming games.
4. Convert model outputs to spreads, totals, and edges vs. consensus lines.
5. Apply a betting policy to decide which games to recommend and at what stake.
6. Display recommendations and their explanations in a simple web UI.

### Must-Have (MVP)

**Feature A:** Automated Data Pipeline & Database

- User Story: Story 1
- User Impact: High

**Feature B:** Weekly Prediction Web Interface

- User Story: Story 1, Story 2
- User Impact: High

### Should-Have (Post-MVP)

**Feature C:** Over/Under (Totals) Betting Model

- User Story: (To be defined)

### Future Direction: Probabilistic Power Ratings (Research Phase)

We intend to extend the system from point/spread/total predictions to **probabilistic power ratings**:

- **Goal:** Maintain team-level ratings (overall, offense, defense, pace) that represent full
  **distributions** over team strength, not just point estimates.
- **Usage:** Power ratings will be used as:

  - An intermediate layer for spread/total projections,
  - A unified lens for comparing teams across weeks and seasons,
  - A potential foundation for moneyline/derivative markets.

- **Status:** **Research-only for now.** We will:

  - Survey existing power-rating methodologies (Elo, Bayesian hierarchical, state-space models),
  - Define how ratings interact with the existing points-for model and opponent-adjusted features,
  - Draft a dedicated PRD before any implementation begins.

### Out of Scope

- **Feature Scope (MVP):** Both raw and processed data are stored in CSV format with a simplified
  partitioning scheme (year/week/game_id for plays, year for other entities).
  Includes opponent-adjusted features per [LOG:2025-08-12]; see
  `docs/project_org/feature_catalog.md` and `docs/decisions/decision_log.md`.
- Advanced ML models (e.g., XGBoost, RandomForest) are deferred post-MVP.
- Real-time line movement analysis.
- Integration of non-play-by-play data (e.g., weather, injuries).

## Architecture

### High-Level Summary

The MVP uses a manual weekly pipeline executed mid-week. A flow ingests play-by-play data from the
CollegeFootballData.com API, processes it, and writes partitioned local CSV datasets for both raw
and processed layers (via a storage backend abstraction). A linear regression model is then retrained
on the latest data. Predictions for the upcoming week are generated and saved alongside the dataset.
A Streamlit web application provides a password-protected interface to display these recommendations.

### System Diagram

```mermaid
graph TD
    A[Manual Trigger (Wed 12 ET)] -- Runs --> B(Prefect Flow)
    B -- Fetches --> C{CollegeFootballData API}
    C -- Returns --> D[(Raw Data Storage)]
    B -- Writes --> E[(Processed / Feature Store)]
    B -- Trains --> F[(Model Artifact)]
    F -- Generates --> G[(Weekly Predictions)]
    G -- Served to --> H[Streamlit Web App]
    H -- Viewed by --> I[User]
```

### Folder Structure

- `/src`: Contains the main source code for the project
- `/docs`: Contains all project documentation, including planning, guides, and logs
- `/notebooks`: Contains Jupyter notebooks for experimentation and analysis
- `/artifacts`

  - `/artifacts/mlruns`: Contains MLflow experiment tracking data (via a Dockerized MLflow stack; canonical run metadata lives here)
  - other run-specific outputs (diagnostics, plots, cached predictions) stored in dated subdirectories

- `/data`: Contains raw, interim, and processed data (not versioned by Git)
- `/tests`: Contains all unit, integration, and functional tests

## Technology Stack

| Category             | Technology                    | Version | Notes                                                  |
| -------------------- | ----------------------------- | ------- | ------------------------------------------------------ |
| Package Management   | uv                            | latest  | High-performance Python package manager and resolver   |
| Core Language        | Python                        | 3.12+   | Primary programming language                           |
| Linting & Formatting | Ruff                          | latest  | Combines linting, formatting, and import sorting       |
| Config & Experiments | Hydra                         | latest  | Configuration management for experiments and pipelines |
| Experiment Tracking  | MLflow (Docker)               | latest  | Dockerized tracking of runs and metrics via Docker MCP |
| Web Interface        | Streamlit                     | latest  | For building and deploying the user-facing application |
| Storage              | Local CSV (raw and processed) | latest  | Partitioned dataset with per-partition manifests       |
| Testing              | Pytest                        | latest  | Framework for writing and running tests                |
| Documentation        | MkDocs                        | latest  | Static site generator for project documentation        |
| Orchestration        | Prefect                       | latest  | Workflow orchestration and scheduling                  |

## Risks & Assumptions

### Key Assumptions

**Data Availability:** We assume the CollegeFootballData.com API will remain available, reliable,
and consistent throughout the season.

**Model Viability:** We assume that opponent-adjusted features derived from play-by-play data
contain enough signal to build a predictive model with a win rate >52.4%.

**User Behavior:** We assume users will primarily use this tool as a decision-support system, not
as a blind autopilot.

### Risks

- **Data Quality Risk:** Inaccurate or missing data could compromise model performance.
- **Model Drift Risk:** As the season progresses, model assumptions may become stale.
- **Operational Risk:** Failures in the automated pipeline could result in missed weekly updates.
- **Responsible Use Risk:** Users might misinterpret or misuse recommendations.

### Mitigations

- Implement data validation checks and alerts for missing or anomalous data.
- Monitor model performance over time (win rate, calibration) and retrain or adjust features as
  necessary.
- Implement logging and notifications for pipeline failures.
- Clearly communicate that recommendations are not guarantees and that users should bet
  responsibly.

## Success Criteria

### Quantitative

- Achieve a long-term win rate >52.4% on recommended spread bets over a full season.
- Maintain at least 95% uptime for weekly pipeline execution (data ingestion, model training,
  prediction generation).
- Maintain a low rate of critical bugs in production (e.g., incorrect lines or mis-priced games).

### Qualitative

- Users report that the system improved their betting decision-making.
- The project owner can iterate on features and models without fear of breaking the pipeline.
- Documentation is clear enough for a new contributor to get productive within a few sessions.

## Governance & Decision-Making

- The project owner has final say over model deployments, betting policy changes, and major
  architectural decisions.
- Architectural and modeling decisions are logged in `docs/decisions/decision_log.md`.
- Epics and tasks are managed via the implementation schedule (`docs/roadmap.md`).

## Dependencies

- CollegeFootballData.com API access and rate limits.
- Python ecosystem (libraries like pandas, scikit-learn, etc.).
- Local storage availability for data and artifacts.

## Open Questions

- What is the best approach for modeling totals (over/under) alongside spreads?
- How should we best calibrate predictions and edges (e.g., Platt scaling, isotonic regression)?
- How often should models be retrained during the season?

## RACI (High-Level)

| Task                        | Responsible | Accountable | Consulted | Informed  |
| --------------------------- | ----------- | ----------- | --------- | --------- |
| Data Ingestion & Validation | Dev         | Owner       | Community | Owner     |
| Feature Engineering         | Dev         | Owner       | Community | Owner     |
| Model Development           | Dev         | Owner       | Community | Owner     |
| Betting Policy Definition   | Owner       | Owner       | Community | Community |
| Web UI Implementation       | Dev         | Owner       | Community | Owner     |
| MLOps & Pipeline Automation | Dev         | Owner       | Community | Owner     |

## Risk Register (Snapshot)

| Risk                   | Likelihood | Impact | Mitigation                                                                                     |
| ---------------------- | ---------- | ------ | ---------------------------------------------------------------------------------------------- |
| Data Quality Issues    | Medium     | High   | Implement validation and alerts for anomalies in source data.                                  |
| Model Underperformance | Medium     | High   | Regularly evaluate performance; adjust features and models as needed.                          |
| Pipeline Failures      | Low        | High   | Add monitoring and retry logic; the pipeline should fail gracefully and notify administrators. |
| CFB Data API Failure   | Low        | High   | Implement robust error handling and fallback strategies where possible.                        |

## Decision Log

_Key architectural and product decisions will be recorded here as the project evolves._

---

_This document consolidates the project definition, technical context, and scope appendix into a
single source of truth._
