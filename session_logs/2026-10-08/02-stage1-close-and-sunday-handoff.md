# 2026-10-08 Stage 1 close and Sunday handoff (Terra implementation session, end)

Contract: [`04-stage1-week5-corrected-data-finalization.md`](../../docs/plans/2026-10-07/04-stage1-week5-corrected-data-finalization.md), Amendments 9-11 (status Implemented). Detail of the day's work: [`01-stage1-completion.md`](01-stage1-completion.md). Decision brief: [`01-stage1-decision-brief.md`](../../docs/plans/2026-10-08/01-stage1-decision-brief.md). Live state: [`docs/status.md`](../../docs/status.md).

## Outcome

Stage 1 is closed. The corrected lineage, the successor replay set (`20261008-c2`), the display-only Week 6 run (Preview), the signed packet builder, the artifact staging tool, the Week 6 waiver and the plan-driven 6B frame stages are all committed. Last commit `a1a1151f`, merged to `main` as `04cd53ce` (PR #4). Worktree clean at close.

## Decisions (user)

- Week 6: labeled display-only in Preview (Amendment 9); stays on the hold screen in Production (Option A). The Production site showing "Week 6 Picks Dropping Soon" is therefore expected, not a fault.
- Amendment 10: display-only Week 6 is excluded from the completed-prospective check so a Week 7 cutover can validate.
- Amendment 11: Task 7 delivered, contract set to Implemented, with the Production-namespace artifact check and CI confirmation moved to the cutover.
- Generalize the 6B week literals now; add the D7f test.

## Files changed this session (all committed)

Packet and staging: `src/cks_picks_cfb/ops/v5_packet_builder.py`, `v5_artifact_staging.py`, `v5_batch_selection_v2.py` (`DISPLAY_ONLY_WEEKS`), `scripts/pipeline/build_v5_cutover_packets.py`, `stage_v5_artifacts.py`. 6B: `src/cks_picks_cfb/rebuild/recon_*.py`. Publisher: `scripts/pipeline/publish_to_db.py` (`_selection_side`). Tests: `test_v5_packet_builder.py`, `test_v5_artifact_staging.py`, `test_recon_week_policies.py`, `test_publish_to_db.py`. Docs: contract 04, decision brief, 6B Week 6 plan template, `docs/status.md`, session logs, c2 evidence file.

## Validation

- Full Python suite with `-W error`: 2208 passed, 13 skipped (before the merge). `ruff format --check` and `ruff check` clean. `git diff --check` clean at close.
- **Not run locally:** the Postgres integration job (first run is CI on the merge to `main`; result not seen by me).
- **Not exercised:** a Week 6 6B run; a Week 7 packet with a real Week 5 prospective record; the staging CLI against real storage.

## Blockers and risks

- CI result on `04cd53ce` is unconfirmed. If `test_v5_batch_selection_v2.py` fails, the Week 6 waiver is the likeliest cause.
- No Week 6 market-sources lock exists; the d2 snapshot was captured after some kickoffs.
- The Week 7 freeze is due Oct 13 22:00Z; certification needs 24 hours of stable finals after Week 6's last kickoff (Oct 11 02:30Z). A missed deadline is a failed cutover.
- Rollback packets need authorizations for the old runs, which do not exist today (the builder takes their manifests as input).

## Next step (Sunday evening, after the Week 6 ingest lands)

1. Extend the lock; 6A and Task 4 rebuild through Week 6.
2. Week 6 market-sources lock for the successor chain.
3. Fill `docs/plans/2026-10-08/6b-w6-frames-plan-template.yaml`; run the frames-only 6B plan (`unserved_week_as_of` after Week 5's last kickoff, before Week 6's first).
4. Week 6 replay chain with provider names; pending Week 7 run (all Preview; each write needs a go-ahead).
5. Preview rehearsal of the cutover (stage, publish, score, certify, authorize, select, rollback) and the Week 7 packet spec.
6. User-run Production steps: stage artifacts, publish and score replays, publish Week 7, register authorizations, apply the selection packet.

Open register items outside this path: #8 prices, #11 line capture, #9 neutral-site model; matchup database gates.
