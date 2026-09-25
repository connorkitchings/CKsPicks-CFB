# V5 Complete Week 4 Replay Site Cutover

- **Status:** Approved
- **Created:** 2026-09-25
- **Planner:** Sol (plan-session)
- **Approval source:** The user requested a plan covering all Week 4 games and requiring scored V5 Weeks 1–3 site history (planning only), then approved execution on 2026-09-25 after reviewing the material-conflict summary with three explicit decisions: (a) the default Weeks 0–4 site view becomes clearly labeled V5 retrospective picks, with frozen V4 runs preserved, queryable, and the tested rollback; (b) this replay lane executes in parallel with the approved [Week 5 live plan](01-v5-week4-finals-to-live-preview.md), whose stabilized-finals gates take precedence when they open; (c) V5 Week 4 replay leans are graded against the frozen V4 pre-kickoff market quotes and labeled as replay grades (Amendment 1). This approval resolves the material release-policy conflict flagged in Current State; each production release still requires the separate Task 4 packet decision.
- **Implementation log:** Create `session_logs/YYYY-MM-DD/NN-v5-week4-replay-cutover.md` during execution.
- **Commit policy:** Separate plan commit recommended. The user executes Git operations.

## Goal

Make the public 2026 site select V5 for every week from Week 0 through Week 4, with Weeks 0–3 published and scored as clearly labeled retrospective history and a complete 58-game V5 Week 4 view. Week 4 can appear while its games are still underway; its run is scored only after all finals are certified, while any already certified game scores can appear through the shared results table. Preserve the frozen V4 Week 4 run and a tested same-week rollback. Do not wait for Week 5 to display V5 as the site's primary model.

This is a **retrospective/late-publication Week 4 release**, not a prospective V5 Week 4 forecast. The first Week 4 kickoff was 2026-09-24 23:30 UTC. At the 2026-09-25 15:11 UTC read-only checkpoint, one of 58 games had kicked off and no Week 4 final had been recorded. A present-day artifact cannot acquire a pre-kickoff Week 4 receipt by using a September 24 data cutoff or by withholding results. The site must expose the actual generation and publication times and classify all Week 4 V5 predictions conservatively as replay. Do not include Week 4 in live prospective performance.

## Current State and Material Conflicts

- The accepted V5 inference bundle is pinned at SHA-256 `f80b63ef01211bc9679b4b65769a3f16c7302c06cfa2b7806f6b8d830f19da0b`. The independently verified Weeks 0–3 replay contains 157 games and 314 paired targets with zero gaps. Preview serves and scores Week 0; Weeks 1–3 have not been published or scored as V5 site history. V4 remains public.
- A read-only Week 4 dry run reconstructed 58 games and 116 paired targets from verified Weeks 0–3 parents. It is not an immutable verified Week 4 replay or a frozen live Contract 09 artifact. Reconstructability must be rechecked against the exact Week 4 schedule and pre-slate source snapshot.
- Production V5 publication currently rejects `evidence_class=replay` in `scripts/pipeline/publish_to_db.py`; production selection rejects it in `src/cks_picks_cfb/ops/public_selection.py`. The exact `v5_serving_authorizations` table and release packet were designed for a verified live 09/05 forecast. A replay must never be passed through that live authorization by relabeling its evidence.
- The approved [Week 4 finals to live Preview plan](01-v5-week4-finals-to-live-preview.md), [Contract 09](../2026-09-18/09-v5-2026-forecast-and-readiness.md), [site cutover contract](../2026-09-22/04-v5-authority-simplification-and-site-cutover.md), and [weekly operator](../../ops/v5_weekly_operator.md) put the first live V5 slate after stabilized Week 4 finals. This plan proposes a separate replay release lane for site history. It does not amend the live 07/08/09/05 sequence or turn a late Week 4 prediction into live evidence. Approval of this Draft must explicitly resolve this material release-policy conflict before implementation. That approval was recorded on 2026-09-25; see Approval source and Amendments.
- The V4 production Week 4 run `2026w4-da5d98761831` is frozen with 58 predictions. Its scoring and audit trail must remain intact even if V5 becomes the selected site view.
- The existing `score-replay-week` operator requires complete certified outcomes for its whole run and writes one immutable scored artifact. Its DB scorer changes a published replay to `scored` in one operation. Incremental Week 4 scoring would require a separate versioned design; this plan uses a complete-finals gate instead.
- The current replay serving adapter passes no market snapshot and therefore produces no market leans. The existing `system_stats` recomputation draws grades from selected runs and does not separate replay from live. Copying V4 lines without rebuilding V5 leans and separating retrospective grades would misstate performance.

