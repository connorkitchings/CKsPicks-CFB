# CFBD Point-in-Time Data Pipeline

The production data path is request-addressed and fail closed:

```text
CFBDSourceAdapter request
  → canonical JSON hash + immutable Bronze Parquet
  → catalog capture observation
  → provider-neutral Silver version
  → reconciled team-game version
  → team-side Gold features
  → deterministic wide inference view
```

Week `0` is a valid value everywhere. Missing weeks are rejected rather than
coerced to zero. A failed weekly request fails the complete source step, and
compatibility partitions are updated only after the Bronze capture and catalog
registration succeed.

Silver builds require explicit Bronze capture IDs. Gold builds require explicit
Silver/Gold parent refs. Dataset manifests record both dependency types, schema,
code/config hashes, coverage, validation, and point-in-time cutoff. Production
readers never select mutable partitions.

The canonical Gold dataset has one row per `(season, game_id, team)` and retains
separate `prior_*` and `current_*` feature blocks. A derived wide dataset supplies
the home/away shape used by model training and inference. Prior/current blending
is performed only by a frozen model route using temporal OOF-selected weights.

## Operational commands

```bash
python -m cks_picks_cfb.ops fetch-source
python -m cks_picks_cfb.ops build-silver
python -m cks_picks_cfb.ops build-team-game  # explicit data_corrections ref required
python -m cks_picks_cfb.ops build-features
python -m cks_picks_cfb.ops audit-data
```

All commands require an explicit preview or production environment. Preview is
the default rollout target; production promotion remains a separate validated
operation.

## Historical bootstrap

Historical migration uses separately scoped object-read/list credentials under
`CFB_R2_SOURCE_*`. The source client is wrapped by `ReadOnlyStorage`, which
rejects every public write and disables the legacy `read_index` path because its
error handler can quarantine into the source bucket.

```bash
make inventory-source
make import-history

# Adding locked 2025 baseline predictions requires the frozen design identity.
make build-baselines YEAR=2026 ENV=preview AS_OF=<timestamp> \
  CORE_REF_URI=<uri> OUTPUT_REF_URI=<uri> FROZEN_DESIGN_SHA=<sha>
```

Native Bronze objects retain provider `cfbd`; transformed partitions are
registered as `legacy_cfbd_export`. Imports preserve the source URI, SHA-256,
ETag/version metadata, modification time, format, and partitions. A legacy
market row without its own authentic `captured_at` fails Silver validation.

Structural Gold contains no baseline predictions. Baselines are a separate
temporal artifact, and model-ready Gold depends explicitly on structural Gold,
baseline predictions, and canonical market snapshots. The default baseline
build generates only 2022-2024 OOF predictions. Adding 2025 requires both
`--include-locked-2025` and `--frozen-design-sha`.
