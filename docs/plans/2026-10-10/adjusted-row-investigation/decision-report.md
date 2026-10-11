# Adjusted-row investigation decision report — 2026-10-10

The investigation is complete: all **95 original database-only keys** were recovered, individually explained and verified against current Preview and Production. All remain unchanged. **No database or R2 writes were performed. Remediation is still open and requires a separate reviewed scope.**

## Historical identity and scope

The retained adjusted Parquet snapshot has raw SHA-256 `ddb8814789307ac72d4d5d9109eadc1c589ed74e2a477b002e74ec694e234e16` in both environments, exactly matching the [saved Preview metadata](../../2026-10-07/stage1-evidence/matchup-previous-preview-meta.json) and [Production metadata](../../2026-10-07/stage1-evidence/matchup-previous-production-meta.json). Full adjusted, game-measurement and rating-component snapshots were preserved under [historical/](historical/preview/capture-metadata.json); each Parquet checksum was checked before copying. The original captured name inventory contains 138 names; Preview and Production inventories agree and aliases are checked for ambiguity/collision.

The in-memory reconstruction uses the pinned Week-5 Task 4 plan (`conf/rebuild/6a_task4_w5_v1.yaml`), its checked Git inputs and signed/hash-checked published objects. The rebuilt population agrees with both the immutable Task 4 report and the independently saved comparison's adjusted-table section. Their report envelopes differ because the saved file also records Production/Preview parity; equality is checked on the actual adjusted-table comparison, without equating different envelopes.

| Population | Keys |
|---|---:|
| Historical database, as-of weeks 1–5 | 2,062 |
| Corrected historical candidate | 1,967 |
| Shared historical keys | 1,967 |
| Historical database-only extras | 95 |
| Historical candidate-only extras | 0 |
| Separately added as-of-6 candidate | 549 |
| Full pinned candidate including as-of-6 | 2,516 |
| Current database in each environment | 2,611 |

The canonical key is `(season, as_of_week, team, role, measurement_id)`. No as-of-6 rows were used to redefine the historical discrepancy. Cutoffs come from the pinned source lock; eligibility requires `week < as_of_week` and kickoff plus six hours at or before the cutoff.

## Individual explanations and current disposition

All 95 keys are `epa_per_possession`, across 45 teams:

| As-of week | Extras |
|---|---:|
| 1 | 4 |
| 2 | 34 |
| 3 | 31 |
| 4 | 18 |
| 5 | 8 |

For every key, the verified original observation parent supplied observed EPA and the old adjusted row is independently reproduced using the whole original adjustment population, including its raw/adjusted values, opponent adjustment, exposure, games, rank, cohort and cutoff. The corrected observations instead declare `missing_or_nonfinite_eligible_ppa`; their raw value is null and usable exposure is zero. All relevant eligible corrected observations are missing, leaving **zero observed EPA observations** for that team/role/window. The existing builder therefore emits no adjusted row. This is missing coverage, not a numerical zero or a count-based inference.

Both source populations confirm completed games, valid outcomes and matching team, week and kickoff identities. Each key's explanation includes source game IDs, original/corrected observation fields, source hashes, population records, adjustment-population hashes, reconstructed legacy row and current row.

- [Preview complete 95-key CSV](preview-final/historical-extras.csv) and [source explanations](preview-final/source-explanations.json).
- [Production complete 95-key CSV](production-final/historical-extras.csv) and [source explanations](production-final/source-explanations.json).

Every key is classified **supported exclusion recommendation**, subject to separately approved replacement. All 95 still exist unchanged in both databases. There are **zero unresolved historical findings**.

## Current state and later context

All 2,062 historical business rows remain unchanged from the original snapshots. There are no new population, numerical or lineage changes in this scope. The later 549 as-of-6 rows match the pinned candidate's keys and non-provenance fields; all 1,098 manifest-field differences are individually retained and bound to verified publication manifests. The original synthetic comparison uses the corrected root's signed canonical identity for both manifest fields, whereas serving publication uses the actual rating manifest and raw root identity. This explains provenance differences without claiming numeric drift.

- [Historical/current comparison](production-final/historical-current-drift.json).
- [Later field differences](production-final/later-field-differences.csv), [per-key later dispositions](production-final/later-dispositions.csv), [verified publication references](production-final/publication-lineage.json).
- [Cross-environment business comparison](production-final/environment-drift.json): all 2,611 exact keys and business fields agree.
- [All-field offline review](review-final/receipt.json) and [exact timestamp differences](review-final/metadata-differences.csv): `updated_at` differs on 2,611 rows. These timestamps are recorded as operational metadata from environment-specific upserts (`updated_at = NOW()`), not suppressed or treated as model-input drift. The Preview legacy publication record precedes its row timestamps by about 29 seconds; the other three publication/row timestamp groups coincide. The original snapshots omit `updated_at`, so historical write-time equivalence is not claimed.

Capture identities are the restricted `cks_preview_pipeline` and `cks_prod_pipeline` roles, with both login and effective role checked. Both transactions reported read-only `on` and isolation `repeatable read`; capture timestamps and database identity are in each snapshot. This is a captured-state investigation, not continuing assurance about future writes.

## Reproduction and receipt verification

Use a fresh output directory for every run; existing directories are refused. R2 must be explicitly configured and match the pinned Preview storage identity. Use the environment wrappers to select restricted credentials:

```bash
zsh scripts/ops/with_preview_env.sh uv run python scripts/pipeline/investigate_adjusted_rows.py \
  --environment preview --comparison-plan conf/rebuild/6a_task4_w5_v1.yaml \
  --output-dir artifacts/audit/adjusted-rows/preview-new

zsh scripts/ops/with_production_pipeline_env.sh uv run python scripts/pipeline/investigate_adjusted_rows.py \
  --environment production --comparison-plan conf/rebuild/6a_task4_w5_v1.yaml \
  --output-dir artifacts/audit/adjusted-rows/production-new \
  --peer-output artifacts/audit/adjusted-rows/preview-new
```

The final [Preview receipt](preview-final/receipt.json) and [Production receipt](production-final/receipt.json) bind code hashes (including readers, pure builder, adjuster and name map), all inputs and every output. Receipts use canonical SHA-256 checksums; they do not attest a release decision. The offline [verification script](verify-evidence.py) checked every final output checksum, both receipt self-hashes and all environment fields. Its review directory is also create-once.

Earlier runs are retained as development/partial evidence; only `preview-final`, `production-final` and `review-final` are the completed handoff. `preview-r1` stopped because the two report envelopes differ; this failure was preserved and the comparison corrected to the actual table section. No failed run was overwritten.

## Separately scoped remediation recommendation

**Engineer/user owner:** prepare a new execution contract for certified historical EPA replacement covering as-of weeks 1–5, including the exact 95 stale keys, affected shared EPA values/ranks/cohorts, immutable before-state snapshots and appropriate owner permissions. The original comparison already reports 951 shared EPA rows with differences; deleting 95 rows alone does not repair the historical cohort or values.

Require drift checks against the exact reviewed keys/fields, atomic application, independent complete-population/value/provenance readback and rollback proof. Preserve old evidence and all later as-of-6 rows; keep release approvals separate. Do not use these recommendations as deletion authority. Descendant certification and the broader repair completion matrix remain open.

## Validation

- 18 focused investigation tests and 17 unchanged documentation-authority tests passed (35 total, warnings as errors).
- Scoped Ruff lint/format checks passed.
- Offline final receipt/output/all-field review passed.
- Strict MkDocs and `git diff --check` are recorded in the implementation log after final validation.