## Decisions to Review Before Approval

The proposed session sequence assumes three decisions that are **not yet recorded as approvals in this contract**:

1. V5 retrospective history may become the default public 2026 view for Weeks 0–4, with an explicit replay label and actual publication time. This does not imply prospective Week 4 evidence.
2. The replay work may proceed alongside the already Approved live Week 5 plan, but the live plan's finals gate and pre-kickoff deadlines take scheduling priority. Shared migrations, code checkpoints, DB operations, and public selection remain serialized.
3. Week 4 V5 replay market grades may use **independently verified, game-specific V4 frozen quote references** only when the underlying quote was captured before that game's kickoff and its exact value, source ID, and timing are recoverable. The V5 lean must be recalculated from the V5 prediction at that fixed line. Games without an eligible quote remain ungraded. These grades must be labeled retrospective and excluded from live bankroll/ROI or prospective metrics.

Approval must name these decisions and the exact plan path. Do not mark the Draft `Approved` from the proposed phase text alone. An exact production release packet and its later activation decision are still separate.

## Proposed Approach

Use the certified Weeks 0–3 replay for Weeks 0–3. Produce a separate, immutable Week 4 V5 replay from the fixed through-2025 inference bundle, verified ratings through Week 3, and a versioned schedule/input cutoff before the first Week 4 kickoff. Independently reconstruct all 58 paired predictions and prove no Week 4 results or post-cutoff measurements enter features. The Week 4 run's **publication timestamp is the actual execution time** and its `evidence_class` is `replay` for the whole slate, including games still upcoming when published.

Introduce a narrow, append-only **replay release authorization** bound to exact replay manifest, verifier receipt, prediction artifact, serving config, model bundle, season/week/run, and explicit decision reference. The restricted production pipeline role may read but not insert authorizations. Production replay publication and selection require that exact authorization and the usual environment/role guard. Keep the existing prospective authorization and readiness path unchanged. Historical selection must not claim that replay was frozen before kickoff. If decision 3 is approved, independently verify and bind eligible V4 frozen quote references to the Week 4 replay before deriving V5 market leans and grades. A quote that cannot be proven pre-kickoff for its game produces no grade. Completed-game forecast error remains available independently of market grades.

The user must review the actual Week 0–4 replay packet and Preview rollback evidence before the admin inserts any replay authorizations or the production selection changes. The request to plan Week 4 does not itself supply that exact release decision.

## Scope

### Included

- Reconcile 2025 V5 historical evaluation coverage with the eligible corpus and show it as historical research context only; do not silently invent 2025 V5 site runs. Audit 2026 Weeks 0–3 and Week 4 game populations against canonical schedules and outcomes.
- Publish, score, and select V5 Weeks 1–3 in Preview, then production under the new exact replay authorization; verify Week 0 production history too. Preserve truthful replay labels and distinguish completed-game scores from market grades.
- Build and independently verify all 58 Week 4 V5 predictions from pre-slate inputs, then rehearse, authorize, publish, and select the replay Week 4 run. Score the run after all 58 finals are certified without changing prediction bytes.
- Preview and production checks for explicit week selection, current-week consistency, performance classification, V4 fallback, and selected-run health.
- If decision 3 is approved, version-bound market quote reuse, V5 lean recomputation, separate retrospective grade presentation, and protection of live `system_stats`/ROI from replay grades.

