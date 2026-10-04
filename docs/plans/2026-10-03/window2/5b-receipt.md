# Window 2 Step 5B: exit receipt

- **Status:** **Closed** with Step 5 (user, 2026-10-04; committed `e33d63d`). Built and tested locally. The v1 mode of `possession_verification.py` deferred below was delivered in 5C (`ea53c07`). No dataset was built or published and nothing was written to Preview, production or any database by this step.
- **Authority:** [contract 04, Amendment 2](../04-data-integrity-two-window-implementation.md), [Appendix A, 5B](data-contracts-and-certification.md) and its Amendment 1, authorized by the user on 2026-10-04.
- **Exit gate in Appendix A:** "schema, population, null propagation and served PPP-only tests pass; no structural refactor."

## What was built

| Piece | Where | Tests |
|---|---|---|
| Versioned metric registry (23 definitions, registry checksum; rank directions equal the existing website contract) | `src/cks_picks_cfb/metrics/registry.py` | `tests/test_metric_registry.py` (6) |
| Four dataset contracts registered in `schema_for`: `team_game_metrics_v1`, `football_possessions_v1`, `football_scoring_ledger_v1`, `scoring_attribution_evidence_v1` | `src/cks_picks_cfb/data/schema_contracts.py` | `tests/test_gold_contracts.py` (19, with the validators) |
| Semantic validators: null-versus-zero, observed-versus-missing, defense mirror, deterministic possession ids, ledger references and admission, evidence rights | `src/cks_picks_cfb/metrics/contracts.py` | same file |
| Pure `team_game_metrics` builder and season aggregation (weighted ratios; a missing game withholds the aggregate) | `src/cks_picks_cfb/metrics/builders.py` | `tests/test_team_game_metrics_builder.py` (12) |
| Baseline ledger and possessions converted to the v1 contracts | `src/cks_picks_cfb/metrics/ledger.py` | `tests/test_ledger_conversion.py` (8) |
| Nullable PPA, opt-in, default unchanged; build-script flag | `features/byplay/enrichment.py`, `features/pipeline.py`, `scripts/pipeline/build_team_game_dataset.py` | `tests/test_new_features.py` (+4) |
| Issue 7: stream team scores compared with certified finals, recorded, non-blocking | `data/reconciliation.py`, `scripts/pipeline/build_team_game_dataset.py`, `quality/silver.py` | `tests/test_reconciliation_stream_points.py` (9) |
| Null-aware consumers (v1 data only): offsets, independent offset verifier, corpus audit, blocker diagnosis | `forecast/offsets.py`, `forecast/forecast_verification.py`, `audit/corpus.py`, `audit/foundation_blocker_diagnosis.py` | `tests/test_null_ledger_consumers.py` (15) |
| Served-path proof: ratings identical when every EPA observation is removed, scrambled, made extreme or withheld; changing a PPP observation does move them; import chain never touches the EPA tournament | `tests/test_served_ppp_isolation.py` | 8 |
| R2 retention of the 162 CFBD drive responses (5A, approved) | `scripts/data/upload_cfbd_drives_5a.py` | run result below |

## Verified against real data (read-only, 2026 weeks 0-4: 215 games, 430 team-games)

- The existing baseline ledger converts to the v1 contracts with **0 semantic problems**: 2,034 events and 7,222 possessions pass the schema and every rule; the 53 unresolved markers that carried zero increments are now null; every possession reference resolves to a deterministic id (the baseline stored play ids).
- The stream-score comparison runs for all 215 games (430 team-games) and finds **6 mismatches, none blocking**, consistent with the October investigation's 6 of 215 games that overshoot the final.
- The CFBD drive upload to `raw/cfbd/drives/` wrote 162 objects plus the checksum manifest, each read back and hash-checked, and a second run found all 162 identical (idempotent).

## Validation

Full suite with CI's flags (warnings as errors, parallel workers): 1814 passed, 9 skipped. `ruff format --check`, `ruff check`, `contracts/validation.py`, and `python -m cks_picks_cfb.quality --verify-registry` (29 checks) pass. The data-quality catalog test passes with the new `silver.stream_scores_match_finals` check.

## Not done in 5B, and why

- **No Silver or Gold dataset was built or published.** The nullable-PPA Silver rebuild, the Gold `team_game_metrics`, possessions and ledger datasets, and their signed manifests are 6A/5C work and need R2 writes.
- **Admission of R1 groups** (the 1,416 corroborated groups; the 402 recovery groups revert) and the independent admitted-ledger verifier are 5C. The converters and contracts here are what 5C fills.
- **The website and V5 consumers still read the existing team-stat and measurement paths.** Switching them to `team_game_metrics` is later work and must keep the website population (FBS-vs-FBS regular season) separate from the V5 population.
- **`ratings/possession_verification.py` has no v1 mode yet** (see Amendment 1).
- **No numeric check against the website's published team stats** was made: the builder computes metrics from game rows, and agreement with the season aggregates in `team_season_stats` is untested.
- The 2015-2019 and 2021-2025 corpora were not run through the new builder; only synthetic frames and the 2026 baseline ledger were.

## For your review

1. The `points_scored` metric and the JSON-text storage convention (Appendix A, Amendment 1).
2. That the stream-score mismatch is recorded but never blocks the Silver build.
3. Whether to proceed to 5C (admission and independent certification) next.

## Subsequent pre-6A review (2026-10-04)

This receipt retains what Step 5 established at the time. Closed review questions and dated “not done” entries above are historical. The [approved pre-6A contract](../../2026-10-04/02-pre-stage6-integrity-and-rebuild.md) now governs remaining integration, corrected missingness/aggregation/admission semantics, evidence-table construction and the rebuild. Step 5 closure is not an end-to-end certification of those consumers. Preview R2 plus verified Preview catalog registration is authorized for 6A; serving and production writes remain excluded.
