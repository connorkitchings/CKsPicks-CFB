# Decision Log

Log of planning-level decisions. Use one entry per decision.

---

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
  - Training window: 2014–2024, excluding 2020.
  - Opponent adjustment: additive offset, 4 iterations; league-mean centering; opponent means
    weighted by game-level recency weights.
  - Recency: linear last-3 weighting at game level (weights 3, 2, 1; earlier games = 1).
  - Base stats to adjust (offense/defense where applicable): EPA/play, success rate (CFBD thresholds),
    yards/play, rush yards/play, pass yards/play, explosive rates (rush ≥10, pass ≥15; overall 10+/20+/30+),
    possession metrics (Eckel rate; finishing points per scoring opportunity at opp 40+).
- Rationale: Keep MVP explainable and robust while capturing schedule strength and pace/finishing context.
- References: [LOG:2025-08-12], `docs/project_org/modeling_baseline.md`, `docs/project_org/feature_catalog.md`,
  `docs/planning/roadmap.md`, `docs/cfbd/data_ingestion.md`.
