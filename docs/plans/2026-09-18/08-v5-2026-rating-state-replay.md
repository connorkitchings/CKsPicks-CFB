# V5-08: 2026 Rating-State Replay

- **Status:** Implemented 2026-09-22
- **Created:** 2026-09-18
- **Planner:** Sol
- **Approval source:** User approved the three-contract 2026 extension plan on 2026-09-18 with decisions: Repair extension (not V4-Silver-direct), three layered contracts, full season from Week 0. Implementation explicitly deferred.
- **Implementation log:** `session_logs/2026-09-22/07-v5-documentation-authority-reset-and-08-rating-replay.md`
- **Commit policy:** Separate code and certified-evidence checkpoints; user explicitly authorized Git add and commit.

## Goal, current state, and entry gate

Replay the **frozen** Contract 03 winner `ppp__rho_0_60__exposure`
(carryover prior + exposure updater) forward through the live 2026 season,
from Week 0 through the latest completed week, producing certified 2026
`team_states` so readiness resolves and Contract 09 can forecast. No
re-selection, no candidate comparison, no tuning: 2026 is replay, not a new
validation season. The [common contract](../2026-09-13/v5-ratings-successor-roadmap-and-contracts.md)
is binding.

**Entry gate:** Contract 07 Implemented with a certified 2026 measurement
manifest recorded as the sole eligible 08 parent. This contract starts only
when that manifest exists in Preview R2. The historical certified rating
identity is `possession-v1-ratings-20260921-11d59ee-r9cert` (Amendment 1;
supersedes `possession-v1-ratings-20260917-d029526-cert`); its selection stays
frozen and untouched.

**Historical-first deferral (2026-09-18):** Do not execute this approved
contract until Contracts 10-12 close, the user explicitly accepts historical
readiness, and 07/08 are re-reviewed with the frozen design, exact eligible
artifacts, through-2025 final fit/calibration, selected-prior inputs, and
timestamp provenance. Replaying 2026 results never creates prospective evidence.

**Conditional-results clarification (2026-09-20):** Implemented Contract 11A
and approved Contract 12A may produce `conditional_historical_results_only`
development evidence only.
They do not close Contracts 10-12, restore forecast eligibility, establish
prospective evidence, or satisfy this contract's explicit-user-acceptance and
re-reviewed-application gate.

**Re-review record (2026-09-22):** The deferral gates are satisfied — Contracts
10, 11, and 12 are Implemented, and the user explicitly accepted the Contract 12
historical readiness recommendation on 2026-09-22
(`docs/research/2026-09-21-v5-12-historical-results-and-readiness-review-report.md`;
scorecard run `readiness-v1-20260921-scorecard`, manifest SHA
`a8351fb3cabd7edbd1f78c961aa563a110b585db6c410e2b3f5973c8a2278b29`).
Contracts 07–09 were re-reviewed under
[`docs/plans/2026-09-22/01-v5-acceptance-and-07-09-rereview-2026-launch.md`](../2026-09-22/01-v5-acceptance-and-07-09-rereview-2026-launch.md):
the historical-first deferral is **lifted** and execution is authorized against
the corrected certified lineage (Amendment 1). The first Contract 06 slate
target is Week 5 (~Thu Oct 1 first kickoff).

At implementation close, the independently verified Weeks 0–3 replay is
`possession-v1-rating-replay-20260922-fcaa571`. Historical rating states were
not modified, re-selected, or inherited as 2026 evidence.

## Approach, scope, and interfaces

Assemble 2026 preseason priors from the existing preseason ingestion path,
then run a state-replay (not a tournament) that applies the frozen winner's
prior family and updater to the certified 2026 measurements week by week,
emitting 2026 `rating_states` and `team_states` with `live` timing. New
run-ID; full preflight/apply/independent-verify/idempotent-repeat cycle in
Preview.

Stage: `rating-replay`. Consume the certified 07 measurement manifest plus
2026 preseason context (returning production, recruiting, coaching via the
existing `ingest_preseason.py` path). Output versioned 2026 `priors`,
`rating_states`, `team_states`, and a terminal `retained-rating-manifest.json`
marked as a replay (not a selection) with
`production_activation_authorized: false`. No Neon/production/web writes.

The 2026 rating manifest becomes the sole eligible rating parent for
Contract 09. The historical 11B retained manifest
(`possession-v1-ratings-20260921-11d59ee-r9cert`) remains the sole eligible
parent for historical replay; neither substitutes for the other.

## Implementation tasks

### Task 1 — 2026 preseason prior assembly

Assemble 2026 preseason context blocks (returning production, recruiting,
coaching continuity) through the existing preseason ingestion path for the
2026 season, bound to exact immutable input refs. Apply the frozen winner's
prior family (`rho_0_60` carryover structure with 2026 context where the
family requires it) without refitting any learned quantity on 2026 outcomes.
Persist 2026 `priors` with `live` timing and exact source refs.

