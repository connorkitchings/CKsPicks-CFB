# Phase 0 Cleanup Disposition

**Recovery commit:** `b930066`

Phase 0 classifies repository material without moving or deleting existing
Python, configuration, or documentation paths. Dynamic command use and stored
code identities make static reference counts insufficient evidence for
removal.

| Classification | Paths | Known references and role | Replacement or rationale | Reconsider |
|---|---|---|---|---|
| `current-production` | `src/cks_picks_cfb/data/`, `features/`, `inference/`, `ops/`; `scripts/pipeline/generate_weekly_bets.py`, `publish_to_db.py`, `freeze_week.py`, `replay_season.py`, scoring commands; `conf/weekly_bets/v4_2026.yaml`; `contracts/`; `web/` | Make targets, operations state machine, V4 bundle/config, schema validation, and live app | Current supported system; preserve | Only through a separate production contract |
| `new-research` | `scripts/research/`; `conf/research/data_first_football_v1/`; `artifacts/research/data-first-football-v1/` | New data-first contracts and future Phase 1–6 commands | Target location; no model/data implementation in Phase 0 | Populate under each later contract |
| `named-benchmark-compatibility` | `scripts/pipeline/build_successor_r1_foundation.py`, `build_successor_history_ref_set.py`, `certify_successor_history.py`; related `conf/ratings/` and `src/cks_picks_cfb/ratings/` readers | R1 orchestration, tests, docs, and immutable identities | Preserve exact paths for certified R1 reproduction | After the Phase 1 evidence audit |
| `named-benchmark-compatibility` | `build_rating_measurements.py`, `build_rating_team_states.py`; measurement/state configs and reusable rating modules | Fixed rating benchmark tests and reports | Preserve as the simple historical reference | Phase 3 or 4 after corrected lineage is known |
| `named-benchmark-compatibility` | `build_rating_shadow_freeze.py`, `build_rating_shadow_score.py`, `audit_rating_prospective_evidence.py`; `conf/ratings/shadow_operations_v1.yaml` | Candidate-v1 frozen evaluation and shadow runbook | Compatibility-only; candidate identity remains `ac1fba1` | After prospective records are fully dispositioned |
| `named-benchmark-compatibility` | `build_r2_prior_tournament.py`; `src/cks_picks_cfb/ratings/priors.py`; successor tournament config | Completed R2 result `r2-prior-20260904-4c6e610` | Preserve result and reproducibility subject to audit | Phase 4 after evidence audit and recertification |
| `named-benchmark-compatibility` | `generate_game_ordinal_candidates.py`, `evaluate_game_ordinal_predictions.py`, `conf/weekly_bets/v3_preview_games_ordinal_2026.yaml` | Direct early-game sealed result, tests, and committed-code identity | Preserve direct benchmark path | Phase 5 after forecast comparisons |
| `historical-evidence` | `docs/ops/rating_successor_research.md`, `docs/ops/rating_shadow_operations.md`; prior ratings plans/reports and existing successor configs | Completed R1/R2 and superseded R3/R4 sequence | Keep in place with authority banners to avoid link and reproduction breakage | Archive movement after Phase 1 lineage map |
| `future-removal-candidate` | `src/cks_picks_cfb/flows/` | Prefect-era flow imports and historical execution references require a complete audit | Current operations use `src/cks_picks_cfb/ops/`; confirm no external runner or artifact identity depends on flows | Phase 1 inventory, then a dedicated cleanup contract |
| `future-removal-candidate` | `src/cks_picks_cfb/features/v1_pipeline.py`, `src/cks_picks_cfb/models/v1_baseline.py`, `src/cks_picks_cfb/models/v2_*.py`; `conf/legacy/` and legacy experiment/feature configs | Historical training, tests, documentation, and possible bundle reproduction | Preserve until bundle readers and historical reproduction requirements are enumerated | Phase 1 lineage audit or after Phase 5 benchmark selection |
| `future-removal-candidate` | historical research entry points currently under `scripts/pipeline/` | Subprocess orchestration, tests, docs, and code identity manifests reference exact paths | Future commands use `scripts/research/`; existing paths need wrappers before any move | Phase 1 classification, then separate structural contract |

No listed future-removal candidate is approved for deletion. Recovery from
`b930066` is possible, but recoverability alone does not satisfy compatibility
or evidence-retention requirements.