### Excluded

- Any claim that the Week 4 V5 artifact was generated or frozen before its first kickoff; prospective Week 4 evidence, backdated timestamps, or silently omitting its already-started game.
- Refitting V5 on 2026 outcomes, modifying accepted model mathematics, or using Week 4 results in Week 4 features.
- Removing the V4 run, changing its frozen picks, or including V4 outcomes in a V5 performance aggregate.
- Retiring V4 execution before the separately required successful V5 live publish/freeze/close cycle. The existing post-Week-4 Week 5 live plan remains active.

## Affected Components and Contracts

- Replay source and serving producers: `scripts/pipeline/build_v5_replay.py`, `scripts/pipeline/generate_v5_replay_weekly_bets.py`, the verified source loader, and V5 serving config. Extend them only as needed for a Week 4 target constructed from Week 3 state and exact point-in-time inputs; do not regenerate earlier frozen replay bytes.
- Publication, scoring, selection and release: `scripts/pipeline/publish_to_db.py`, `scripts/pipeline/score_weekly_bets.py`, `scripts/pipeline/score_to_db.py`, `src/cks_picks_cfb/ops/public_selection.py`, the ops controller, `src/cks_picks_cfb/ops/v5_release.py`, shared SQL/TypeScript contracts, and an append-only migration for replay authorization. Use migration `0015` only if it remains the next available version at implementation time.
- Site: selected-week queries, forecast and performance pages, model/evidence labels, health endpoint, and current-week handling in `web/`.
- Documentation: this plan is a proposed material amendment to the production replay policy of the product transformation and cutover contracts. Keep the existing live release contract and Week 5 execution plan distinguishable.

## Implementation Tasks

### 1. Freeze the factual Week 4 input boundary

Inventory the canonical 58-game FBS-versus-FBS Week 4 slate, kickoff times, and pre-first-kickoff schedule version. Verify the exact certified Weeks 0–3 07/08 parents, their 157-game coverage, and the through-2025 bridge and inference bundle. Reconstruct Week 4 features and 116 predictions independently. Prove no Week 4 game outcome, measurement, rating update, or post-cutoff source enters a Week 4 feature. Log actual artifact creation time separately from the source cutoff. Review preflight, establish a clean committed code checkpoint, then apply and verify a **new** immutable Week 4 replay in Preview R2 under a distinct identity; do not alter the Weeks 0–3 replay. If any game or source cannot be reconstructed, stop; do not quietly narrow the slate.

**Acceptance:** 58 unique games, 116 paired target rows, zero unexplained gaps, exact parent and source SHAs, independent prediction equality, and an explicit late-publication/replay finding.

### 2. Implement and test exact production replay admission

Design an append-only replay authorization migration separate from the live 09/05 authorization. Bind one environment/season/week/run to exact immutable replay and verification bytes, prediction artifact and config SHAs, model/bundle identity, decision reference, and approval timestamp. Give the pipeline role SELECT only and the web role no authorization access. Require the restricted production login as both `session_user` and `current_user` at replay publication and selection. Reject missing, mismatched, duplicated, or wrong-environment authorization before any write. Keep live authorization semantics and V4 fallback intact. Record the explicit contract amendment before the code checkpoint. Rehearse migration and grant checks in Preview. Before a production migration, recheck the migration chain, commit the reviewed file, apply only the expected next migration with the admin role, and read back unchanged V4 serving state and role privileges.

**Acceptance:** Negative tests leave zero writes for unapproved or mismatched replay; a matching authorization admits only its exact replay run. Live runs still require the existing exact 09/05 record, and replay cannot satisfy readiness or prospective gates.

### 3. Complete and rehearse 2026 retrospective history on Preview

