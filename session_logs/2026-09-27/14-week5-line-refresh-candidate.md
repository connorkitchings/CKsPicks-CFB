# Session: Week 5 complete-line refresh and production release

## TL;DR

- **Worked On:** Captured fresh Week 5 CFBD markets, reconciled a new Preview run, prepared the exact production artifact and packet, then completed the user-authorized release.
- **Outcome:** Production now selects `2026w5-5d436e58c072`: 56/56 predicted and lined games, with both spread and total selections for every scheduled FBS game. Public health is `ok`, and the homepage renders 56 of 56 games.
- **Plan Contract:** N/A (authorized weekly market refresh under the V5 operator checklist).
- **Approval / Status:** The user explicitly authorized exact run `2026w5-5d436e58c072` after reviewing the complete-line packet and the prior V5 run as rollback. Admin authorization `v5-live-2026w5-752bc5af` was inserted; the restricted pipeline role published and selected the run. No freeze occurred.
- **Blockers:** None for publication. Final market refresh and freeze remain due before kickoff.
- **Next:** Recheck both line types against the full schedule before freeze, then freeze the reviewed run within the one-hour pre-kickoff boundary. Close and score after certified finals stabilize.

## Context and Decisions

- Verified the clean committed checkout at `54ebded1282aea20bf6ee18776ad0f09620bf39e` and the task's R2 and Preview credentials without exposing values. The first sandboxed command could not access the uv cache or Keychain; the restricted Preview wrapper succeeded with approved host access. No repository `./data/` path was used.
- A Preview `publish-week` pipeline run `5d436e58c072419bb20760aa26e4c795` used the V5 serving config and cutoff `2026-09-27T22:05:00Z`. Its CFBD betting-lines request was captured at `2026-09-27T21:46:12Z` as capture `b09eaaebe3e94f9282e61352890d63a6`: 59 provider games, 56 matching the FBS schedule, 56 captured rows. The cutoff is the inclusive upper bound; the actual market capture occurred at the recorded earlier time.
- The new Silver `market_quotes` version `c5eed77a7646bff4013b61a9` and `market_snapshots` version `68521c6723201011e731cf8e` are validated, with 56 rows each. The Preview games table contains 56 Week 5 IDs. The candidate contains exactly those 56 IDs, 56 non-null spreads, 56 non-null totals, 56 snapshot IDs, and 56 quote selections for **each** target. Missing IDs: none at source, Silver, or Preview serving.
- Preview artifact `artifacts/preview/predictions/year=2026/week=5/run_id=2026w5-5d436e58c072/predictions.csv` and production artifact `artifacts/production/predictions/year=2026/week=5/run_id=2026w5-5d436e58c072/predictions.csv` are byte identical, SHA-256 `752bc5af95f90d53853753394938c3114590120b32dbfe9e67a509eeae3e9fb4`. The serving config SHA is `ec174ca1fd383649df2f75a273d7a2202219ad4234406173d505e0dbca22459e`; inference bundle SHA is `f80b63ef01211bc9679b4b65769a3f16c7302c06cfa2b7806f6b8d830f19da0b`.
- Exact authorization `v5-live-2026w5-752bc5af` used `decision_ref=user-authorized-2026-09-27-week5-line-refresh-2026w5-5d436e58c072`. The approved packet is saved outside the repository at `/tmp/v5-week5-line-refresh-approved-release-record.json`; the read-only validator returned `{"valid": true}` against the signed Week 5 forecast and verified ready receipt before admin insertion.
- At `2026-09-27T21:55:06Z`, a fresh read-only CFBD request again found 56 scheduled FBS games with both spread and total lines; missing IDs were empty for both targets. No newer source coverage required rebuilding the immutable candidate.
- Before release, production had only the earlier Week 5 V5 run. The user accepted reselection of `2026w5-d6366e59fd43` as the immediate rollback for this V5-to-V5 line refresh. No same-week V4 run exists in production; V4 frozen historical runs remain available but do not cover Week 5.
- The first Week 5 kickoff is `2026-10-02T00:00:00Z`. The next operator-run source check is due by `2026-09-28T12:00:00Z` and again immediately before freeze. No automatic refresh was scheduled.

## Work Completed

- Executed Preview `publish-week` through the restricted Preview wrapper; every pipeline step succeeded, including source capture, Silver snapshot, prediction, and Preview activation.
- Reconciled exact schedule, prediction, spread/total lines, snapshots, quote selections, source capture, and validated Silver counts by read-only Preview queries.
- Ran production `generate_weekly_bets.py --prepare-only` through the restricted production wrapper, then compared the immutable Preview and production prediction bytes.
- Assembled the exact packet from the existing release lineage with the new run and artifact identity, recorded the user's release decision, and revalidated it read-only.
- Inserted one exact authorization as `neondb_owner`, after checking the existing production Week 5 run and authorization. Published the immutable artifact through `cks_prod_pipeline`; publication atomically selected the new run and triggered on-demand page revalidation.
- Confirmed production `current_week` and `site_week_selections` both point to the new run. Production stores 56 predictions, 56 non-null spreads and totals, 56 snapshots, and 56 quote selections for each target. `/api/health` returned `status: ok`, active run `2026w5-5d436e58c072`, coverage 56/56/56; the homepage returned HTTP 200 and rendered “Showing 56 of 56 games.”
- Checked GitHub CI for committed HEAD `54ebded`: [run 36352736685](https://github.com/connorkitchings/CKsPicks-CFB/actions/runs/36352736685) succeeded, including Python tests, Python lint/contracts, and Web. The earlier failed run was superseded.

## Files Modified

- `session_logs/2026-09-27/14-week5-line-refresh-candidate.md` — this evidence and handoff record.
- `AGENTS.md`, `.codex/QUICKSTART.md`, `README.md`, `docs/plans/index.md`, `docs/modeling/v5_status.md`, `docs/ops/weekly_pipeline.md`, `docs/ops/production_runbook.md`, `docs/ops/v5_weekly_operator.md` — current release status and same-week rollback guidance.

## Validation

- [x] Preview pipeline receipt: all steps succeeded.
- [x] Source → Silver → serving reconciliation: 56 scheduled games, 56 captured, 56 quotes/snapshots, 56 predictions, 56 spread and 56 total selections; no missing game IDs.
- [x] Preview and production prediction artifact bytes and SHA match.
- [x] `validate_v5_release_packet.py --kind live`: valid exact approved packet.
- [x] Fresh source read-only check at `21:55:06Z`: 56 spread and 56 total games, no missing IDs.
- [x] Production authorization, selected run, prediction coverage, quote selections, `/api/health`, and homepage readback.
- [x] Current committed CI Python tests and other jobs successful.
- [x] `git diff --check`; the new log also has no trailing whitespace.

## Amendments and Blockers

The first direct publisher attempt stopped before database writes because `PYTHONPATH=src` omitted the repository root needed by `scripts.pipeline.generate_v5_weekly_bets`. Retrying with `PYTHONPATH=.:src` succeeded. The production database contains one new authorization and one new published, selected run. Week 5 has no same-week V4 production run; the prior V5 run is the recorded immediate rollback.

## Handoff Notes

- **Resume at:** Recheck market source coverage, prepare any needed new immutable run if lines change materially, then freeze the selected reviewed run before the first kickoff gate. Close and score after finals stabilize.
- **Watch out for:** Freeze requires a final fresh capture and the one-hour pre-kickoff boundary. The packet file is in `/tmp` and may need regeneration after a host restart.
- **Suggested commit message:** `Record Week 5 complete-line production refresh`

**tags:** ["v5", "week5", "market-lines", "preview", "production", "release"]
