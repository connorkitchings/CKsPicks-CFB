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