Using the already verified Weeks 0–3 replay, publish, score, and explicitly select Weeks 1–3 under stable run and pipeline identities; this work can start while the new Week 4 replay and migration are being prepared. Recheck Week 0's selected scored V5 run. Reconcile each week's predictions and completed outcomes with its canonical game population. If decision 3 is approved, audit the source quote identity, value, capture time, and game kickoff individually. Recompute V5 market leans at eligible fixed lines and bind their exact snapshot IDs; never import V4 picks or grades. Publish the new Week 4 replay on Preview, with all 58 predictions and pending results where games are unfinished. Exercise exact week selection, current-week view, ratings, performance separation, health, and a same-week switch to the frozen V4 Week 4 run and back. Verify page text does not say all replay predictions were created after their games when some Week 4 games were still future at publication. Capture run IDs, receipts, timestamps, response/page evidence, and rollback time.

**Acceptance:** Preview shows V5 for each Week 0–4 week, Weeks 0–3 have complete score coverage, Week 4 has 58/58 predictions with honest replay labeling, and V4 Week 4 rollback succeeds. Any Week 4 market grades use audited eligible quotes, carry a distinct retrospective grading version, and do not enter live `system_stats`/ROI. No prospective Week 4 metric is recorded.

### 4. Prepare and review the production release packet

After clean-code and migration reviews, independently verify the replay source, serving config, prediction artifacts, schedule population, and Preview evidence. Prepare exact authorization rows for Weeks 0–4 and a proposed selection order: completed Weeks 0–3 first, then Week 4. Verify production policy/model identity, role privileges, and that the V4 Week 4 run remains frozen. Present the packet, including actual prediction generation/publication timestamps and the missed Week 4 prospective boundary, for a **separate approval decision**. No authorizations or selection writes occur before that decision.

**Acceptance:** One reviewable byte-bound packet per selected week, negative guard checks, proven V4 rollback, and an explicit decision on retrospective production publication.

### 5. Release, score, and monitor under the approved packet

Only after the exact decision, insert replay authorizations with the admin role and use the restricted production wrapper to publish/score/select the approved runs. Confirm Weeks 0–3 show V5 results and Week 4 shows all 58 V5 forecasts, pending or final scores by game, and actual replay timestamps. Preserve the V4 frozen run and score it by explicit run ID through its existing path. Once **all 58 Week 4 finals are certified**, score the V5 replay idempotently from one immutable outcomes reference without rewriting predictions; the existing scorer must not mark a partially completed run `scored`. Keep the separate live Week 5 preparation path and its stabilized Week 4 gate. If that gate opens during replay work, pause replay at an atomic checkpoint and prioritize the live forecast's pre-kickoff work; never interleave migration, authorization, or selection writes between the lanes without reconciling exact state.

**Acceptance:** Public selected-run health, browser pages, selection history, V5-only 2026 season view through Week 4, truthful replay/live performance split, and a tested production V4 fallback. V5 Week 4 is not called fully scored until all 58 certified finals are present.

## Validation

- Focused replay source, schedule/cutoff, paired-coverage, publication, role/authorization, selection, scoring, and rollback tests, including changed artifact bytes, wrong week, wrong branch, owner/migrator/web login, `SET ROLE`, duplicate authorization, one already-kicked-off game, incomplete finals, invalid/post-kickoff quotes, and replay grades leaking into live stats.
- Migration rehearsal on an isolated Preview database, shared `make contracts-check`, scoped Python tests and Ruff, web lint/typecheck/build, and real Preview browser/health checks.
- Production readback of immutable artifact SHAs, replay authorization rows, run states, predictions, results, selected-week history, `current_week`, and unchanged frozen V4 picks. Strict MkDocs build and `git diff --check`.
- At each operational checkpoint, verify R2 backend and exact Preview/production credentials without printing secrets. No `./data/` fallback.

