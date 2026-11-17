# V5 offensive and defensive ratings audit

- **Status:** In Progress
- **Created:** 2026-11-08
- **Planner:** Sol
- **Approval source:** Owner's 2026-11-08 request, "PLEASE IMPLEMENT THIS PLAN", naming this contract and reproducing its complete specification.
- **Implementation log:** `session_logs/2026-11-08/02-v5-ratings-audit-implementation.md`
- **Commit policy:** Separate plan commit; git operations remain user-controlled.

## Goal and acceptance

Produce separate offensive and defensive audits explaining the Georgia–Florida discrepancy, validating calculations and measurements, and checking whether matchup ratings match forecast inputs. Classify findings as expected behavior, methodological concerns, or implementation/data/presentation defects. Every check reports agreement, concrete discrepancies, or unavailable evidence.

Georgia–Florida, `game_id=401856734`, is the Pre-Week 9 / Post-Week 8 state under `conf/season/2026/revision_manifest_w9_v2.json` and `conf/season/2026/model_manifest_v1.json`:

| Offensive measure | Georgia | Florida |
| --- | ---: | ---: |
| Raw PPP | 3.254 | 3.231 |
| Adjusted PPP | 3.601 | 3.712 |
| Offensive rating | 1.839 (#5) | 1.857 (#4) |

Completion requires reproducible population, adjustment, scale/prior, quarantine, Neon projection, and matchup-to-forecast checks. A documented defect is a valid audit outcome; unavailable evidence must never be declared verified.

## Baseline and constraints

- Primary scope: ten pregame generations (Weeks 0–9, including preseason) and nine post-week generations (Weeks 0–8) from Week 9 v2. Exclude completed Week 9 observations from Week 10 v1 from this historical reconstruction.
- Separate serving scope: capture active Production once in a read-only repeatable-read transaction and check its Weeks 0–9 matchup/forecast lineage against its own pinned revision and prepared artifacts. Later revisions never replace the historical baseline.
- Planning inspected clean `dev` at `f7b8551c`; implementation starts in an isolated worktree and records audit-code and deployed-web-code provenance. Current release/week identifiers remain solely in `docs/status.md`.
- Week 9 v2's exception digest is `a9c7541e2db0b1769ba0aa514d2ab226b74ba7aa7cf49785a578a00366d39237`. Read the historical file with `git show 5fecf08eccfc6a8d0d76ccb02ffe176acad1423b:conf/season/2026/score_reconciliation_exceptions.json`, verify that digest, and preserve the checkout and manifest.
- Preliminary checks reproduced 276 Week 9 role states within floating-point precision; this proves arithmetic agreement, not source quality or methodological reasonableness.
- The pinned 2025 terminal file returns offense center/spread/sign `1.6786570621268924 / 0.9551072150270865 / +1` (230 teams), defense `2.72226674035986 / 1.2234980691939807 / -1` (227 teams). Reconcile requested approximate centers `1.623` and `2.647` if reproducible, otherwise mark unverified. Demonstrate team-equal weighting, role-specific coverage, denominator and FBS/FCS composition effects rather than assume the cause.
- Read-only R2 and Neon only. Preserve V5, forecasts, historical records, schemas, production code, and weekly operations. No provider captures, prepare/release commands, model fitting, or deployment.

## Ordered changes

1. Implement `scripts/analysis/audit_v5_ratings.py`, pure computations in `src/cks_picks_cfb/audit/v5_ratings.py`, and tests in `tests/test_v5_ratings_audit.py`. CLI: `--model-manifest PATH`, `--revision-manifest PATH`, `--score-exceptions-git-ref COMMIT`, repeatable `--run-manifest PATH`, `--environment production`, `--last-pregame-week 9`, `--report PATH`, `--evidence PATH`. Require explicit R2 configuration and checksum verification. Supply prepared manifests for baseline and active release; missing original feature artifacts leave verification incomplete, never silently substitute reconstructed features. JSON records input/code hashes, cohorts, check results, numerical differences, adjustment/contribution ledgers, exclusions and per-game forecast comparisons.
2. Compare Georgia/Florida FBS-vs-FBS `team_possession_stats` with full usable `IntendedUpdate`/`team_possession_adjusted` populations for both roles and every generation: games, opponents, points, possessions, PPP, ranks. Separate direct evidence differences from FCS opponent-graph context.
3. Build pass 0–4 ledgers for both teams and their played opponents through Week 8: role, raw PPP, exposure, opposite-role center, opponent estimate, resulting adjustment. Explain Florida's +0.481 and Georgia's +0.347 PPP. Independently verify exposure-weighted game-specific adjusted PPP equals pass-4 cumulative adjusted value when context is complete; show missing-context fallbacks separately. Show exact historical scales, terminal exposure, prior mean/variance/weight/contribution and each game contribution for both teams and roles; verify posterior mean/variance independently.
4. Enumerate every Weeks 0–8 team-game-role failing `usable_ppp_mask`, reasons, score reconciliation, pinned exception membership, and all four role statuses. Trace scoring/possession evidence for every affected game, including Ole Miss at Texas `401856732`. Establish whether broken scoring removes own offense/opponent defense while retaining the opposite scoring pair. Trace one-hop/two-hop paths to Georgia/Florida. Remove remaining usable edges of partially quarantined SEC games individually and jointly to measure diagnostic graph sensitivity; invent no scores and change no production input.
5. Compare independently recomputed baseline and active-release generations with existing `season_release_team_rating_components` and `season_release_team_possession_adjusted`, preserving pregame/post-week cutoff semantics. `projection_football.py`/`matchup_data.py` already stage both; `web/src/lib/matchup.ts` currently reads neither. Evaluate their fields, provenance joins and gaps for a later explanation feature; no UI/schema implementation.
6. For `401856734` and every forecast-bearing Weeks 0–9 game, follow `getRatingsAsOf(2026, game.startDate.getTime())`: actual period helper, source qualification, current-class lookup, preseason fallback. Compare selected team values with exact original pregame states and `home_offense`, `home_defense`, `away_offense`, `away_defense` features for spread and total lineage. Record cutoffs, source hashes and per-field differences; unequal timestamps may be valid but value equality must be demonstrated. Enumerate games without forecasts.
7. Write `docs/modeling/v5_offense_defense_ratings_audit_2026.md` with separate offense/defense conclusions, case study, recommendations and limitations; link `docs/modeling/evidence/v5_offense_defense_ratings_audit_2026.json`. Register this contract in `docs/plans/index.md` and report under 2026 Direction in `mkdocs.yml`.

## Validation

- Absolute numeric tolerance `1e-10`; exact keys, populations, roles and provenance.
- Test complete/missing opponent context, unequal exposure, FCS inclusion, zero/missing measurements, duplicate contributions, future evidence, defensive sign.
- Test asymmetric quarantine and its opponent-role/graph effects; corrupt components/adjusted values, mismatched features, wrong periods and missing original artifacts.
- Run new audit tests, existing intended-update tests, scoped Python lint/format checks, frozen historical and captured active comparisons.
- Preserve failed checks; do not repair inputs to force agreement. Run strict MkDocs and `git diff --check`; check report/JSON consistency, credentials and live run-ID hygiene.

## Handoff/amendments

Owner has approved implementation of this exact contract. Persist contract/planning log in an isolated worktree; use a fresh Terra worker under `implement-plan`. User controls commits and pushes. Implementation may document defects/concerns without correcting production. Missing evidence prevents verification of affected checks. Completed Week 9 expansion, model-semantic, schema/UI or production changes require a reviewed amendment/separate contract.

Mechanical baseline reconciliation (2026-11-08): implementation starts from `7505a4c20940063eeb268c36e9fb80b71d311400`; intervening changes concern Week 11 rollover, automation and status only. Audit/model/web calculation files are unchanged; preserve those operations outside audit scope. The orchestrator persists this contract and delegates implementation to fresh workers, with one worker owning each coupled file group.

Implementation results (2026-11-08): CLI, independent arithmetic/source checks, tests, report, JSON evidence and documentation registration are implemented. The final read-only run verifies all 19 baseline and 19 active component generations, nine adjusted generations in each scope, 1,776 independently rebuilt active source observations, and selected-current versus projected-pregame values for 500 games in each scope. Thirty focused tests, scoped Ruff checks and strict MkDocs pass. See the [audit report](../../modeling/v5_offense_defense_ratings_audit_2026.md) and implementation log for limitations and diagnostic sensitivity findings.

The contract remains **In Progress** because original forecast-artifact verification cannot be completed: the historical baseline original manifest and prepared parquet files are unavailable, and only the active original receipt manifest could be recovered. Original feature/rating/prediction parquet checks remain explicitly unavailable. Two non-case predecessor-prior checks and exact historical 2025 division membership also remain unavailable; these are documented rather than silently inferred. Restoring the original artifacts and rerunning their checksum-bound comparisons is the precise next verification step. No model/serving correction or artifact-retention implementation is included in this contract.

Mechanical implementation details: the CLI permits omitting repeatable `--run-manifest` arguments so missing originals can be documented while all available checks execute. Original artifact presence and comparison failures propagate into scope/report statuses. Used input manifests and prepared artifacts are protected from output-path collisions, and failures are sanitized. The machine evidence is compact JSON; detailed pass ledgers retain the case teams and their opponents, while all cohort discrepancies and source quarantine ledgers remain available. Deployment provenance and reviewed narrative are appended after computation and are explicitly labeled as review additions.
