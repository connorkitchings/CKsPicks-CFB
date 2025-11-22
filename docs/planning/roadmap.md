# Implementation Schedule

This document is the tactical plan for the **cfb_model** project. It translates the goals from the
[Project Charter](../project_org/project_charter.md) into a high-level schedule of epics and tasks.

> 📋 **Last Updated**: 2025-10-11 | **Next Review**: Weekly Wednesday sprint planning
> 🔗 **Related**: [Open Decisions](../project_org/open_decisions.md) | [Decision Log](../decisions/decision_log.md)

## Sprint Overview

**Current Sprint:** Sprint 4: MLOps Foundation

**Key Goals:**

- Finalize the integration of Hydra and Optuna for hyperparameter optimization.
- Refactor the prediction pipeline to use Hydra for configuration.
- Integrate the MLflow Model Registry (Dockerized via Docker MCP) for model versioning.

---

## Development Schedule

### Sprint 4: MLOps Foundation

| ID  | Epic  | Deliverable                                | Effort | Dependencies | Priority |
| :-: | :---- | :----------------------------------------- | :----: | :----------- | :------: |
| 35  | MLOps | Finalize Hydra/Optuna Integration          |   3d   | -            |   High   |
| 36  | MLOps | Refactor Prediction Script with Hydra      |   2d   | Task 35      |   High   |
| 37  | MLOps | Integrate Dockerized MLflow Model Registry |   2d   | Task 35      |  Medium  |

### Sprint 5: Advanced Modeling & Monitoring

| ID  | Epic       | Deliverable                              | Effort | Dependencies      | Priority |
| :-: | :--------- | :--------------------------------------- | :----: | :---------------- | :------: |
| 14  | Modeling   | Experiment with XGBoost                  |   6d   | Task 20, OPEN-002 |  Medium  |
| 25  | Monitoring | Build a Simple Monitoring Dashboard      |   5d   | Task 21, OPEN-007 |   Low    |
| 38  | Monitoring | Implement Rolling Performance Monitoring |   3d   | Task 25           |   Low    |

### Future Sprint: Probabilistic Power Ratings (Research & Design)

| ID  | Epic       | Deliverable                                        | Effort | Dependencies         | Priority |
| :-: | :--------- | :------------------------------------------------- | :----: | :------------------- | :------: |
| 60  | Modeling   | Research memo on probabilistic power-rating models |   3d   | Points-For Model PRD |  Medium  |
| 61  | Modeling   | Draft PRD for Probabilistic Power Ratings          |   2d   | Task 60              |  Medium  |
| 62  | Data/Feat. | Spec for required inputs and outputs               |   2d   | Task 61, team_week   |  Medium  |
| 63  | MLOps      | Experiment plan for first prototype                |   2d   | Task 61              |   Low    |

## Completed Sprints

(For a detailed history of completed work, please refer to the `session_logs/` directory.)