## Risks and Stop Conditions

- A September 24 source cutoff is a data-leakage control, not evidence that the forecast existed before kickoff. The actual creation/publication time must remain visible and immutable.
- The existing replay builder is tied to the verified Weeks 0–3 artifact. It may require a new Week 4 replay type or input adapter; never overwrite the Weeks 0–3 replay or treat a dry run as an immutable release.
- If the first-game result enters any Week 4 input, the Week 4 source fails. If the 58-game schedule cannot be reproduced as it stood before kickoff, stop the full-slate release and seek a reviewed amendment.
- If production replay authorization cannot be made distinct from the live 09/05 gate, stop. No blanket replay toggle or production role privilege expansion.
- Production activation and V4 retirement remain separate decisions. Do not mark the V5 live forecast/readiness or the existing Week 5 plan complete from this replay site release.
- The V4 Week 4 freeze timestamp alone does not prove that every quote was captured before its game's kickoff. Audit each quote timestamp and source version. An absent or ineligible quote remains ungraded even if V4 displayed a line.

## Definition of Done

- [ ] Material release-policy amendment approved before implementation; exact authorization design reviewed.
- [ ] 2025 historical research coverage audited and represented honestly; Weeks 0–3 V5 site history complete, scored, and selected.
- [ ] All 58 Week 4 V5 predictions independently verified from pre-slate inputs and labeled replay with actual timestamps.
- [ ] Preview publication, scoring, page checks, and V4 Week 4 rollback proven.
- [ ] Exact production replay packet reviewed and separately approved; only then are Week 0–4 replay authorizations and selection applied.
- [ ] Public V5-only 2026 view through Week 4 verified; V4 frozen run preserved; Week 4 retrospective scoring completed after certified finals.
- [ ] Focused validation, documentation, and implementation log complete; status changed to `Implemented` only after every item passes.

## Amendments

This plan was a proposed material departure from the approved first-live-slate and production replay policies; implementation was stopped until the conflict was explicitly approved through this contract, which occurred on 2026-09-25 (see Approval source). Any change to the 58-game population, evidence label, point-in-time source boundary, release authorization, or public scoring semantics requires another reviewed amendment.

### Amendment 1 — Week 4 replay market grades (2026-09-25)

The plan left Week 4 market grades optional ("may be absent if there are no legitimate point-in-time quotes"). The frozen V4 Week 4 run `2026w4-da5d98761831` captured timestamped pre-kickoff market quotes for all 58 lined games. The user approved grading V5 Week 4 replay leans against exactly those frozen quotes, displayed and recorded as replay grades and never counted as live or prospective performance. This introduces no feature leakage: V5 consumes no bookmaker data, the quotes predate kickoff, and the predictions keep their replay evidence class and actual publication timestamps.

### Amendment 3 — Weeks 0–3 replay grades vs frozen quotes (2026-09-25)

During production execution the user extended Amendment 1's frozen-quote grading to the Weeks 0–3 V5 replay leans, using the same mechanism (each week's frozen V4 pre-kickoff quotes, frozen-line rule, replay-labeled grades, never prospective). Reason: selecting ungraded V5 weeks would show a 0–0–0 public season record until Week 4 grades land, while legitimate point-in-time quotes exist for every completed week. V5 consumes no bookmaker data, so this introduces no leakage.

### Amendment 2 — no row locks on authorization reads (2026-09-25)

Production execution proved that `SELECT ... FOR SHARE` requires write privilege on this Postgres, so the restricted pipeline role (SELECT-only by design) cannot take row locks on either authorization table. Both `require_release_record` and `require_replay_release_record` now read without a locking clause; this was blocking every authorized production V5 write, including the previously approved live path. Integrity is unchanged: both tables are append-only with no concurrent writer in any approved flow, and every record is revalidated byte-for-byte against R2 inside the publication/selection transaction. Covered by a dedicated no-locking-clause regression test.