**Acceptance:** 2026 priors present in Preview with exact input refs; no
learned quantity fitted on any 2026 outcome; frozen family structure
byte-comparable to the certified 03 definition.

**Validation:** Focused prior-assembly unit tests; input-ref binding checks;
`git diff --check`.

### Task 2 — Week-by-week state replay (Week 0 through latest completed)

Execute the replay runner: for each 2026 week from 0 through the latest
completed week, advance every team's offense/defense states using the frozen
carryover prior and exposure updater applied to that week's certified 2026
observations, with strict pre-kickoff cutoff semantics (a week's games enter
states only after finals stabilize, mirroring the historical replay
discipline). Emit 2026 `rating_states` and `team_states` partitions;
terminal replay manifest published last.

**Acceptance:** Continuous 2026 state history with no gaps from Week 0;
every state row traceable to pre-cutoff certified measurements; replay is
deterministic (byte-identical rerun).

**Validation:** Replay preflight + apply + idempotent repeat; continuity and
cutoff unit tests; `uv run ruff check .`.

### Task 3 — Independent verification of the 2026 replay

Independently reconstruct the 2026 priors, states, and replay manifest from
the certified 07 measurement parent and exact preseason input refs using
verifier-owned code that never imports the replay producer. Confirm parent
identity, timing classes, cutoff discipline, and manifest signature;
idempotent repeat returns `already_applied` with zero writes.

**Acceptance:** Signed verifier confirmation of the 2026 replay end-to-end
from source artifacts; readiness `team_states` source resolves against 2026
rows; manifest recorded as the sole eligible 09 rating parent.

**Validation:** Verifier CLI run + signed verifier manifest; R2 inventory
confined to the Preview research prefix; strict MkDocs and `git diff --check`
for documentation updates.

## Testing strategy

Focused unit tests for 2026 prior assembly (no 2026-outcome fitting),
replay continuity from Week 0, and pre-kickoff cutoff discipline. Full
certification cycle (preflight/apply/verify/repeat) for the replay run.
Reuse the existing rating-verifier patterns; do not add mirror tests for
certification-only runs. Strict MkDocs and `git diff --check` for
documentation updates.

## Implementation evidence (2026-09-22)

- Replay run: `possession-v1-rating-replay-20260922-fcaa571` at code SHA
  `fcaa57168702e6005dfe786c0e3489a6c04c6df2`.
- Retained manifest:
  `artifacts/research/data-first-football-v1/possession-v1/rating-replay/runs/possession-v1-rating-replay-20260922-fcaa571/retained-rating-replay-manifest.json`,
  raw SHA
  `0c7bca598dcf5a377b7c619edba7eca34bb31dd7c61d489d47c06a5bfc38e3f0`.
- Independently verified output: 276 priors, 628 rating states, and 314 team
  states across 157 eligible games in Weeks 0–3. Output record digests are
  `6978743191ffdb44205c8b11b4ae28edff84bec044e623913b12c062f005d9ea`,
  `792eb65e529aee698255ed7ce5de73d251babc44fd71be59fe4f15b78270c14e`,
  and `e4e93ce24f47cc8f8ab61ea7c487442bf6f4efcebf4712001aa43a64a3481244`.
- Verifier manifest:
  `artifacts/research/data-first-football-v1/possession-v1/rating-replay/runs/possession-v1-rating-replay-20260922-fcaa571/verification/verifier-manifest.json`,
  signed SHA
  `568113873d5a1329d68f54b46bd0f507e79c24ebe770e76accc9db1d6557a709`.
- Producer repeat returned `already_applied`; verifier repeat returned the same
  signed SHA. The 11B historical parent raw SHA remains
  `9d00e63564691c0323fa203b76b4ee49a9fff5aa945fdb8fa000142f640e4ba0`.
- All artifacts remain Preview-only with
  `production_activation_authorized: false`; no Neon, V4 production, or web
  state changed.

## Risks, definition of done, and amendments

Any refit of priors, updater parameters, or selection on 2026 outcomes is
tuning and is prohibited — this contract is replay-only. Incomplete 2026
weeks (CFBD finals lag) block replay advancement for that week; never
advance states on partial outcomes. Sealed 03 code (candidate registry,
`OUTER_SEASONS`, parent run-IDs) requires explicit amendment to admit the
2026 replay parent.

