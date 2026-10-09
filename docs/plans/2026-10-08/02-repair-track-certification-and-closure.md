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

| Requirement | State | Evidence / next gate |
|---|---|---|
| Direct c2 readback and B2 certification | Verified | 408 objects; six serving recomputations; independent B2 verifier; see `repair-track-evidence/` |
| Exact-commit CI and deployments | Historical baseline verified | `04cd53ce` CI passed and Production deployment `dpl_C32B…` was READY at that SHA. `main` has since advanced through PRs #5 and #6 to `07c53045` (web-only); CI and deploy verification for `07c53045` and the next commit are still open |
| Production staging dry run / rollback | Partial | Six replay staging dry run passed with no writes; complete cutover rollback/readback still open |
| Positive Week 7 packet / Week 6 exclusion | Partial | Signed synthetic Week 5 receipt passes packet validation and survives unchanged; actual Week 5 evidence and real Preview rehearsal still required |
| Seven-week fixture and Week 6 reconstruction | Partial | Seven-week frame build and independent verifiers pass; no original Week 6 artifact fabricated. Successor certification integration and stabilized live finals still required |
| Preview cutover and matchup database gates | Open | Pending Week 7 and corrected snapshot bindings |
| Six quality follow-ups | Partial | A byte-pinned raw schedule generator, weekly plays/stats request comparison, required-check policy file and opt-in R2 readback are code-level increments. The policy is not yet enforced in builders; raw failed-capture retention, odds evidence, complete ambiguity review, durable builder receipts and legacy disposition remain |
| Duplicate plays / scoring / complete metrics | Verified locally (2026-10-09) | The [pinned Bronze/Silver identity census](repair-track-evidence/play-identity-census.json) verified 168 Bronze captures (1,673,337 rows) by object hash across all 11 B2 seasons. Both tiers contain the same 28 complete-sequence collisions with distinct provider IDs (1 in 2021, 27 in 2025). In 2025, 25 collisions cross periods; historical `keep="first"` has 24 regulation-play removal candidates. Across both seasons, 28 candidate removals include 19 non-null PPA values and three scoring plays. New `byplay_v1` builds now fail closed on distinct source records at one sequence and allow only exact repeats; a read-only 2021 pinned-source smoke test rejected the real collision. The 75,032 Bronze rows with incomplete sequence keys are separate; normalized Silver has no missing sequence fields. The draft `drafts/byplay-play-identity.patch` is **not applied**: `byplay_v1` rejects retained distinct IDs, while drive and possession identities also need review. Adoption needs versioned identity contracts and attribution of every descendant change; scoring and independent full metrics remain open. **Update (2026-10-09):** Delivered and verified under [2026-10-09/01-byplay-v2-play-identity.md](../2026-10-09/01-byplay-v2-play-identity.md) (Tasks 1–6 complete); see Amendment 2 for receipts. |
| 2025 matchup backfill | Open | Corrected lineage and serving gates |
| Null-lean database regression | Verified locally | Real PostgreSQL publication with quoted null/No Bet rows and valid controls; legacy model exercises shared persistence path, not V5 authorization |
| Documentation reconciliation | In progress | This matrix tracks remaining work |

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
- `a226c56f` `feat(identity): add byplay_v2 and drives_v2 schema contracts and builder opt-in` (Task 2)
- `7cedece0` `feat(ordering): add shared play order, unresolved-play flags and v1 golden regression` (Task 3)
- `a7ff4f22` `feat(identity): add provider-keyed possession ledger, independent verifier and Gold converters` (Task 4.1–4.4)
- `e6f7804e` `feat(identity): re-key admission decisions to provider ids and wire the play-identity policy` (Task 4.5–4.7)
- `ca357353` `feat(invariance): prove v1/v2 invariance and record discrepancy ledger` (Task 5)

**Key results and receipts:**
- **Invariance proof (`rebuild/invariance.py`, `scripts/analysis/invariance_v2.py`):** 148,527,073 cells compared across 10 B2 seasons (2015–2019, 2021–2025) and two 2026 pin sets. **Zero differences outside the four collision games.**
- **Discrepancy ledger:** 1,588 rows, 0 unexplained. All changes confined to four games (2021: 401310699; 2025: 401756916, 401761632, 401762831). 28 legacy dedup candidate removals are accounted for: 25 restored in `byplay_v2`, 3 filtered by unchanged play-type filtering.
- **Evidence artifacts in `repair-track-evidence/`:** `play-identity-impact.json`, `period-label-diagnostic.json`, `possession-v2-comparison.json`, `admission-v2/` (decisions, corroboration, summaries), `net-punt-yards-comparison.json`, `invariance-proof-v2.json`, `discrepancy-ledger-v2.csv`. All 32 digests verified in `checksums.json`.
- **Validation:** Full Python suite with `-W error` (2,433 passed, 15 skipped), `ruff check` and `ruff format` clean, `make contracts-check` passed, strict `mkdocs build` passed.
