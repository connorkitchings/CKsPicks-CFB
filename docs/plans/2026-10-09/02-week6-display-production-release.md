# Week 6 Display-Only Run: Production Release

- **Status:** In Progress (Terra execution started 2026-10-09 ~14:00Z)
- **Created:** 2026-10-09
- **Planner:** Sol (Plan Mode investigation; read-only review of Preview/Production state, run artifacts and tooling)
- **Approval source:** User decisions in session 2026-10-09 — existing d2 run, full publish scope, Preview rollback rehearsal kept, local-site verification loop; explicit `implement-plan` instruction on this exact path
- **Implementation log:** `session_logs/2026-10-09/03-week6-display-production-implementation.md`
- **Commit policy:** Commit with implementation
- **Parent decisions:** [Contract 04 Amendment 9](../2026-10-07/04-stage1-week5-corrected-data-finalization.md#amendment-9-2026-10-08-labeled-display-only-week-6-on-the-corrected-lineage) (display-only mode rules; Production publication is a separate go-ahead — this contract is that go-ahead), Amendment 10 (Week 6 waiver in the prospective check), Amendment 11 (Task 7 chain delivered). Supersedes the hold-until-cutover decision for Week 6 only ([decision brief](../2026-10-08/01-stage1-decision-brief.md), Outcome).

## Goal

Open Week 6 on the Production site using the verified display-only run
`2026w6-v5repair-20261008-d2` (corrected lineage, B2 bundle), with a coherent
site: Picks (55 games + approved notice), post-Week-5 Ratings, Week 6 matchup
pages. No prospective-record contamination. A scripted, Preview-rehearsed
rollback is a hard gate before any Production write.

## Current State (verified read-only 2026-10-09)

- **Production:** `current_week`=(2026, 6) with no active run → hold screen; zero
  Week 6 `games` rows; 271 venues; Weeks 0–5 served on the uncorrected lineage
  (`20260929-p1/p2`, rating source `e80ae347…`, bundle `30c4f1eb…`);
  `v5_model_bundle_approvals` covers only `30c4f1eb…`.
- **Preview:** run `-d2` published (`state=published`, `evidence_class=pending`,
  `validation.display_only=true`, `expected=predicted=55`) and selected;
  `site_week_selections` reason cites Contract 04 Amendment 9.
- **The run:** built 2026-10-08T16:53:58Z, market capture 16:19Z (110 quotes);
  55/58 games, all lined; 3 omitted as kicked-off before the build (Southern Miss
  @ Troy 401871051, Jacksonville State @ Kennesaw State 401871066, New Mexico
  State @ FIU 401871090). Every pick predates its game's kickoff; ratings are
  through-Week-5 only — no Week 6 plays/results ingested. Evidence in
  `docs/plans/2026-10-07/stage1-evidence/week6-display-only-preview-d2.json`.
- **Ratings gap (new finding):** the corrected manifest `c83b1423…`
  (rating run `v5-intended-update-2026-corrected-w6live-r1`) has **no
  `v5_rating_snapshots` rows anywhere** — Preview's Ratings page is empty today.
  Selecting d2 flips the site-wide rating source to it, so snapshots must be
  published. Verified-but-unapplied candidates exist: rating manifest in R2,
  team-stats as-of-6 (3,036 rows), matchup payload (static gates 7/7).
- **Tooling:** site notice already deployed on origin/main (data-driven off
  `validation.display_only` + `created_at`; generic text). `run_web_local.sh
  [preview|production]` runs the site locally against real Neon (read-only,
  matchup pages open); no Vercel change needed for verification. Web read path
  accepts `state=published` + `evidence=pending` (no freeze required); rollback
  is reselection-only in tooling — no deselect exists.

## Scope

### Included

- Phase 0 (Preview): project corrected rating snapshots, team stats as-of 6,
  and Week 6 matchup data to Preview; verify routes on the local site.
- Phase 1 (Preview): rollback script + rehearsal restoring the exact hold
  screen, then re-apply forward.
- Phase 2 (Production, all applies user-run): stage d2 artifacts to the
  production namespace; 2 admin inserts (bundle approval for B2, production
  release authorization for d2); publish chain (seed schedule → venues →
  ratings → stats → matchup → `publish_to_db --from-artifact` → `select_public_run`);
  verify on the local site + live Production routes.
- Phase 3: post-finals unconstrained `--grades-only` backfill (Preview +
  Production); docs updates (`status.md`, completion matrix, Stage 7B
  before-state note).

### Excluded

- Retraining, refit, or any change to the B2 bundle or rating manifest.
- `freeze_week.py` / `close_week.py` on Week 6 (the display-only guard forbids it).
- Any change to Weeks 0–5 selections, grades, or the prospective record.
- Mutation of existing Production rows; weakening any gate (policy, venue,
  bundle-approval, authorization, verifier).

## Affected Components

- `scripts/pipeline/stage_v5_artifacts.py`, `build_v5_cutover_packets.py`
  (or the authorization tooling Terra confirms), `seed_week_schedule.py`,
  `publish_game_venues.py`, `publish_v5_ratings.py`, `publish_team_stats.py`,
  `publish_matchup_data.py`, `publish_to_db.py`, `select_public_run.py`,
  `backfill_v5_unconstrained_grades.py`
- Owner-role SQL: 2 inserts (approval + authorization) + the rollback script
- Neon: `prediction_runs`, `predictions`, `games`, `market_quotes`,
  `market_snapshots`, `prediction_market_selections`, `site_week_selections`,
  `current_week`, `v5_rating_snapshots`, `team_season_stats`, the four matchup
  tables + `matchup_data_publications`, `v5_model_bundle_approvals`,
  `v5_intended_update_release_authorizations`
- Docs: `docs/status.md`, repair-track completion matrix, Stage 7B plan note

---

## Implementation Tasks

### Task 0 — Confirm review inputs (done in planning; Terra re-verifies read-only)

- d2 run row: `published`/`pending`, 55/55, `display_only=true`,
  rating sha `c83b1423…`, bundle `a507d0c7…`, created 2026-10-08 16:56 UTC.
- Preview selection cites Amendment 9; Production hold state as above.

### Task 1 — Phase 0: Preview completion gap

**Commands (pipeline role, Preview):**

```bash
# 1a. Rating snapshots for the corrected w6live manifest
PYTHONPATH=src:. zsh scripts/ops/with_preview_env.sh uv run python scripts/pipeline/publish_v5_ratings.py \
  --rating-manifest-uri artifacts/research/data-first-football-v1/possession-v1/intended-update-2026/runs/v5-intended-update-2026-corrected-w6live-r1/rating-manifest.json \
  --environment preview --apply
# 1b. Team stats as-of 6 (verified candidate; --diff dry run first: only as-of-6 additions)
# 1c. Matchup data bound to the corrected rating + measurement manifests (--expect-payload-sha Preview equality; DB gates must pass)
```

**Gates:** `v5_release_policy` must cover the intended-update candidate before
1a writes — if it refuses, **stop for review; do not weaken the gate.**
Team-stats dry run must show no change to as-of 1–5.

**Acceptance:** `CFB_PUBLICATION_MODE=predictions zsh scripts/ops/run_web_local.sh preview`
shows Picks 55 games + notice; Ratings 138 post-W5 teams
(`current_teams.parquet` cutoff 2026-10-05: Notre Dame +1.88 … UTEP −0.64);
Week 6 matchup pages pass lineage gates; Weeks 0–5 routes unchanged.

### Task 2 — Phase 1: rollback script + Preview rehearsal (user reviews script first)

Write a rollback script restoring the exact prior state: delete
`site_week_selections`(2026,6); `current_week.active_run_id=NULL`; delete the
55 `predictions`, 58 week-6 `games`, week-6 market rows, the `prediction_runs`
row, `c83b1423…` snapshots, as-of-6 stats, matchup rows + publication-registry
row. Append-only history tables stay.

1. Apply in Preview (owner role, user-run); verify via the local site that the
   hold screen returns **and** the rating source reverts to `e80ae347…`.
2. Re-apply Tasks 1 + Preview selection forward so Preview ends in the open state.
3. **Phase 2 may not start until the user has reviewed the script and the rehearsal.**

**Rehearsal outcome 2026-10-09 (evening, recorded here; script pending user review):**
rollback `--apply` executed in Preview after two fail-closed aborts (unselected
market rows, then FK order — both rolled back atomically with Preview intact).
Final run deleted 7,879 rows and verified the exact hold screen (`current_week`
(2026,6)/NULL, 0 W6 games, weeks 0–5 intact; local site "Dropping Soon").
Requires the one-time Preview grant (`GRANT DELETE/SELECT ON
prediction_market_selections TO cks_preview_migrator`; that table is uniquely
`neondb_owner`-held). Re-apply forward deferred to resume (needs a clean tree
for the authorizer). `docs/status.md` notes Preview is on hold until then.

### Task 3 — Phase 2a: stage d2 artifacts to the production namespace

```bash
uv run python scripts/pipeline/stage_v5_artifacts.py --source preview --target production \
  --run 6=2026w6-v5repair-20261008-d2 --receipt <receipt-path>        # dry run
# review receipt, then --apply with --expected-receipt-sha256 + clean committed code (user-run)
```

Targets: `artifacts/production/predictions/year=2026/week=6/run_id=2026w6-v5repair-20261008-d2/{predictions.csv,manifest.json}`,
write-once with byte readback + signed receipt. (The existing staging dry-run
evidence covers only the c2 Weeks 0–5 set, not d2.)

### Task 4 — Phase 2b: admin inserts (owner role, user-run, exact payloads reviewed first)

1. `v5_model_bundle_approvals`: (`v5-intended-update-2026-v1`, `a507d0c7…`,
   first-live 2026/6, decision_ref=this contract). Required: `select_public_run`
   and `publish_to_db` both demand exactly one matching approval row; Production
   currently approves only `30c4f1eb…`.
2. `v5_intended_update_release_authorizations`: production/2026/6/d2,
   evidence `pending`, certified chain (forecast `500dfa0f…`, serving
   `d23172ac…`, verifier `74c9945f…`, artifact `be18fc6e…` at its production
   URI, rating `c83b1423…`), decision_ref=this contract.

Terra generates the exact payloads via the packet-builder/authorization tooling
and presents them; the user executes.

### Task 5 — Phase 2c: Production publish chain (`with_production_pipeline_env.sh`, dry runs first, applies user-run)

Order matters (learned from the Preview rehearsal):

1. `seed_week_schedule.py --source-lock conf/rebuild/successor_lock_w6live_v1.json --week 6 --environment production --apply`
   (seeds the 58 schedule rows; refused "extra" games otherwise).
2. `publish_game_venues.py --season 2026 --environment production`
   (dry run, then apply — venues upsert only for games already in Neon; the
   publisher's venue-city gate requires them).
3. `publish_v5_ratings.py --rating-manifest-uri <w6live manifest> --environment production --apply`.
4. Team stats as-of 6 → production (candidate + `--diff` dry run).
5. `publish_matchup_data.py` → production (corrected manifests,
   `--expect-payload-sha` Preview↔production equality).
6. `publish_to_db.py --year 2026 --week 6 --from-artifact --run-id 2026w6-v5repair-20261008-d2 --environment production`
   (fail-closed transaction; mirrored on the Preview invocation).
7. `select_public_run.py --year 2026 --week 6 --run-id 2026w6-v5repair-20261008-d2 --reason "Week 6 display-only Production release (<contract-ref>); pending, never frozen" --environment production`.

### Task 6 — Phase 2d: verify Production

- Local: `CFB_PUBLICATION_MODE=predictions zsh scripts/ops/run_web_local.sh production` —
  Picks (55 + notice), Results W6, Ratings (post-W5 corrected), W6 matchup pages,
  Weeks 0–5 unchanged, Performance prospective section still Week 5 only.
- Live: same checks against the deployed site (DB + ISR revalidation carry it;
  the publisher fires revalidation; no Vercel change).

### Task 7 — Phase 3: post-finals + bookkeeping

- After finals stabilize (~Oct 11–12):
  `backfill_v5_unconstrained_grades.py --week 6 --grades-only` on Preview +
  Production (user-run). Run stays `published`/`pending`; Week 6 is superseded
  by its corrected replay at the Stage 7B cutover.
- Update `docs/status.md` (Week 6 row: Production display-only), the
  repair-track completion matrix, and the Stage 7B plan: the cutover's
  "before" state now includes the d2 selection, corrected snapshots, as-of-6
  stats, 2 admin rows and staged artifacts.
- Validation: scoped pytest + ruff + `contracts-check` + web
  lint/typecheck/publication tests; `git diff --check`; session log.

## Amendments

### Amendment 1 (2026-10-09, Terra, mechanical): ratings publisher substitution

Task 1 named `publish_v5_ratings.py`. That script only accepts the legacy
rating-replay schema (`selected_candidate`, URI parents) and refuses every
intended-update manifest — including the served one. The correct tool for the
`v5_intended_update_2026_rating_manifest_v1` schema is
`publish_v5_intended_update_ratings.py` (same CLI shape, same target table,
full signed-chain verification in the dry run). Used for the Preview
projection: 1,624 rows for `c83b1423…`, verified (top: Notre Dame +1.88, Utah
+1.83, Alabama +1.80 — matches the R2 review). No scope change.

### Amendment 2 (2026-10-09, Terra, blocking): matchup leg has no consumable measurement manifest — release stopped

**Finding.** `publish_matchup_data.py` requires a measurement manifest with
`output_refs.observations` whose raw sha equals the rating manifest's parent.
The w6live rating manifest pins `parents.measurement_manifest_sha256 =
7865d353…`, which is the 6A rebuild *root* manifest (`rebuild/6a/
6a-rebuild-w5-20261007-r2/root-manifest.json`, sha verified) — it has no
`output_refs`, so the publisher fails with `KeyError: 'output_refs'`
(reproduced on the dry run). No standalone corrected measurement manifest
exists in R2 (all 13 are original-lineage). The Oct 8 matchup candidate
bypassed the publisher (read 6A states directly, bound to the 6A root sha) and
cannot be written as-is: the site binds W6 matchup data to rating sha
`c83b1423…`, not `7865d353…`. This is the "still deferred: matchup database
gates" item from Amendment 11 — it was never only about missing snapshots.

**Decision (user, 2026-10-09):** stop the release; send back to Sol for a
revised plan designing the bridge (a signed corrected measurement manifest or
a 6A-aware publisher mode, with its own independent verifier). Design
constraint for Sol: the w6live rating manifest is frozen, so its parent sha
(`7865d353…`) cannot change — the bridge must resolve that sha to consumable
observations (e.g. a 6A-aware loader asserting the root sha + signature, as
`build_matchup_candidate.py` and the Task 4 comparison already trust), then
bind output to rating sha `c83b1423…`. The candidate's 7/7 static gates show
the numbers reconcile.

**State left behind (all Preview-only, additive):** d2 still selected; corrected
snapshots (1,624 rows) + as-of-6 team stats (3,036 rows) projected — both are
needed by the eventual DB gates, so they stand. No Production write, no freeze/
close, no code changes. Tasks 2–7 not started. Contract stays `In Progress`
(blocked); resume at Task 1c once the bridge design lands.

### Amendment 3 (2026-10-09, Terra): bridge delivered — Task 1c complete in Preview, release resumed

Contract `03-matchup-6a-bridge.md` is Implemented (loader + signed gate-receipt
verifier + Week-6 log write scoping + 12 tests, full suite green). Task 1c proof
in Preview (all user-authorized applies):
- Bridge verifier signed + written to R2:
  `.../v5-intended-update-2026-corrected-w6live-r1/verification/bridge-verifier-manifest.json`
  (2,640 bytes; 11/11 gates).
- Matchup publish `--apply`: stats 1,656 + adjusted 549 + components 508 +
  registry row (`2026:intended_update:c83b1423…:08e22bae…`, weeks `[6]`); game-log
  write correctly 0 rows (no completed W6 games; served W0–5 provenance untouched).
- Payload sha `08e22bae…` deterministic across 3 independent builds;
  `verify_matchup_data` exit 0, 0 differing rows.
- Local Preview site: Picks 55 games + notice; W6 matchup page lineage `ready`;
  Ratings renders corrected post-W5; W5 page unchanged (see below).

**Task 5 ordering fix:** matchup publish runs *after* select in each environment
(the DB "selected source" gate requires the manifest to be the selected source).

**New finding requiring explicit accept:** selecting d2 in Production flips the
site-wide rating source to `c83b1423…`, so Weeks 0–5 matchup pages there will read
"Forecast and rating snapshots use different published lineages" (model sections
hidden) until the Week 7 cutover rebinds them. Preview's W5 page already shows
this state since the Oct 8 d2 selection — pre-existing, not caused by this work;
served W0–5 rows and bindings are byte-intact. Picks/Results/Ratings are unaffected.

### Amendment 4 (2026-10-09, Terra): timing notice hidden behind an opt-out flag (user-directed)

**Decision (user, 2026-10-09):** Week 6 ships with no timing notice and no
lineage labels anywhere. This overrides Amendment 9's notice rule for this
release only; the run's `validation.display_only` database flag, the
freeze/never-missed guards, the unconstrained grading path and the prospective
exclusion are all unchanged — the authoritative record still marks the run
display-only/pending, but the UI no longer tells casual visitors the picks
were generated mid-week rather than frozen pre-kickoff.

**Implementation:** `CFB_DISPLAY_ONLY_NOTICE=0` hides the notice on Picks and
Results (both call sites gated; default unset shows it, mirroring the
`CFB_MATCHUP_ENABLED=0` opt-out pattern); unit tests extended; web
lint/typecheck/publication-tests/build green; both modes verified against the
local Preview site. **Ops consequence:** the Production Vercel environment
needs `CFB_DISPLAY_ONLY_NOTICE=0` at release time (user/ops step).

## Risks and Edge Cases

- **Already-final games on the Picks tab:** 4 Thursday games are final and 5
  more kick off tonight; they show as picks until the Sunday backfill grades
  them. The notice explains the run covers only games unstarted at generation.
- **Line staleness:** market capture is Thu 16:19Z; Saturday lines may have
  moved (quote timestamps render on the cards). Accepted by choosing d2 over a
  fresh d3.
- **Mixed lineage until cutover:** Weeks 0–5 uncorrected, Week 6 corrected
  (ratings delta small: mean 0.33 margin pts vs served), Ratings tab flips to
  corrected post-W5 — the intent of this release.
- **No deselect:** the only way back to the hold screen is the Task 2 rollback
  (owner-role deletes). Never run it unrehearsed.
- **Cutover interaction:** Stage 7B before/after checks must account for the new
  Production rows (Task 7 records this). Amendment 10 already waives Week 6
  from the completed-prospective check.

## Definition of Done

- [ ] Task 1: Preview gap publishes applied; local Preview routes verified.
- [ ] Task 2: rollback script reviewed by user, rehearsed in Preview (hold screen
      + rating source reverted), Preview re-applied forward.
- [ ] Task 3: d2 artifacts staged to production namespace (signed receipt).
- [ ] Task 4: both admin rows inserted by user from reviewed payloads.
- [ ] Task 5: Production publish chain + selection complete (user-run applies).
- [ ] Task 6: local + live Production verification passes; Weeks 0–5 unchanged.
- [ ] Task 7: post-finals backfill done; docs updated; Week 6 never frozen/closed.
- [ ] Contract status updated to `Implemented`; session log closed.