- [x] 2026 priors assembled with exact input refs; nothing fitted on 2026 outcomes.
- [x] Certified 2026 rating replay manifest in Preview (preflight/apply/verify/repeat).
- [x] Continuous 2026 state history from Week 0; readiness `team_states` source resolvable.
- [x] Historical rating artifacts (`possession-v1-ratings-20260921-11d59ee-r9cert` certified; superseded `possession-v1-ratings-20260917-d029526-cert`) byte-identical, selection untouched.
- [x] No production/Neon/web writes; manifest carries `production_activation_authorized: false`.
- [x] Reports, plan index, roadmap status, contract lifecycle, and session logs are current.

Follow the common amendment process for prior, updater, timing, or replay
changes. Contract 09 may consume only the independently verified live replay
parent, after Contracts 07 and 08 are refreshed through stabilized Week 4 finals
under new immutable identities.

## Amendments

### Amendment 1 — Re-reviewed lineage and lifted deferral (Sol, 2026-09-22)

**Reason:** The historical-first lane completed 2026-09-21 and the user
explicitly accepted the Contract 12 recommendation on 2026-09-22. The
2026-09-18 deferral required re-review against the corrected certified
artifacts — frozen design, eligible artifacts, through-2025 final
fit/calibration, selected-prior inputs, and timestamp provenance — before any
execution.

**Original approach:** This contract bound the frozen winner's certified
identity to the 03 retained manifest
(`possession-v1-ratings-20260917-d029526-cert`, r6-derived) and deferred all
execution behind Contracts 10–12, explicit user acceptance, and re-review.

**Revised approach:** The frozen winner `ppp__rho_0_60__exposure` is unchanged;
its certified identity is re-pointed to the r9-derived 11B retained manifest
`possession-v1-ratings-20260921-11d59ee-r9cert` (manifest SHA
`2f1cdc5f26743ddd25a01b9a4a1d84ce562ab15bbaa810b15df8e9055c4c3f65`; selected
`ppp__rho_0_60__exposure` with **no selection flip** versus the r6-derived
run — recorded in `session_logs/2026-09-21/07-v5-11b-ratings-r9-rebuild.md`).
The replay consumes the certified 2026 measurement manifest from amended
Contract 07 (whose settings inherit r9, including the corrected scoring
extraction). Priors apply the frozen carryover prior structure with 2026
preseason context; no learned quantity is fitted on any 2026 outcome. The
historical-first deferral is lifted; execution is authorized. All replay-only
guarantees are unchanged: no refit, no re-selection, no tuning, sealed 03/11B
code admits the 2026 replay parent only by explicit amendment,
`production_activation_authorized: false`, no Neon/production/web writes.

**Impact:** No design, scope, or acceptance-criteria change; the certified
parent identity is re-pointed with the recorded no-flip evidence. Re-review
authority and the authorized execution sequence:
[`docs/plans/2026-09-22/01-v5-acceptance-and-07-09-rereview-2026-launch.md`](../2026-09-22/01-v5-acceptance-and-07-09-rereview-2026-launch.md).

### Amendment 2 — Isolated live-replay interface (Terra, 2026-09-22)

**Reason:** The sealed historical rating runner and its verifier reconstruct the
complete 60-candidate historical tournament from the r9 measurement and Repair
v2 parents. They cannot accept the Contract 07 live measurement parent without
either re-selecting on 2026 results or changing historical artifact behavior.

**Revised interface:** Add a dedicated Preview-only `rating-replay` runner and
an independently owned verifier. Both bind, by raw checksum and signed
manifest, the Contract 07 measurement manifest, the frozen 11B retained-rating
manifest, its r9 historical measurement terminal reference, and the three
existing 2026 preseason capture manifests (recruiting, returning production,
and coaches). The fixed candidate is exactly
`ppp__rho_0_60__exposure`; the replay emits only versioned `priors`,
`rating_states`, and `team_states` under a new live-replay root. It performs no
candidate registry traversal, noise fitting, bridge fitting, calibration, or
2026-outcome selection.

**Frozen replay semantics:** 2026 priors use the 2025 terminal PPP states with
the 11B carryover coefficient `rho=0.60`; the fixed exposure updater consumes
only iteration-four live snapshots that have crossed the next certified weekly
cutoff for that same team. Scaling remains the prior-season 2025 team-equal center and scale. The
three preseason manifests are bound as immutable provenance inputs; this prior
family has no learned context term, so their values cannot alter a prior. The
last completed week's observations do not enter a state until the next
certified replay refresh, preserving strict pre-kickoff availability.

**Independent verification:** The verifier must not import the replay producer
or historical tournament producer. It re-reads the stored inputs and output
partitions, independently reconstructs all three outputs, checks source timing,
continuous weeks, state/cutoff lineage, manifest signature, and deterministic
idempotency. Historical 11B artifacts remain read-only parents.

**Impact:** This implements the original contract's explicit sealed-code
amendment requirement. It does not change the candidate, mathematics,
admission rules, production boundary, or Contract 09 entry gate.
