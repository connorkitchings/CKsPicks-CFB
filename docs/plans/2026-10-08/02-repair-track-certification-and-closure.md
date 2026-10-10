# Repair-track certification and closure

- **Status:** In Progress
- **Approval:** User explicitly requested implementation of the complete updated plan after `04cd53ce` in this chat. This contract persists that approved scope; it does not authorize automatic Production activation.
- **Baseline:** `04cd53ce`; Stage 1 is closed. B2 successor chain, provider names, packet/staging tools, display-only Week 6 and frame-week policies already exist.
- **Implementation log:** `session_logs/2026-10-08/02-repair-track-certification.md`
- **Commit policy:** User-run commits; preserve unrelated work. No automatic merge, deployment or serving change.

## Goal and constraints

Complete the October 4 data-repair objective, independently certify the corrected chain, and prepare the Week 7 cutover. A separately approved limited release does not close this track. All six quality follow-ups and all incorrect values must be resolved for closure; verified missingness with correct exclusion and disclosure is acceptable. Retain the model design, B2 production fitting recipe, original prospective evidence and immutable source history. Do not include 2020 or fit/tune on 2026 outcomes.

## Ordered work and acceptance

1. Read c2 directly from R2: verify manifests, parent hashes, B2 bundle, predictions, selections, grades and release inputs. Replace scratchpad-only evidence; retain B1/c1 as superseded. Verify exact-commit CI/database jobs and deployed revisions. Run Production staging dry run and verify namespace, identity, bytes and rollback sources.
2. Exercise a successful Week 7 packet with verified Week 5 prospective evidence. Prove Week 6 cannot enter the prospective record, freeze or close; no other week is exempt. Preserve Week 5 exactly.
3. Add a seven-week integration fixture. After Week 6 certified finals stabilize, ingest/pin sources, extend 6A and Task 4, and build Weeks 0–6 frames. Preserve earlier content unless an attributed revision explains a change. Use successor B2 for Week 6 reconstruction, independently verify outcomes/quotes/grades/completeness/certification, and never fabricate an original run or post-kickoff historical quote. Do not use the original-run reconciliation stages for an unserved week.
4. Build pending Week 7 with fresh coverage. Rehearse Preview authorization, staging, selection, freeze, readback, rollback and matchup database gates against corrected snapshots/statistics. Production remains a separate exact decision; missed kickoff requires a revised operating decision.
5. Complete independent expected-request inventory (including never-scheduled requests), ingestion enforcement, ambiguous-version resolution, Gold checks/Silver receipts, blocking policy, durable receipts and legacy validation disposition. Resolve duplicate-play loss and scoring defects; independently verify all metric populations and values, reconcile the 95 database-only adjusted rows by key, complete 2025 matchup backfill, and add database-level null-lean publication coverage.
6. Reconcile status, decision brief, issue register and contracts into one completion matrix distinguishing delivered code, published artifacts, Preview selection, deployment and Production activation.

## Interfaces and validation

Retain delivered plan policies and packet/staging CLIs; add only needed Week 6 certification integration, with no public API redesign. Validate wrong bundle/parents, time boundaries, missing and conflicting sources, ambiguous pins, zero versus missing PPA, duplicate plays, null leans, seven-week operation, display-only exclusions and successful packet application/rollback. Run focused tests as each component changes, then applicable full Python/contract/web checks and exact-commit CI, including warnings-as-errors and database integration. Cloud evidence requires readback and idempotence; hashes alone do not prove numerical correctness.

## Completion matrix

**Reconciled 2026-10-10:** this matrix is the current obligation map. It incorporates Amendments 2–9 and supporting contracts without changing acceptance, approval or release gates. Historical decisions and amendments below remain intact. Code, candidate artifacts, Preview selection, deployment and Production activation are separate states; documentation consolidation closes none of them. Live serving facts remain in [Current Status](../../status.md).

