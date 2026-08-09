# Session: Historical R2 Bootstrap and Model-Ready Data

## TL;DR

- **Worked On:** Read-only historical source access, resumable production-R2 to
  preview import, Silver reconstruction, reconciliation, temporal Gold, and OOF
  baseline assembly.
- **Completed:** The preview bootstrap implementation, read-only source setup,
  optimized production inventory, inventory adjudication, execution plan, and
  local quality gates. Production remained read-only.
- **Blocker:** Historical betting-line exports lack authentic quote timestamps;
  exact market replay, grading, and ROI evaluation must remain blocked. The 2026
  opening slate also requires an explicit canonical Week 0 mapping because CFBD
  reports those games as provider Week 1.
- **Next:** Implement Phase 1 of
  `docs/planning/2026_historical_bootstrap_week0_execution.md`, then run the
  resumable preview import.

## Changes Made

- Added `ReadOnlyStorage` and separate `CFB_R2_SOURCE_*` configuration. All
  public write methods fail before delegation; legacy `read_index` is disabled
  because its corrupt-object path can write quarantine data.
- Added source inventory with object metadata, representative schemas, seasons,
  weeks, forbidden-2020 reporting, and native-versus-legacy classification.
- Optimized inventory to reuse metadata from paginated R2 listings instead of
  issuing one HEAD request per object. The 36,138-object bucket now inventories
  in seconds rather than requiring tens of thousands of requests.
- Added deterministic, idempotent historical imports that preserve source URI,
  SHA-256, ETag/version, modification time, format, partitions, and capture IDs.
- Added one resumable `import-history` operation covering object imports,
  correction seeding, season-scoped Silver, reconciliation, combined 2021-2025
  refs, 2021-2026 schedule, temporal matchup inputs, structural Gold, selection
  baselines, model-ready assembly, and both audit modes.
- Fixed Silver partition selection, correction contracts, team-game-stat
  flattening, team aliases, game outcomes, and authentic market timestamp rules.
- Converted legacy play fixes into an immutable approved correction dataset.
- Split structural Gold, temporal baseline artifacts, and market-aware
  model-ready Gold. Default baselines cover only 2022-2024; 2025 requires a
  frozen-design SHA.
- Added kickoff-ordered current/prior matchup inputs with 2019 used only for
  early-2021 priors and explicit rejection of 2020.
- Updated operational and architecture documentation.

## Testing

- [x] Ruff format check
- [x] Ruff check
- [x] Full pytest — 273 passed
- [x] Contract validation
- [x] Migration tests — 2 passed
- [x] Web lint
- [x] Web typecheck
- [x] Web production build
- [x] Bootstrap CLI smoke checks
- [x] `git diff --check`
- [x] Execution plan and decision log updated
- [x] Read-only source credentials and local mutation guard
- [x] Production R2 inventory — 8,020 recognized / 7,156 eligible objects
- [ ] Historical import and source checksum verification
- [ ] Structural/model-ready data audits
- [ ] Complete 2025 preview replay and browser smoke tests

## Notes for Next Session

Read-only source R2, preview R2, and preview Neon are configured and verified.
The accepted adjudication keeps untimestamped lines in a separate
`legacy_market_references` dataset and prohibits their use in canonical markets,
leans, grades, ROI, model selection, or high-confidence labels. Preserve CFBD's
provider week and assign the August 29 opening slate through a versioned canonical
Week 0 policy. Implement those two contracts before `make import-history`.

**tags:** ["r2", "history", "bootstrap", "read-only", "silver", "gold", "oof"]
