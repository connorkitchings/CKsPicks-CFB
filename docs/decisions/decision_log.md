# Decision Log

Log of planning-level decisions. Use one entry per decision.

---

## 2025-09-04 — Processed Schema Versioning in Manifests

- Category: Data / Storage
- Decision: Add `schema_version`, `data_type`, `file_format`, and `entity` to all partition `manifest.json` files for both raw and processed datasets.
- Rationale: Enables reliable downstream validation, reproducibility, and safe schema evolution across seasons.
- References: `src/cfb_model/data/storage/local_storage.py`, [LOG:2025-09-04]

## 2025-09-04 — Deep Semantic Validation Suite

- Category: Data Quality
- Decision: Implement deep validators for drives (byplay→drives), team_game (off/def mirrors; counts), team_season (recency-weight recompute), and opponent-adjusted (recompute vs persisted); expose via `--deep`.
- Rationale: Prevent silent aggregation drift and ensure consistency between pipeline layers.
- References: `src/cfb_model/data/validation.py`, [LOG:2025-09-04]

## 2025-09-04 — Quiet Aggregations Flag

- Category: Operations
- Decision: Add `--quiet` flag to pre-aggregation CLI; propagate `verbose` to persistence to reduce per-game logging.
- Rationale: Cleaner logs for long-running seasonal jobs; retains final summaries.
- References: `scripts/aggregations_cli.py`, `src/cfb_model/data/aggregations/persist.py`, [LOG:2025-09-04]

## 2025-09-04 — Historical Recollection (2014–2019, 2021–2024)

- Category: Data / Pipeline
- Decision: Re-collect plays across seasons (skip 2020) and re-run aggregations to unify schema and eliminate legacy inconsistencies (e.g., `is_drive_play`). Added driver script to automate.
- Rationale: Establishes uniform processed outputs across years; simplifies future strict schema validation.
- References: `scripts/recollect_plays_and_aggregate.py`, [LOG:2025-09-04]

## 2025-09-05 — Ruff Lint Policy Update

- Category: Code Quality
- Decision: Exclude notebooks from Ruff lint (`extend-exclude`: `*.ipynb`, `**/*.ipynb`, with `force-exclude: true`) and ignore `E501` globally to reduce noise from long docstrings and CLI help text.
- Rationale: Keep lint signal high in source code while avoiding churn from exploratory notebooks and long documentation strings.
- References: `pyproject.toml`, [LOG:2025-09-05]

## 2025-09-05 — Box Score vs Team-Game Validation Thresholds

- Category: Data Quality
- Decision: Adopt thresholds for comparing processed `team_game` metrics to CFBD advanced box scores:
  - Plays: WARN > 3, ERROR > 8
  - YPP: WARN > 0.20, ERROR > 0.50
  - Success rate: WARN > 0.02, ERROR > 0.05
- Rationale: Provide actionable validation tolerances that balance data variability with detection of aggregation drift.
- References: `src/cfb_model/data/validation.py` (validate_team_game_vs_boxscore), [LOG:2025-09-05]

## 2025-08-11 — Documentation Structure

- Category: Docs
- Decision: Rename `docs/reference/` → `docs/project_org/`, update MkDocs nav and internal links.
- Rationale: Clearer, minimal structure for authoritative project docs.
- References: [LOG:2025-08-11], `mkdocs.yml`, `docs/index.md`.

## 2025-08-11 — Weekly Pipeline Operations

- Category: Operations
- Decision: Manual weekly run on Wednesdays at 12:00 ET; CSV output `reports/YYYY/CFB_weekWW_bets.csv`.
- Rationale: External/local storage prevents full automation; ensures timely mid-week report.
- References: [LOG:2025-08-11], `docs/operations/weekly_pipeline.md`.

## 2025-08-11 — Modeling Baseline

- Category: Modeling
- Decision: MVP uses Ridge Regression for spread and total; begin predictions only after teams have
  ≥ 4 games; bet thresholds: spread ≥ 3.5, total ≥ 7.5.
- Rationale: Stable baseline, simple policy aligned with MVP objectives (≥53% hit rate).
- References: [LOG:2025-08-11], `docs/project_org/modeling_baseline.md`, `docs/project_org/project_charter.md`.

## 2025-08-12 — Training Window and Feature Engineering Specs

- Category: Modeling / Features
- Decision:
- Training window: 2019–2023, excluding 2020; 2024 as holdout/test.
  - Opponent adjustment: additive offset, 4 iterations; league-mean centering; opponent means
    weighted by game-level recency weights.
  - Recency: linear last-3 weighting at game level (weights 3, 2, 1; earlier games = 1).
  - Base stats to adjust (offense/defense where applicable): EPA/play, success rate (CFBD thresholds),
    yards/play, rush yards/play, pass yards/play, explosive rates (rush ≥15, pass ≥20; overall 10+/20+/30+),
    possession metrics (Eckel rate; finishing points per scoring opportunity at opp 40+).
- Rationale: Keep MVP explainable and robust while capturing schedule strength and pace/finishing context.
- References: [LOG:2025-08-12], `docs/project_org/modeling_baseline.md`, `docs/project_org/feature_catalog.md`,
  `docs/planning/roadmap.md`, `docs/cfbd/data_ingestion.md`.