| Requirement | State | Evidence / next gate and originating scope |
|---|---|---|
| Direct corrected replay readback and B2 certification | Verified for the recorded candidate lineage | 408 objects and six serving recomputations in `repair-track-evidence/`; Amendment 3 approves keeping B2 without refit. Changed descendants still need recertification. |
| Exact-commit CI, database integration and deployed revision | Historical baseline verified; current release checks open | Baseline evidence below is dated. Verify the exact release commit and deployed revision, including database integration; [Stage 1](../2026-10-07/04-stage1-week5-corrected-data-finalization.md), Amendment 11, and [Stage 7B](../2026-10-06/02-stage7b-exact-release-and-cutover.md). No fresh CI/deploy verification was performed by this cleanup. |
| Production namespace staging and exact rollback/readback | Partial | Earlier six-replay staging dry run passed without writes; verify complete packet inputs, bytes, restored before-state and matchup rollback during the real rehearsal. [Stage 7B](../2026-10-06/02-stage7b-exact-release-and-cutover.md), steps 3–5. |
| Week 5 original freeze provenance; Week 6 never frozen/closed | Packet smoke verified; real apply still open | Amendment 7 validated the packet against real Week 5 attestation and registered rollback rows. Preserve that evidence unchanged; Week 6 remains excluded from freeze provenance, while its eligible grades count in the unified record under Amendments 8–9. |
| Seven-week integration and complete Week 6 reconstruction | Tooling/fixtures delivered; live execution open | Stabilized finals (24 h), new pins, 6A/Task 4/6B extension, source-identity check, attributed earlier-week changes and independent replay certification remain required. [Run sheet](../2026-10-10/01-week7-cutover-run-sheet.md), steps 1–6; no complete Week 6 replay is certified yet. |
| Passing point-in-time receipt covering every selected run | Partial; Week 6 blocked | Amendment 9 passes 271 corrected Weeks 0–5 candidate games; the existing display Week 6 fails cutoff/state binding and complete coverage. Rebuild all 58 forecasts with the required forecast boundary, record both cutoffs and audit the exact proposed runs before packet creation. Passing candidates do not certify the older served runs. |
| Market coverage and late-quote admission | Lock tooling delivered; fresh coverage required | Amendment 7 delivered the Week 6 lock. Amendment 9's CFBD comparison matched 19/59 lines and failed acceptance; the three early games remain ungraded verified gaps. A declared exception needs a passing empirical receipt. Reconcile fresh spread/total sources against the complete schedule; [run sheet](../2026-10-10/01-week7-cutover-run-sheet.md), steps 3 and 8. |
| Preview approval alignment and registered rollback evidence | Read-only rows checked; owner update/readback open | Amendment 7 records the Preview/Production first-live-week mismatch. User-run Preview alignment and fresh row export/readback are required before rehearsal; no SQL was applied by this cleanup. Existing registered authorizations are carried unchanged, not fabricated. |
| Pending Week 7 and full Preview cutover rehearsal | Open | Exact prior authorization, guarded atomic selection/statistics/current-week apply, pre-kickoff freeze, corrected matchup repin, query/cache readback, owner-login rollback and re-apply. [Stage 7B](../2026-10-06/02-stage7b-exact-release-and-cutover.md), step 4, and run-sheet step 9. Fixtures/smoke validation do not establish a successful live rehearsal. |
| Separate exact Production decision and complete cutover receipts | Open | Review the actual Production-bound packet only after Preview passes. Recheck drift, identity, authorization, timing and before-state; retain apply/freeze/repin/readback/rollback evidence and then update status. [Stage 7B](../2026-10-06/02-stage7b-exact-release-and-cutover.md), step 5. |
| Week 6 display-release verification/configuration follow-through | Open supporting close-out | [Week 6 release](../2026-10-09/02-week6-display-production-release.md), Task 6 and Amendment 7. Status records user-confirmed deployment/live verification; reconcile remaining local/live checks and `CFB_DISPLAY_ONLY_NOTICE=0` evidence before closing Task 6. No configuration or live check was performed here. |
| Week 6 post-finals grades-only backfill and bookkeeping | Open; stable finals required | [Week 6 release](../2026-10-09/02-week6-display-production-release.md), Task 7, and run-sheet step 2: user-run Preview then Production, parity/readback and backups, pending display run never frozen/closed. Corrected replay replaces it only at the separately approved cutover. |
| Quality follow-up 1: ingestion checks and retained capture evidence | Partial | Schedule inventory/request checks are code increments; wire completeness, unmatched-odds and schema inputs before writes, enforce checks, retain failed captures and odds evidence. [Quality contract Amendment 3](../2026-10-04/01-pipeline-data-quality-gates.md#amendment-3-tasks-5-and-6-delivered-items-still-open-2026-10-04), item 1; ordered work 5 above. |
| Quality follow-up 2: ambiguous dataset/version review | Partial | Review all five originally unpinned families: outcomes, legacy market references, offseason context, schedule revisions and team aliases. Reader guards alone do not close the review. Quality Amendment 3, item 2; ordered work 5. |
| Quality follow-up 3: Gold checks and Silver builder receipts | Partial | Complete checks and durable builder-emitted evidence, including actual score/box comparisons and missing-column refusals. Quality Amendment 3, item 3; [two-window prevention gates](../2026-10-03/04-data-integrity-two-window-implementation.md#prevention-gates). |
| Quality follow-up 4: reviewed blocking policy | Partial | Required-check policy exists; builders must enforce the reviewed policy and prove refusals. Preserve explicit `warn`/`--require-check` and request-inventory semantics. Quality Amendment 3, item 4; ordered work 5. |
| Quality follow-up 5: durable release-adjacent receipts | Partial | Retain R2 receipts beside immutable release evidence and verify readback. Local receipts and opt-in readback code alone are insufficient. Quality Amendment 3, item 5. |
| Quality follow-up 6: legacy validation disposition | Open | Record the reviewed disposition of `utils/validation.py`, preserving required validation behavior. Quality Amendment 3, item 6. No code is retired by this documentation cleanup. |
| Provider-keyed play identity; scoring and full metric correctness | Identity verified; scoring/full metrics open | [byplay_v2 Tasks 1–6](../2026-10-09/01-byplay-v2-play-identity.md) and Amendment 2 retain the census, invariance proof and discrepancy ledger. Resolve scoring defects and independently verify every population/value; retain missingness and documented exclusions rather than fabricate attribution. [Data appendix](../2026-10-03/window2/data-contracts-and-certification.md) remains normative. |
| Descendant statistics/matchup recertification and 95 adjusted rows | Open | Amendments 2–3 retain B2 but do not close v2-derived season stats, snapshot companions or matchup features. Reconcile the 95 database-only adjusted rows by exact key, explain every delta, pin corrected parents and independently verify affected descendants/serving payloads. [Two-window Task 8](../2026-10-03/04-data-integrity-two-window-implementation.md#task-8-matchup-and-issue-completion). |
| 2025 historical matchup backfill | Open; final separately gated step | [Matchup contract Task 8 Phase B](../2026-10-02/01-matchup-data-layer-v2.md#task-8-backfills-preview-first) and two-window Task 8 retain full parity, historical-replay labels and Preview/Production lineage verification after corrected selection. Cutover alone does not close Window 2. |
| Null-lean database regression | Verified locally | Real PostgreSQL publication with quoted null/No Bet rows and valid controls; legacy model exercises shared persistence, not V5 authorization. No broader live-apply claim. |
| Documentation/issue reconciliation | Obligation map delivered; operational close-out open | This cleanup maps existing acceptance only. Reconcile issue-register dispositions, close-out receipts and verified status as their owning tasks actually complete; [Stage 7B definition of done](../2026-10-06/02-stage7b-exact-release-and-cutover.md#definition-of-done). |

### Supporting ownership outside repair closure

| Scope | Owner / preserved acceptance |
|---|---|
| Product/workflow completion | [V5 Product Transformation](../2026-09-23/01-v5-product-transformation.md): retain unresolved production-API extraction, scheduler/retry/idempotence, product coverage and dependency/recovery-checked retirement acceptance unless later evidence closes it. V4 remains the rollback; cleanup does not authorize retirement. Repair release obligations map above. |
| Ongoing evidence monitoring | [Contract 06](../2026-09-13/06-v5-prospective-evidence-and-recommendation.md), Amendment 3: immutable attempts/freezes, stabilized outcome reports and independent authentic-quote diagnostics; six slates are a monitoring milestone, not a launch gate. The unified record does not fabricate freeze provenance. |
| Investigation and stats/matchup supporting specifications | [Investigation Amendment 3](../2026-10-03/02-week5-data-issue-investigation.md#amendment-3-sweep-phase-g-and-delta-added-2026-10-03) records A–F/G findings and the [decision packet](../2026-10-03/03-data-decision-packet.md); no original unchecked box is silently closed here. D1–D4 repair obligations, shared Gold metric consumers, missingness and descendant certification map above under the [two-window contract](../2026-10-03/04-data-integrity-two-window-implementation.md). [Team-stats Phase 2](../2026-10-02/03-team-stats-feeds-ratings.md#phase-2-design-built-at-the-planned-rating-rebuild) is absorbed into that scope; intended-update projection dispatch remains documented by the [matchup contract](../2026-10-02/01-matchup-data-layer-v2.md), not silently implemented by this cleanup. |
| Artifact preservation and pruning | [Local-artifact archive](../2026-09-27/03-archive-unique-local-artifacts.md): lifecycle proof, approved eight-file prune and report remain independently gated; all 11 backups and local candidates are preserved here. |
| Architecture and separate model research | [Production-boundary draft](../2026-10-01/04-production-boundary-refactor.md) retains its own approval and boundary/equivalence tests. The two-window exclusions retain neutral-site model research as separate scope; no refactor or model change is authorized here. |
| Post-cutover documentation work | Physical historical-plan archival and weekly-runbook merger are deferred to Week 8 steady-state after repair/cutover closure, with separate reviewed scope. Existing paths and commands remain unchanged. |

## Decisions (2026-10-08 review)

- **Release gating:** the October 9 user direction supersedes the earlier limited-release proposal for this execution: integrity closure precedes this cutover. Corrected Production activation still requires a separate exact decision.
- **Week 7 checkpoint:** Sunday Oct 11 evening. If the successor Week 6 certification integration is not built and tested by then, move the cutover to Week 8; no gate is compressed.
- **Open, recommended default:** build rollback authorizations for the old runs as part of the Preview rehearsal (none exist today).
- **Open, recommended default:** Week 6 games whose only quotes are post-kickoff (the d2 snapshot was captured after some kickoffs; no Week 6 market-sources lock exists) are verified gaps with no selection or grade.
- **Quality gates:** Gold checks start at `warn`; releases promote them with `--require-check`. Requiring `ingest.capture_completeness` needs `--request-inventory`; without one the check uses the attempt ledger and is labelled `request_basis = attempt_ledger`.

## Amendment policy

Record mechanical findings here without changing acceptance. Material model, lineage, release, or evidence-policy changes require a new decision; never weaken a gate merely to finish. Mark Implemented only after all closure requirements pass. If future source availability prevents execution, retain In Progress and record the exact resume gate.

## October 9 implementation direction

The user approved the complete repair-track plan in this chat and chose integrity
closure before release timing. Continue actionable repairs even when Week 6 finals
are pending. Stage 1 remains closed. Preserve the B2 fitting recipe rather than
assuming its currently verified artifact bytes will survive corrected inputs.
Every changed measurement requires a recorded downstream impact decision and
recertification of affected ratings, forecasts, selections, grades and matchup
data. The Week 7 target is conditional on correctness and the existing kickoff
gates; missing it requires a revised operating decision.

On October 9, implementation added a schedule-derived expected-request inventory
and R2 readback path, strict weekly
request/capture comparison for completed games, a Silver reader ambiguity guard,
and exact population keys in published comparisons. A draft source-identity play
change remains unapplied pending a `byplay_v2` contract. A checksum-verified census
of all pinned Bronze play captures confirmed the 28 distinct-ID sequence
collisions; descendant impact analysis remains open. The current Week 5 Silver games
artifact lists 56 FBS–FBS games and omits three FBS–FCS games that the ingesters
request. A byte-pinned `raw/games/year=2026/part-0.parquet` inventory covers all
59 and matches both real request enumerators on readback. Raw schedule mutation
invalidates its digest and blocks reuse.

The collision pairs show period reuse, not simply repeated rows: 25 of the 27
2025 groups cross regulation and overtime periods. The current dedup would remove
24 regulation plays from these groups, including candidates with PPA and scoring
data. New `byplay_v1` builds now reject such a source population before deriving
values; this is a protective gate, not a corrected rebuild. `byplay_v2` must
carry provider identity, and the downstream drive,
possession, scoring-event and ordering contracts must be reviewed together.
Neither provider IDs nor same-numbered positions alone establish event order;
unresolvable attribution must remain missing and excluded rather than be sorted
into a fabricated sequence.
These are code-level increments. No corrected datasets were rebuilt and no
six-follow-up or numerical closure is claimed. The new work's log is
`session_logs/2026-10-09/01-repair-track-integrity.md`.

## Certification evidence and limits (2026-10-08)

The `repair-track-evidence/` directory replaces scratchpad-only c2 claims with
fresh immutable-object readback. The B2 verifier independently checked 35,740 states,
170,379 source game-role contributions, 377 FCS fallback states, and 7,192 calibration
rows per target. It exited successfully but emitted sklearn matrix arithmetic warnings;
this is not a warnings-as-errors pass. Six serving verifiers recomputed selections and
grades for 271 games. No cloud objects, database rows, authorizations or serving pointers
were changed. Production deployment identity is verified; live database selection and
matchup lineage are separate, still-open checks. B1 and c1 remain superseded evidence.

Stage 1 closure stands. This contract remains In Progress. Week 6 reconstruction waits
for certified finals and stabilization; software and broader audit work remain actionable
before that gate. No missing historical quote may be replaced by a later capture. Week 7
remains the target; missing its readiness/kickoff window requires a new operating decision.

### Local validation at this checkpoint

- 86 focused tests passed with warnings as errors, including real PostgreSQL transactions.
- All 35 6B flow tests passed with warnings as errors, including the seven-week fixture.
- Four audit-scope tests passed; the new receipt corruption regression passed in the 11-test library run.
- Whole-repository Ruff lint/format, shared contracts and registry validation passed.
- This is not full new-change CI, live database certification or production activation.

### October 9 validation

- Full Python suite: 2,237 passed, 14 skipped with `-W error`; serial PostgreSQL
  integration against a disposable local PostgreSQL 16 database: 29 passed.
- Ruff format/check, shared contracts, quality registry, web lint/typecheck/build,
  web publication tests (141 passed, 1 skipped), browser fixtures (51 passed),
  and strict MkDocs build passed. The local evidence manifest verifies 13 files.
- Exact-commit CI, live database lineage, rebuilt corrected descendants, and
  a guarded Preview cutover rehearsal remain open. These local gates do not
  certify serving correctness.

## Amendments

### Amendment 1 (2026-10-09): byplay_v2 play identity has its own contract

The duplicate-play and play-identity work (completion-matrix row "Duplicate plays / scoring / complete metrics") is executed under [2026-10-09/01-byplay-v2-play-identity.md](../2026-10-09/01-byplay-v2-play-identity.md): an impact-first shadow diff with a user stop gate, then `byplay_v2` keyed by provider play ID (`source_play_id` as a string), period-first ordering with the game clock as diagnostics only, and proof of unchanged output outside the 28 collision keys. This contract's text and matrix are otherwise unchanged; the new contract's Task 6 appends receipts here. Scoring defects, the quality follow-ups, the 95 adjusted rows, Week 6 certification and the Preview rehearsal stay governed by this contract.

### Amendment 2 (2026-10-09): byplay_v2 delivered with invariance proof and discrepancy ledger

**Contract reference:** [2026-10-09/01-byplay-v2-play-identity.md](../2026-10-09/01-byplay-v2-play-identity.md) (`Implemented`).

**Delivered commits (user-run):**
- `a226c56f` `feat(identity): add byplay_v2 and drives_v2 provider-keyed play identity` (Task 2; **correction 2026-10-09:** this entry first carried a wrong commit title)
- `7cedece0` `feat(ordering): add shared play order, unresolved-play flags and v1 golden regression` (Task 3)
- `a7ff4f22` `feat(identity): add provider-keyed possession ledger, independent verifier and Gold converters` (Task 4.1–4.4)
- `e6f7804e` `feat(identity): re-key admission decisions to provider ids and wire the play-identity policy` (Task 4.5–4.7)
- `ca357353` `feat(invariance): prove v1/v2 invariance and record discrepancy ledger` (Task 5)

**Key results and receipts:**
- **Invariance proof (`rebuild/invariance.py`, `scripts/analysis/invariance_v2.py`):** 148,527,073 cells compared across 10 B2 seasons (2015–2019, 2021–2025) and two 2026 pin sets. **Zero differences outside the four collision games.** **Correction 2026-10-09:** the first version of this entry (and the close-out log) described this as proof across the "entire 11-season corpus"; the exact scope and limits are in the list below.
- **Discrepancy ledger:** 1,588 rows, 0 unexplained. All changes confined to four games (2021: 401310699; 2025: 401756916, 401761632, 401762831). 28 legacy dedup candidate removals are accounted for: 25 restored in `byplay_v2`, 3 filtered by unchanged play-type filtering.
- **Evidence artifacts in `repair-track-evidence/`:** `play-identity-impact.json`, `period-label-diagnostic.json`, `possession-v2-comparison.json`, `admission-v2/` (decisions, corroboration, summaries), `net-punt-yards-comparison.json`, `invariance-proof-v2.json`, `discrepancy-ledger-v2.csv`. All 32 digests verified in `checksums.json`.
- **Validation:** Full Python suite with `-W error` (2,433 passed, 15 skipped), `ruff check` and `ruff format` clean, `make contracts-check` passed, strict `mkdocs build` passed.

**Scope and limits of the invariance proof (correction 2026-10-09; source: contract `01` Amendment 7):**
- 2026 is the Week 4 and Week 5 pinned parent sets only, Silver tables plus the baseline possession ledger and observations. No admission decisions cover 2026 and no Week 6 pin set exists, so Week 6 is not compared.
- Source reconciliation was compared with no declared-incomplete game ids on either side. The Gold chain used the Gold stage's functions but was not run through the orchestrated stage.
- Decisions: 1,416 admitted and 28 contradicted match the pins; unverified is 1,747, not 1,749, because two overtime-only groups of game 401756916 have no v2 counterpart (18 ledger cells relabel `reverted_unverified` to `baseline_unchanged`; no score changes).
- One evidence row (2024, game 401645358) differs only in which member represents its group; it is listed in the proof.

**Pending milestone: descendant recertification.** Rebuild and recertify, from `byplay_v2`, every as-of-week aggregate and the ratings built from them for: 2021 game 401310699 (San Diego State, New Mexico State, week 1); 2025 game 401762831 (Buffalo, Eastern Michigan, week 6); 2025 game 401756916 (Arizona, BYU, week 7; overtime-only change); 2025 game 401761632 (Marshall, Texas State, week 8), each from the week shown through the end of its season, plus the matchup features of those teams' later opponents. Not started; served data is unchanged.

### Amendment 3 (2026-10-10): B2 bundle impact decision for the byplay_v2 collision games

**Status:** Approved by the user (2026-10-10): keep B2 `a507d0c7…`, accepting the evidence-based proof; no refit. **Scope:** only whether the B2 inference bundle (raw sha `a507d0c7…`, `conf/rebuild/bundle_b2_w5_v1.json`) stays valid. It does not close the descendant recertification of statistics and matchup features (still pending, see Amendment 2).

**Finding: the B2 fit inputs do not change.** This is derived from the complete discrepancy ledger plus the published 6A observations and the consumer code, not from a byte-for-byte rebuild of the frames.

1. **Only four `ppp` observation cells change** (ledger `observations`, measurement `ppp`): the `denominator` of the four team rows in 2025 games 401761632 (14 to 17) and 401762831 (11 to 12). No `ppp` numerator, raw value, usable exposure or coverage status changes, and the 2021 game 401310699 has no `ppp` change.
2. **Those four rows are not observed.** Read directly from the published observations in the 6A run (`ratings/observations.parquet`, read-only): all four have `coverage_status = missing`, `missing_reason = unresolved_scoring_attribution`, `usable_exposure = 0` and a null raw value. The coverage columns do not change in v2, so they stay missing.
3. **Every `ppp` consumer drops non-observed rows before use:** `ratings/possession_measurements.py` (replay: `coverage_status == "observed"` and `denominator > 0`) and `ratings/possession_rating_materializer.py` (same filter). The set of observed `ppp` rows is therefore identical in v1 and v2, so `ppp` snapshots, terminal states, priors and rating states are identical.
4. **`epa_per_possession` changes cannot reach `ppp`.** Its observations do change in these games, but `_adjust` keys every sum, center and opponent lookup by measurement, and the bridge builder reads `ppp` only.
5. **Offsets (`forecast/offsets.py`) do not change.** Only regulation non-offense events with an admitted label contribute, and both `reverted_unverified` and `baseline_unchanged` are admitted. `possession-v2-comparison.json` shows 0 shared events differing in 2025 and `one_sided_points = 0`, so the per-team sums are unchanged. Usability of the affected team-games is unchanged because each affected game already has `unresolved_scoring_attribution` observations in v1 that stay missing in v2.

**Residual limits (not proven by rebuild):** the frames were not rebuilt from `byplay_v2` and hashed. The unresolved-marker status of the one-sided scoring events is inferred from the unchanged coverage columns. `epa_per_possession` snapshot rows in the published ratings frames will differ once rebuilt, which affects no V5 forecast input but does belong to the pending recertification. A byte-level confirmation (`build_v5_intended_update_bundle.py --historical-cache` on v2-derived frames with the same code sha) remains available and local if the user wants it.

**Decision (approved):** keep B2 `a507d0c7…` for the Week 7 cutover. The consequence is that the Production bundle approval (first live week 6) cannot be re-registered for week 7 (one row per model and bundle), so the cutover gates must accept it; see Amendment 4. If rejected, the alternative is a new bundle B3 with its own approval at `first_live_week = 7`.

### Amendment 4 (2026-10-10): cutover bundle gate accepts a display-only first live week

**Status:** Implemented (2026-10-10; forward rule and rollback rule approved by the user; depends on Amendment 3).

**Problem.** Three places required a bundle approval's `first_live_week` to equal the cutover week: `v5_batch_selection_v2.py` (controller), `authorize_v5_intended_update_batch.py` (authorization validator, which also required the approval's `decision_ref` to equal the packet's) and `v5_packet_builder.py` (which stamped `first_live_week = cutover`). The registry allows one approval per model and bundle (`0018_v5_successor_release_registry.sql`, `uq_v5_model_bundle_approval`), and Production already holds the B2 approval with first live week 6, so a Week 7 cutover packet could not be built or validated.

**Change.** One shared rule, `bundle_covers_cutover` in `v5_batch_selection_v2.py`: the first live week must equal the cutover week, or be a `DISPLAY_ONLY_WEEKS` member earlier than the cutover. The authorization validator applies it and requires the packet `decision_ref` only for an approval registered at the cutover. The builder gains an optional `registered_bundle` (the six approval fields exactly as registered), also accepted by `build_v5_cutover_packets.py` as the spec key `registered_bundle`; it refuses an approval for another model, bundle or season and any other field set. Tests: `tests/test_bundle_cutover_gate.py` (accepts 6 for a Week 7 cutover; rejects 5, 8 and 4; keeps the decision-reference requirement at the cutover; tamper and shape checks).

**Rollback rule (user decision 2026-10-10).** A rollback packet (`v5_intended_update_batch_rollback_v2`) restores runs that were already live, and their bundle's approval predates the cutover by design. For rollback packets the gate therefore accepts `first_live_season == 2026` and `5 <= first_live_week <= cutover` (the floor is the first live V5 slate). This matches the runtime selection rule in `public_selection.py`, which only refuses a pending or live run before its approval's first live week. `build_rollback_packet` and the `rollback.registered_bundle` spec key carry the prior bundle's approval unchanged. Tests: `tests/test_bundle_cutover_gate.py`.

**Remaining rollback and `current_week` gaps (found by reading the controller, not yet changed; see Amendment 5).**

### Amendment 5 (2026-10-10): the cutover packet cannot yet open a new Week N (design review, not implemented)

**Status:** Findings 1 and 2 approved by the user and implemented (Amendment 6); Finding 3 is corrected and implemented in Amendment 6. Found by reading `v5_batch_selection_v2.py`, `public_selection.py`, `v5_packet_builder.py` and the role grants.

**Finding 1: week N must already be selected.** `validate_v2_packet` requires `expected_current_runs` to cover Weeks 0 through N and `expected_current_week.week == N`, and `apply_v2_packet` requires the live selections to equal that map exactly. That fits a cutover week that is already live (the original N=5 and N=6 designs). For N=7 there is no Week 7 selection and `current_week` is (2026, 6) pointing at the display-only Week 6 run, so a Week 7 packet cannot satisfy the before-state. The two ways out:
- **Advance mode (recommended).** Accept `expected_current_week.week` equal to N or N-1. In advance mode `expected_current_runs` covers Weeks 0 through N-1 and the apply step verifies that no Week N selection exists, then selects Weeks 0 through N and moves `current_week` from (N-1, prior run) to (N, pending run) in one transaction. Selection of a first-time week already works (`select_week_run` inserts when no row exists).
- **Pre-select Week 7 first.** Needs the Week 7 pending run to go public before the corrected replays and requires the packet to allow the same run in the before and after maps (`replacement packet reuses a prior run` today). Rejected: it exposes Week 7 early and weakens the reuse check.

**Finding 2: rolling back advance mode needs a DELETE the pipeline role lacks.** `cks_pipeline` has SELECT, INSERT and UPDATE on `site_week_selections` (migration 0013), no DELETE. Undoing a first-time Week N selection means deleting that row. Proposed: the rollback packet performs the delete and therefore runs only under the owner or migrator login (as Preview already does and as `rollback_week6_display.py` does for Production); under the pipeline role the transaction fails closed and nothing changes.

**Finding 3: rollback packets assume the old runs fit the replay/pending shape.** `_records_for_cutover` (used for rollback with the prior manifests) requires every prior run to be a `replay` and Week N to be `pending`. The old runs are retrospective replays for Weeks 0-4, a frozen and scored Week 5, and the display-only Week 6, and no Week 7 run exists. Rollback authorizations for them (the open repair-track decision) therefore need their own evidence-class handling, not just the bundle rule.

**Rehearsal requirement.** Whatever is chosen, the Preview rehearsal must apply the Week 6 to Week 7 transition, read back `site_week_selections` and `current_week`, and apply the rollback under the owner login before the Production decision.

### Amendment 6 (2026-10-10): Advance Mode and registered-release rollback implemented

**Status:** Implemented in the working tree (user-approved design); tested against a scratch PostgreSQL 14 with the repository migrations (CI uses 16). Not yet exercised in Preview.

**Advance Mode (Amendment 5, findings 1 and 2).** A selection packet may carry `opens_week = N` (builder flag `advance`, CLI spec `advance: true`). Its before-state is Weeks 0..N-1 with `current_week` at N-1 and no Week N selection; it selects Weeks 0..N and moves `current_week` to N in one transaction. The rollback is the exact inverse: it restores Weeks 0..N-1, moves `current_week` back and deletes the Week N selection through `deselect_week_run` (`public_selection.py`), which records a `DESELECTED:` history row and needs DELETE. The pipeline role has none, so the statement fails closed and nothing changes; the rollback must run under the owner or migrator login. Tests: `tests/test_v5_advance_mode.py` (validator shapes, real-database apply, idempotent retry, refusal when Week N is already selected or the site is on another week, rollback, privilege failure).

**Correction to the open-decisions note and to Amendment 5, finding 3.** Production already holds an authorization for every currently selected run (Weeks 0-4 `replay`, Week 5 `pending`, Week 6 `pending`) and two bundle approvals: `30c4f1eb…` (first live week 5) for Weeks 0-5 and `a507d0c7…` (first live week 6) for Week 6. Read-only check, 2026-10-10. What was missing was the ability to carry those registered records into a rollback packet: the builder created new records under the cutover decision (a different `authorization_id`, which the controller's registered-row comparison would reject) and required one bundle and one evidence class pattern. The Preview rows were not checked and must be (run the export tool with `--environment preview`).

**Changes.**
- `build_rollback_packet` accepts `registered_authorizations` (week to row) and `registered_bundles`, carried verbatim; the packet gains optional `additional_bundle_approvals` (rollback packets only), and the controller requires exactly the bundles of the authorized runs, each passing the rollback gate and each compared with its registered row at apply time. A rollback authorization keeps the decision and the `replay` or `pending` class it was registered under.
- Rollback packets no longer require completed-week certifications or fresh finals: they restore history that was already public and (for a display-only run) can never be certified. Each restored run must still be a complete public run for its own week (`_verify_restored_runs`). Forward packets are unchanged.
- `scripts/pipeline/export_v5_registered_releases.py` (read-only) prints the `registered_authorizations` and `registered_bundles` fragments for a spec from exact `WEEK=RUN_ID` pairs. Tests: `tests/test_v5_rollback_registered.py`.

**Still not exercised.** A Week 7 packet against the real Week 5 prospective record, the controller's apply path with the real registered rows and R2 source chains, and the owner-login rollback in Preview (the Preview rehearsal).

### Amendment 7 (2026-10-10): Preview verification, Week 6 market-sources lock, Week 7 packet smoke test

**Status:** Implemented in the working tree; the lock tool and packet smoke test ran read-only against real Preview and Production data.

**Preview verification (read-only, `cks_preview_pipeline`).** Preview holds an authorization for every selected run (Weeks 0-4 `replay`, Week 5 `pending`, Week 6 `pending`) and both bundle approvals, so `export_v5_registered_releases.py --environment preview` returns exactly one row per run and both approvals. **One difference from Production:** Preview's B2 approval (`…a507d0c7cba5`) has `first_live_week = 5` where Production's has 6. The forward gate accepts only a display-only first live week before the cutover, so a Preview *forward* packet for Week 7 is refused until that row says 6 (rollback packets accept 5). The pipeline role cannot update the table and nothing blocks the owner: before the Preview rehearsal the user runs, as the Preview migrator login, `UPDATE v5_model_bundle_approvals SET first_live_week = 6 WHERE approval_id = 'preview-intended-update-a507d0c7cba5';` (the runtime selection rule only needs the Week 6 run to be at or after the first live week). Not applied.

**Week 6 market-sources lock.** `src/cks_picks_cfb/rebuild/market_sources_lock.py` (pure) and `scripts/pipeline/build_week_market_sources_lock.py` pin the Silver games, market snapshots and market quotes for an unserved week and classify every game and target with the replay's own quote rule (`select_best_quote`: linked to the snapshot, captured before kickoff, no later than `as_of`). A game and target without an eligible quote is a verified gap (`post_kickoff_only`, `no_quote`, `no_canonical_line`, `no_snapshot`, `after_as_of_only`): no selection and no grade. The tool writes the reconstruction source refs extended by that week (earlier weeks untouched, base file hash recorded) and a coverage report. Dry run on the real d2-era data (snapshot captured 2026-10-08T16:19Z, `as_of` 16:53:58Z): 58 games, 55 eligible and 3 gaps per target, and the three gap games (401871051, 401871066, 401871090) are exactly the games the d2 run omitted as already kicked off. Wiring: `derive_successor_lock` appends the refs' `market_gaps` to the lock's declared gaps and records a display-only original run honestly (`state: published`, `display_only: true`) instead of labelling it scored; the replay serving builder now accepts exactly the declared gaps for either target (previously only totals; an unquoted spread was always fatal) and replays from a display-only run. Tests: `tests/test_market_sources_lock.py`, `tests/test_successor_lock.py`, `tests/test_serving_quote_gaps.py`. **Not exercised:** the serving verifier, packager and publisher on a replay with declared spread gaps (a Week 6 replay does not exist yet); they may assume every game has a spread quote.

**Week 7 packet smoke test.** Building it exposed one defect, fixed: `protected_runs` had to be non-empty, but a Week 7 cutover replaces every selection (Weeks 0-6) and nothing else is selected. An empty map is now valid; apply and preflight require that no selection exists outside the replaced weeks (previously only the listed weeks were compared, so an unlisted one was not detected). Tests: `tests/test_week7_packet.py` (full positive path with an ordinary Week 5 freeze receipt, the rollback, refusals for a missing Week 5 record, a Week 6 record, a late or foreign receipt and a before/after record change, plus real-database apply and refusal). Read-only run against real Preview evidence, with fixture Week 7 runs and statistics: the forward advance packet (real selected runs as the before-state, empty protected map) validates against the real Week 5 legacy-attestation record read from the database and R2; the rollback packet, built from the real run manifests, the real registered authorizations (Weeks 0-4 `replay`, Weeks 5-6 `pending`) and both real bundle approvals, validates; its preflight passed the registered-row and restored-run checks and then recognized the live state as already equal to the rollback's end state, as it should (it stopped only on the fixture statistics). **Not exercised:** the forward apply against real registered authorizations (they do not exist until the user registers the new runs) and the owner-login rollback (Preview rehearsal).

### Amendment 8 (2026-10-10): the 2026 record is unified; freeze provenance is unchanged

**Decision (owner, 2026-10-10).** The demonstrated 2026 record is one continuous cumulative V5 record from Week 0, graded the same way for every week, provided every input is strictly point-in-time. Recorded in the [decision log](../../decisions/decision_log.md) and [record methodology](../../modeling/record_methodology.md); it supersedes the 2026-10-01 "prospective ATS win %" metric for reporting.

**Effect on this contract.**
- Ordered work item 2 ("Prove Week 6 cannot enter the prospective record, freeze or close") now means: Week 6 cannot get a **freeze receipt** and is never frozen (a post-kickoff freeze would be fabricated). Its grades **join the unified record**: interim via `load_game_finals.py` and the fixed grades-only backfill on the display-only run (55 of 58 games), and at the cutover via the corrected Week 6 replay. `DISPLAY_ONLY_WEEKS` and the prospective-record checks in `v5_batch_selection_v2.py` stay as provenance mechanics.
- "Display-only exclusions" in the validation list refers to the freeze record only.
- After the cutover the counted run for every week 0-6 is the corrected replay; the frozen Week 5 run and its receipt are preserved unchanged ("Preserve Week 5 exactly" holds for the immutable artifacts).
- The cutover packet must carry a passing point-in-time audit receipt (Amendment 8 work, `scripts/pipeline/audit_point_in_time_leakage.py`) covering every selected run.
- The CFBD closing-line exception (three Week 6 games) is declared in the market lock and is only used if the CFBD re-fetch comparison supports it; otherwise those games stay ungraded verified gaps.
- Rollback gate wording: "the floor is the first live V5 slate" means the first registered live bundle week; it is a technical gate, not a reporting statement.

**Unchanged hard rules.** Training strictly precedes prediction; no 2026 outcome refits the V5 identity; no quote at or after kickoff is used except a declared exception; no freeze receipt after kickoff; frozen records are immutable; market data never enters model inputs.

### Amendment 9 (2026-10-10): leakage loader, empirical CFBD comparison and unified web record

**Authorization:** the owner's explicit four-task implementation handoff in this session, starting from `582c5b9f`; implementation of Amendment 8. No Git mutation, serving write, cloud artifact overwrite or corrected-lineage activation is authorized by this amendment.

**Implemented:** `audit_point_in_time_leakage.py` loads actual checksummed run/forecast/rating/bundle/quote artifacts, follows each forecast's rating-state binding and source-game IDs, and emits the canonical signed receipt. It checks serving statistics by rebuilding each recorded source-version snapshot after independently excluding every same/later-week game and comparing values, counts and ranks. Outputs are exclusive-create, and a failed audit exits 1. `--run WEEK=RUN_ID` and the source-lock/rating/bridge arguments let an operator name exact successor evidence; defaults are the existing corrected replay set and display Week 6. Both cutoffs and every read object's hash are retained.

**Cutoff clarification:** the completed-week replay has a separate pregame state cutoff for each game (the linked state's `cutoff_utc`, equal to that game's kickoff), while `data_as_of` in the serving manifest is the earlier market cutoff. The receipt records both; these replays are not presented as one pre-slate forecast. Rule c checks each game, rule g still requires both cutoffs, and the one-cutoff ordering check applies to slate forecasts. Week 6 additionally requires a forecast before October 7 00:00Z and complete 58-game coverage. The late-quote exception never bypasses the market cutoff, and model development seasons must lie entirely in the approved 2015–2019 / 2021–2025 set.

**Empirical result:** completed Weeks 0–5, three games sampled per week, 59 pre-kickoff provider/target lines compared with fresh CFBD lines; 19 match and 40 differ. This fails the declared acceptance gate. A difference can be legitimate pregame movement after the earlier capture; it is not proof of an in-game feed. The three early Week 6 games remain ungraded verified gaps. The lock CLI, successor lock, serving builder, quote selector and independent verifier now carry exact game/target/quote declarations and source provenance; declarations are refused without a signed, passing comparison. No exception was enabled.

**Read-only audit results:** Weeks 0–5 pass all seven rules for 271 games. Through Week 6, 326 games are checked and the receipt fails: 220 rule-b rating-role cutoff violations (four roles across 55 games), the Week 6 rule-c boundary, and rule-g complete-slate coverage. Rules a, d, e and f have zero violations. This is a formal cutoff/state-binding failure; no future outcome in the rating source histories was found. The existing forecast builder replaces live feature ratings with the per-game pregame states it names; their cutoffs are later than the display run's forecast time. Its immutable artifacts remain unchanged. A separately built and audited complete Week 6 replay is still required before a passing cutover receipt can cover that week.

**Web:** Performance now reads the explicit selected runs across `replay`, `live` and `pending`, displaying one cumulative record. The replay/prospective sections and per-game provenance split are removed from presentation; receipt and evidence-class storage remain intact. No latest-run fallback or database selection was introduced. Unit tests and the five Performance Playwright tests pass.

**Evidence:** local `artifacts/audit/leakage_audit_receipt_2026.json` (canonical failure through Week 6), `leakage_audit_receipt_2026_through_week5.json` (passing subset), and `cfbd_closing_line_comparison_2026.json` (failed comparison). The initial receipt is preserved as `leakage_audit_receipt_2026_initial.json`; the canonical receipt adds the completed statistics rebuild verification. Session validation and handoff: `session_logs/2026-10-10/05-unified-record-leakage-audit.md`.
