# Session: Preseason / Week 1 Model v1

## TL;DR

- **Worked On:** A point-in-time preseason feature, model, validation, and inference path.
- **Completed:** Immutable snapshot ingestion, line-free matchup features, Ridge spread/total bundle training, promotion gates, early-season blending, and tests.
- **Blockers:** No 2026 snapshot has been captured; live provider availability is intentionally required before the candidate can be enabled.
- **Next:** Backfill immutable 2019/2021-2025 snapshots, train against the locked 2024 holdout, select training-only blend weights, and only enable the config after promotion passes.

## Changes Made

- `src/cks_picks_cfb/preseason.py`: Snapshot contract, feature builder, Ridge bundle, validation, blend selection, and routing helpers.
- `scripts/data/ingest_preseason.py`: Immutable CFBD snapshot capture CLI.
- `scripts/pipeline/train_preseason_model.py`: Guardrailed training with 2019/2021-2023 train, 2024 holdout, and optional 2025 shadow.
- `scripts/pipeline/select_preseason_blend.py`: Training-only blend-weight selection CLI.
- `scripts/pipeline/generate_weekly_bets.py`: Opt-in, complete-snapshot and promotion-gated preseason prediction routing.
- `conf/weekly_bets/v2_champion.yaml`: Disabled-by-default preseason candidate configuration.
- `docs/ops/weekly_pipeline.md`: Gated snapshot and promotion workflow for the optional candidate.
- `tests/test_preseason.py`: Snapshot, feature, model, blend, and fallback-unit coverage.

## Testing

- [x] `uv run ruff format .`
- [x] `uv run ruff check .`
- [x] `uv run pytest -q` — 202 passed
- [x] `make contracts-check`
- [x] New CLI `--help` smoke checks

## Notes for Next Session

1. Capture snapshots once per source/date with `scripts/data/ingest_preseason.py`; never reuse an existing `year/as_of` path.
2. All five sources must be nonempty for inference: returning production, transfers, recruiting, coaches, and talent.
3. The weekly generator still uses the established recency fallback until `preseason.enabled` is manually set and the model bundle contains `validation.promotion_pass: true`.

**tags:** ["preseason", "week1", "pipeline", "modeling", "r2"]
