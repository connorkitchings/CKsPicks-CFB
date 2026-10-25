# Session log: serving parity and `rebuild/` retirement

- **Date:** 2026-10-22
- **Plan:** docs/plans/2026-10-22/02-parity-and-rebuild-retirement.md
- **Outcome:** Parity passed; the 6A/6B rebuild package is retired in one commit.

## Part A: serving parity

Command (main checkout, `dev` at `2274ee3d`, clean tree before and after):

```
CFB_STORAGE_BACKEND=r2 PYTHONPATH=src:. uv run python scripts/pipeline/run_season.py prepare \
  --model-manifest conf/season/2026/model_manifest_v1.json \
  --revision-manifest conf/season/2026/revision_manifest_w8_v3.json \
  --through-week 7 --next-week 8 --as-of 2026-10-20T14:39:00Z \
  --output <scratchpad>/parity --environment preview
```

Identity map (old active release to new run): release ID `125158328e025fb89c96ce0d` to `d3d6c0551d0036669bb3c32c`; code commit `e94cf35a` to `2274ee3d`; predictions SHA `de0aa5f4…` to `22c19171…`; publication payload SHA and its 12-character prefix (`a2f415c00c3b` to `18fea3bad05a`); verification SHA.

Result: normalized payload byte-identical (46,283,016 bytes), 24 tables with equal row counts (69,491 rows in the served rows), rating identity `724d891a…` and measurement identity `834ebe7a…` unchanged. 14 of 18 run files are SHA-identical; the four that differ embed the release ID or code commit.

Raw payload SHAs: active `eae0069973b9…`, new run `94b927339c6d…`.

## Part B: retirement (commit `605159cc` on `connorkitchings/retire-rebuild`)

- **Deleted:** `src/cks_picks_cfb/rebuild/` (22 modules); scripts `invariance_v2`, `invariance_frames_v2`, `rekey_admission_v2`, `build_v5_intended_update_forecasts`; modules `forecast/intended_update_bundle`, `ratings/admission_rekey`, `ratings/possession_selected_design`, `metrics/evidence`, `metrics/season_features`, `metrics/builders`; `register_partitioned_dataset_versions` in `data/catalog.py`; three unread `conf/rebuild` files; the listed rebuild, live-week, forecast and admission tests, plus `test_gold_evidence_and_features` and `test_team_game_metrics_builder`, which covered only deleted `metrics` modules.
- **Moved:** `conf/rebuild/bundle_b2_w5_v1.json` to `tests/fixtures/v5_bridge_b2_w5_v1.json`, SHA unchanged (`a507d0c7…`); readers repointed through `BRIDGE_FIXTURE` in `tests/season_fixtures.py`.
- **Kept:** `rebuild/6a` and `6b` R2 prefixes, `SIX_A_NAMESPACE`, `rebuild_root_v1`, manifest URIs, `tests/test_matchup_6a_bridge.py`, and research modules with callers (`ratings/admission`, `score_envelope_r1`, `drive_corroboration`, `metrics/ledger`, `forecast/replay_sources`).
- **Guard:** the only change under the prepare path is deleting `possession_selected_design.py`.
- **Gate:** ruff, contracts, quality and strict mkdocs pass; 2213 passed, 24 skipped, 0 failed; coverage 73.48% (floor 60%); zero-hit `rg`; `git diff HEAD --check` clean. The database suite on a local cluster was not run in this session.
