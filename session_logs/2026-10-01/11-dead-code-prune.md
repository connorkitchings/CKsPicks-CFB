# Session: Dead-code prune

## TL;DR
- **Worked On:** Executed the user-approved dead-code prune (contract `docs/plans/2026-10-01/05-dead-code-prune.md`), including deleting top-level `research/`.
- **Outcome:** Removed 9 unreferenced Python modules, 13+ V2/legacy Hydra configs, deprecated `web/db/migrations` and its scripts, and `research/` (65 tracked files). Test results identical to baseline.
- **Plan Contract:** `docs/plans/2026-10-01/05-dead-code-prune.md` (Implemented)
- **Approval / Status:** User approved the prune list and `research/` deletion in-session.
- **Blockers:** None.
- **Next:** Contract 04 (boundary refactor) awaits approval; remaining review follow-ups (CI/security hardening, V5 release scripts under ops).

## Context and Decisions
- Each path was re-grepped for importers immediately before deletion. `web/src/data/model-accuracy.json` was removed from scope: it is the output of the tested `scripts/pipeline/extract_model_accuracy.py`.
- Kept: `scoring.py`, `analysis/unadjusted.py`, `utils/validation.py` (tested), `conf/weekly_bets/v2_champion.yaml` (ops default), `train.py` + `models/v2_*` (V4 path), orphaned matchup components (plan 10-01/02).
- **Regression I introduced earlier and fixed:** my status-doc consolidation (commit `11c815a`) had removed wording required by `tests/test_data_first_documentation_authority.py` ("Week 4", "V4", "six slates are not…") from README/QUICKSTART/CONTEXT/index. I had not run pytest then. Restored in this session; the earlier log's "Not run: pytest" was accurate but the check should have run.

## Work Completed
- Python: deleted `training/`, `loader.py`, `flows/`, `config/champion.py`, `data/ratings.py`, `utils/{model_registry,visualizations,lineage_tracking}.py`.
- Config: deleted `conf/experiment/{v2_*,02_opponent_adjustment,extended_features_crossval}.yaml`, `conf/experiment/legacy/`, `conf/legacy/`; updated `.codex/HYDRA.md` and `MAP.md`.
- Web: deleted `web/db/`, removed `db:migrate`/`db:generate` from `web/package.json`.
- `research/`: deleted; removed excludes from `pyproject.toml`; fixed references in AGENTS, QUICKSTART, CONTEXT, repository_boundaries, data-first roadmap.

## Validation
- [x] Baseline and final: `CFBD_API_KEY=dummy uv run pytest -q -n 4 --no-cov` → 1543 passed, 3 skipped. Without a key, 16 tests fail identically before and after (they need `CFBD_API_KEY`; this container has no `.env`).
- [x] `uv run ruff check .`; `uv run python contracts/validation.py`; `uv run mkdocs build --quiet`
- [x] Hydra `compose(config_name="config", overrides=["experiment=week0_regimes"])` works
- [x] `cd web && npm run lint && npm run typecheck && npm run test:publication` (49/49)
- [x] `git diff --check`

## Amendments and Blockers
- None. Pre-existing, untouched: `uv run ruff format --check .` reports 15 files needing formatting (e.g. `ops/__main__.py`, `data/lake.py`, `generate_weekly_bets.py`); CI's lint job runs that check, so it may be red. Not reformatted here (repo rule: no broad formatting without authorization).

## Handoff Notes
- **Resume at:** decide whether to authorize a scoped `ruff format` of those 15 files; approve contract 04.
- **Watch out for:** `ratings_lab`/`scripts/research` are production paths, not dead code (contract 04).

**tags:** ["cleanup", "dead-code", "docs", "plan"]
