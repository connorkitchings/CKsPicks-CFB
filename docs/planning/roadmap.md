# Implementation Schedule

This document is the tactical plan for the **cfb_model** project. It translates the goals from the
[Project Charter](./reference/project_charter.md) into a high-level schedule of epics and tasks.

## Sprint Overview

**Current Sprint:** Sprint 1 (MVP)

**Sprint Goal:** Build an end-to-end pipeline that ingests data, trains a baseline model,
generates weekly predictions, and displays them in a simple web interface.

**Dates:** TBD

### Task Board (Sprint 1)

| ID | Epic               | Deliverable                               | Owner | Status |
|:--:|:-------------------|:-------------------------------------------|:-----:|:------:|
| 1  | Data Pipeline      | Parquet layout + validation utils          | @dev  | ⬜ Todo |
| 2  | Data Pipeline      | Ingest historical PBP via API              | @dev  | ⬜ Todo |
| 3  | Feature Eng.       | Basic features (e.g., yards/play) from PBP | @dev  | ⬜ Todo |
| 4  | Modeling           | Train baseline linear regression model     | @dev  | ⬜ Todo |
| 5  | Modeling           | Weekly predictions script                  | @dev  | ⬜ Todo |
| 6  | Web Interface      | Basic Streamlit UI for predictions         | @dev  | ⬜ Todo |

### Backlog (Future Sprints)

| ID | Epic                 | Deliverable                                  | Priority |
|:--:|:---------------------|:----------------------------------------------|:--------:|
| 7  | Data Pipeline        | Weekly ingestion (Prefect)                    | High     |
| 8  | Modeling             | Weekly retrain + prediction                   | High     |
| 9  | Performance Tracking | Dashboard: model vs lines                     | High     |
| 10 | Modeling             | SHAP explainability                           | Medium   |
| 11 | Feature Eng.         | Opponent-adjusted features                     | Medium   |
| 12 | Web Interface        | Historical charts + SHAP in UI                | Medium   |
| 13 | Modeling             | Try other models (e.g., XGBoost)              | Low      |

---

## Risk Management

| Risk                             | Prob. | Impact | Mitigation                              |
|:---------------------------------|:-----:|:------:|:----------------------------------------|
| CFBD API unreliability           | Medium| High   | Error handling, caching, monitoring      |
| Win rate below 52.4%             | Medium| High   | Improve features and tuning              |
| Overly complex feature pipeline  | Low   | Medium | Start simple; add complexity gradually   |

---

## Sprint Retrospective

*To be filled out at the end of each sprint.*

| What Went Well | What Didn't Go Well | Action Items for Next Sprint |
|:---------------|:--------------------|:-----------------------------|
| TBD            | TBD                 | TBD                          |
