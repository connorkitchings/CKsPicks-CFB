# Implementation Schedule

This document is the tactical plan for the **cfb_model** project. It translates the goals from the
[Project Charter](./reference/project_charter.md) into a high-level schedule of epics and tasks.

## Sprint Overview

**Current Sprint:** Sprint 1 (MVP)

**Sprint Goal:** Build an end-to-end pipeline that ingests data, trains a baseline model,
generates weekly predictions, and displays them in a simple web interface.

**Dates:** TBD

### Task Board (Sprint 1)

| ID  | Epic                  | Deliverable                                           | Owner | Status  |
|:----|:----------------------|:------------------------------------------------------|:------|:--------|
| 1   | Data Pipeline         | Set up Supabase schema for games, plays, predictions. | @dev  | ⬜ Todo |
| 2   | Data Pipeline         | Build script to ingest historical PBP data via API.   | @dev  | ⬜ Todo |
| 3   | Feature Engineering   | Develop initial feature engineering logic from PBP.   | @dev  | ⬜ Todo |
| 4   | Modeling              | Train and serialize a baseline linear regression model. | @dev  | ⬜ Todo |
| 5   | Modeling              | Create script to generate/store weekly predictions.   | @dev  | ⬜ Todo |
| 6   | Web Interface         | Build a basic Streamlit app to display predictions.   | @dev  | ⬜ Todo |

### Backlog (Future Sprints)

| ID  | Epic                  | Deliverable                                           | Priority |
|:----|:----------------------|:------------------------------------------------------|:---------|
| 7   | Data Pipeline         | Implement automated weekly data ingestion with Prefect. | High     |
| 8   | Modeling              | Implement automated weekly model retraining/prediction. | High     |
| 9   | Performance Tracking  | Create a dashboard to track model performance vs lines. | High     |
| 10  | Modeling              | Integrate SHAP for model explainability.              | Medium   |
| 11  | Feature Engineering   | Add opponent-adjustment logic to features.            | Medium   |
| 12  | Web Interface         | Add historical performance charts and SHAP to UI.     | Medium   |
| 13  | Modeling              | Experiment with alternative models (e.g., XGBoost).   | Low      |

---

## Risk Management

| Risk                                      | Probability | Impact | Mitigation Strategy                                     |
|:------------------------------------------|:------------|:-------|:--------------------------------------------------------|
| CollegeFootballData.com API is unreliable | Medium      | High   | Implement robust error handling, caching, & monitoring. |
| Model performance is below 52.4% win rate | Medium      | High   | Focus on feature engineering and model tuning.          |
| Feature engineering is overly complex     | Low         | Medium | Start simple and add complexity incrementally.          |

---

## Sprint Retrospective

*To be filled out at the end of each sprint.*

| What Went Well | What Didn't Go Well | Action Items for Next Sprint |
|:---------------|:--------------------|:-----------------------------|
| TBD            | TBD                 | TBD                          |
