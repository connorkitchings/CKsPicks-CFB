# Implementation Schedule

This document is the tactical plan for the **cfb_model** project. It translates the goals from the
[Project Charter](../project_org/project_charter.md) into a high-level schedule of epics and tasks.

## Sprint Overview

**Current Sprint:** Sprint 1 (MVP)

**Sprint Goal:** Establish the MVP plan and docs, finalize data scope and betting policy, and set up
the weekly manual pipeline (local Parquet storage). Deliver a clear Modeling Baseline and Weekly
Pipeline runbook; code work begins next sprint.

**Dates:** TBD

### Task Board (Sprint 1)

| ID | Epic          | Deliverable                                      | Owner | Status |
|:--:|:--------------|:--------------------------------------------------|:-----:|:------:|
| 1  | Docs          | Rename `reference/` → `project_org/`, fix links   | @dev  | ✅ Done |
| 2  | Docs          | Add `modeling_baseline.md`, `weekly_pipeline.md`  | @dev  | ✅ Done |
| 3  | Docs          | Add `decisions/README.md`, `decision_log.md`      | @dev  | ✅ Done |
| 4  | Docs          | Update `mkdocs.yml` + `docs/index.md` nav         | @dev  | ✅ Done |
| 5  | CFBD Data     | Update ingestion: FBS-only, 2015–2024 (incl. 2020)| @dev  | ✅ Done |
| 6  | Operations    | Weekly pipeline (Wed 12 ET) + CSV spec            | @dev  | ✅ Done |
| 7  | Planning      | Refresh roadmap + acceptance criteria              | @dev  | ✅ Done |
| 8  | Feature Eng.  | Plan opponent-adj features (iter. avg, last-3)    | @dev  | ✅ Done |
| 9  | Modeling      | Outline training (season silo; Ridge)             | @dev  | ✅ Done |
| 10 | Operations    | Document bet thresholds and constraints            | @dev  | ✅ Done |

### Acceptance Criteria (Sprint 1)

- Project docs reorganized under `docs/project_org/`; nav updated in `mkdocs.yml` and `docs/index.md`.
- `docs/project_org/modeling_baseline.md` defines MVP model + betting policy.
- `docs/operations/weekly_pipeline.md` defines schedule, steps, and CSV output schema.
- CFBD resources moved to `docs/cfbd/resources/`.
- `docs/cfbd/data_ingestion.md` reflects FBS-only scope and clarifies ingestion coverage (2015–2024
  complete today) vs. modeling training window (2014–2024, excluding 2020). 2014 backfill is tracked
  as a backlog item.
- `docs/project_org/feature_catalog.md` expanded with:
  - Play filters (CFBD success rate thresholds; scrimmage-only), explosive definitions (rush ≥10,
    pass ≥15; overall 10+/20+/30+ buckets), possession metrics (Eckel rate; finishing points per opp).
  - Opponent-adjustment algorithm: additive offset, 4 iterations, linear last-3 game weights (3/2/1).
  - Validation ranges and reproducibility requirements.
- MVP feature artifacts specification documented: `features/<year>/*.parquet` (team-season,
  team-week, team-game), `features/<year>/manifest.json`, and a seasonal summary CSV at
  `reports/metrics/features_<year>_summary.csv`.
- Markdownlint: MD029 fixed in weekly pipeline; no critical new warnings introduced.

### Backlog (Future Sprints)

| ID | Epic                 | Deliverable                                              | Priority |
|:--:|:---------------------|:----------------------------------------------------------|:--------:|
| 11 | Feature Eng.         | Implement iterative averaging (4 iters) + feature catalog | High     |
| 12 | Modeling             | Ridge training + weekly prediction scripts               | High     |
| 13 | Operations           | Generate weekly CSV at `reports/YYYY/CFB_weekWW_bets.csv`| High     |
| 14 | Modeling             | Try alternative models (XGBoost, RF) after MVP           | Medium   |
| 15 | Explainability       | SHAP summaries for model insights                         | Medium   |
| 16 | Web Interface        | Minimal Streamlit view of weekly CSV                      | Medium   |
| 17 | Performance Tracking | ROI/win rate tracking dashboards                           | Medium   |
| 18 | CFBD Data            | Backfill 2014 season across entities to match training scope | Medium |

## Execution Checklist

- CFBD exploration
  - Document endpoints, params, rate limits, and common fields; add sample pulls script/notebook
  - Acceptance: endpoints/payloads documented; sample script prints schema examples

- External storage setup
  - Use `--data-root` (e.g., `/Volumes/EXTDRV/cfb_model_data`) and validate write permissions
  - Acceptance: ingestion writes Parquet to external drive; path documented

- Data transformation → modeling-ready
  - Build season-to-date aggregates; opponent adjustments (4 iterations) with last-3 weighting
  - Acceptance: reproducible feature build; feature catalog page added

- Modeling and testing (historical)
  - Train per-season Ridge for spread/total; report RMSE/MAE vs baselines; persist artifacts
  - Acceptance: metrics table produced per season; artifacts saved

- Backtesting vs historical lines
  - Compute edges; apply bet policy; track ROI/hit rate weekly and cumulatively
  - Acceptance: `reports/backtests/*` CSVs generated with summary KPIs

- Weekly live pipeline (current season)
  - Manual run (Wed 12:00 ET) producing `reports/YYYY/CFB_weekWW_bets.csv` per runbook
  - Acceptance: one entry-point runs E2E; clear success summary

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
