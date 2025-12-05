# Repository Cleanup & Reorg Plan (Draft)

This document captures the agreed direction for the upcoming repo cleanup/reorg. No actions have been taken yet.

## Goals (Process-First)
- Establish a single source of truth for process/usage.
- Reorganize docs for clarity without trimming content.
- Archive or remove unused/legacy items (scripts, configs, notebooks, artifacts).
- Start fresh for modeling artifacts (models, predictions, scores) while preserving the current 2025 Week 15 predictions so they can be scored next week.
- Keep modeling data on the external drive; improve artifact/documentation patterns.

## Decisions Confirmed
- Single-source hub will be `docs/guide.md` (new), with other docs pointing to it.
- Reorganize docs into clearer buckets; no content deletions, only moves/retitles and cross-links.
- Add `archive/` at repo root with a manifest for moved items.
- Archive the current decision log and start a fresh one.
- Wipe MLflow runs/models and other artifacts; preserve only 2025 Week 15 predictions for quick scoring (path to be confirmed).
- Keep notebooks `notebooks/API_Functions.ipynb` and `notebooks/CFB_Functions.ipynb`; archive other notebooks unless explicitly kept.
- Pause code changes until cleanup plan is executed.

## Proposed Structure (to implement)
- `docs/guide.md` — canonical hub with links to process, modeling, ops, planning, and research.
- `docs/process/` — ML workflow, agent/AI usage, development standards, checklists.
- `docs/modeling/` — modeling baseline/current strategy, feature catalog, evaluation criteria, calibration notes.
- `docs/ops/` — weekly pipeline, production deployment, data partition/paths, MLflow usage, dashboards.
- `docs/planning/` — roadmap, active plans, experiment templates.
- `docs/research/` — probabilistic ratings PRDs, exploratory writeups.
- `docs/archive/` — legacy/obsolete docs moved intact (e.g., older points-for PRDs if superseded).
- `archive/` (repo root) — unused scripts, legacy configs, stale notebooks/feature configs, legacy decision log, with a manifest `archive/MANIFEST.md`.

## Artifacts & Data Handling
- Delete: `artifacts/**`, `artifacts/mlruns/**`, `data/production/predictions/**`, `data/production/scored/**`.
- Preserve: 2025 Week 15 predictions for scoring; confirm exact file path(s) before deletion sweep.
- Continue storing modeling data on the external drive (`CFB_MODEL_DATA_ROOT`); add a short retention/paths note in `docs/guide.md`.

## Specific Move/Archive Candidates
- Scripts: unused items in `scripts/analysis/`, `scripts/experiments/`, `scripts/debug/`, `scripts/utils/` that are not referenced by current pipelines → `archive/` (note disposition in manifest).
- Configs: legacy Hydra experiments, unused feature configs → `archive/`.
- Notebooks: keep `API_Functions.ipynb`, `CFB_Functions.ipynb`; move others to `archive/` unless explicitly kept.
- Decision log: move `docs/decisions/decision_log.md` to `archive/decision_log_legacy.md`; create a fresh `docs/decisions/decision_log.md` shell.
- Points-for/legacy docs: if superseded, move to `docs/archive/` and link from `docs/guide.md` as historical context.

## Link/Reference Updates (post-move)
- Update internal links in README, CLAUDE.md, and other docs to point at `docs/guide.md` and new locations.
- Add redirects/notes in moved docs to avoid confusion.

## Open Items to Confirm Next Session
- Exact path(s) of 2025 Week 15 predictions to preserve.
- Final doc bucket mapping for specific files (e.g., CLAUDE.md linkage into `docs/guide.md`).
- Which scripts/configs are truly unused (quick audit checklist needed).
- Whether to export minimal MLflow metadata before deletion (likely no, per approval).

## Execution Order (when approved)
1) Create `docs/guide.md` scaffold; map links to existing docs.
2) Move docs into buckets and fix links; move legacy items into `docs/archive/`.
3) Create `archive/` with `archive/MANIFEST.md`; move unused scripts/configs/notebooks there.
4) Archive decision log; create fresh `docs/decisions/decision_log.md`.
5) Purge artifacts (`artifacts/**`, `artifacts/mlruns/**`, `data/production/{predictions,scored}/**`), keeping 2025 Week 15 predictions.
6) Add data/artifact retention note in `docs/guide.md`.
7) Sanity check links and paths; leave Week 15 generation untouched for scoring.

Prepared for next session; no changes applied yet.
