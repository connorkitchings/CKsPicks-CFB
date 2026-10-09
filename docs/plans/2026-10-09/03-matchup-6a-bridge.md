# 6A-Bridged Matchup Publication for the Corrected Lineage

- **Status:** Approved
- **Created:** 2026-10-09
- **Planner:** Sol (Plan Mode investigation; read-only review of the publisher, candidate tool, 6A run, manifests and gates)
- **Approval source:** User decisions in session 2026-10-09 — 6A-aware loader design, signed gate-receipt verifier, Week-6 write scoping, Preview proof included
- **Implementation log:** none yet (Terra executes via `implement-plan` on this exact path)
- **Commit policy:** Commit with implementation
- **Amends (does not replace):** `02-week6-display-production-release.md` (In Progress, blocked at Task 1c; see its Amendment 2). This contract delivers the bridge machinery + Preview proof; the release resumes there afterwards.

## Goal

Give `publish_matchup_data.py` / `verify_matchup_data.py` a verified 6A-aware
loading path so the corrected lineage (w6live rating manifest `c83b1423…`,
measurement parent `7865d353…`) publishes Week 6 matchup data bound to the
served rating sha — unblocking the stopped release at Task 1c.

## Current State (verified read-only 2026-10-09)

- `publish_matchup_data.py` → `mp.prepare_run` → `load_intended_update_artifacts`
  demands `output_refs.observations` from a measurement manifest whose raw sha
  equals the rating parent. The w6live parent (`7865d353…`) is the 6A rebuild
  root manifest (`rebuild/6a/6a-rebuild-w5-20261007-r2/root-manifest.json`, sha
  verified) — no `output_refs` → `KeyError: 'output_refs'` (reproduced on dry run).
- Rating side is fully consumable: w6live manifest passes schema/frozen/
  candidate/verifier checks; `output_refs` priors (276 rows), pregame_roles
  (1,316), current_roles (1,656) exist with checksums. `CANDIDATE_ID` matches
  (`ppp__rho_0_60__exposure__game_at_cutoff_v1`).
- Snapshots were projected row-for-row from the w6live frames, so bridge
  components built from the w6live priors/roles meet the 1e-12 snapshot gate
  by construction. 6A run exposes `states_2026/{observations,priors,
  pregame_roles,current_roles}.parquet` through `open_published_run` (root sha
  + signature) — the candidate tool proved the read path (static gates 7/7).
- `verify_matchup_data.py` shares `mp.prepare_run`, so one bridge serves both.
- Preview holds d2 selected + corrected snapshots (1,624 rows) + as-of-6 stats;
  the DB "selected source" gate passes there today. Production untouched.

## Scope

### Included

- 6A-aware loader + CLI pass-through flags (default path byte-unchanged).
- Signed bridge verifier manifest + publisher assertion pre-write.
- Week-6 write scoping for the game-log table (gates see the full payload).
- Unit + local-Postgres tests, incl. a served-rows no-overwrite proof.
- Preview proof: dry run → DB gates → `--apply` → `verify_matchup_data` exit 0
  → local route check (W6 page `ready`, W0–5 unchanged).
- Handoff annotation on contract `02` for release resume.

### Excluded

- Any change to the default (served-lineage) loader behavior.
- Schema/migration changes (keys stay lineage-unaware by design; scoping, not
  schema, prevents overwrite).
- Retraining, refit, new/modified rating or 6A artifacts; second-implementation
  verifier (user chose signed gate-receipt).
- Production writes (Preview T4 apply is user-run or explicitly authorized).
- Resuming the release itself (belongs to contract `02`, Tasks 1c–7).

## Affected Components and Contracts

- `src/cks_picks_cfb/data/matchup_publish.py` — new `load_6a_bridged_artifacts()`;
  `prepare_run` selects it only when `--six-a-run-id` + `--six-a-root-sha256`
  are both given.
- `scripts/pipeline/publish_matchup_data.py`, `verify_matchup_data.py` —
  pass-through flags only.
- `scripts/pipeline/build_6a_bridge_verifier.py` (new) — asserts inputs,
  rebuilds via publisher builders, runs all gates, signs verifier manifest in
  R2 beside the w6live run.
- `tests/test_matchup_6a_bridge.py` (new).
- R2: `.../v5-intended-update-2026-corrected-w6live-r1/verification/bridge-verifier-manifest.json`
  (new signed artifact); Preview Neon matchup tables + `matchup_data_publications`
  (T4 apply only).
- Contract `02-week6-display-production-release.md` — resume annotation on
  completion (not edited otherwise).

---

## Implementation Tasks

### Task 1 — 6A-aware loader + CLI flags

**Changes:**
- `matchup_publish.py`: `load_6a_bridged_artifacts(storage, rating_manifest_uri,
  six_a_run_id, six_a_root_sha)`:
  - Rating side: identical checks to `load_intended_update_artifacts`
    (schema/frozen/candidate/verifier match, children checksums for priors,
    pregame_roles, current_roles from `output_refs`).
  - Measurement side: assert rating `parents.measurement_manifest_sha256 ==
    six_a_root_sha`; open the 6A run (`open_published_run`: root sha +
    `verify_signed_payload`); read `states_2026/observations.parquet`, record
    its real bytes sha (never a placeholder).
  - Return `Artifacts`: rating manifest/uri/sha (`c83b1423…`) and run_id
    (`v5-intended-update-2026-corrected-w6live-r1`) from w6live (so components
    reference the projected snapshots); measurement manifest = 6A root dict,
    sha = root sha, URI = root-manifest URI; priors/roles from w6live refs;
    cutoffs from w6live (covers as-of 6).
- `prepare_run`: use the bridge iff both `--six-a-*` flags are present.
- Both CLIs: `--six-a-run-id`, `--six-a-root-sha256` pass-through.

**Acceptance:** default (served-lineage) invocations byte-identical; bridge dry
run on the w6live/6A pair loads without error.

### Task 2 — Bridge verifier script

**Changes:** `scripts/pipeline/build_6a_bridge_verifier.py` — loads via the
bridge, rebuilds the payload, runs static + DB gates, writes the signed
`bridge-verifier-manifest.json` (rating/root/observations/children/payload
shas + gate summary; same signing scheme as the rating verifier). Publisher
asserts the verifier's payload sha equals its own build before any write.

**Acceptance:** verifier refuses wrong root sha, unsigned/tampered root,
tampered observations bytes, mismatched parent — each with a distinct error.

### Task 3 — Tests

**Changes:** `tests/test_matchup_6a_bridge.py` — accept fully-verified set;
reject cases from Task 2; local-Postgres test (mirroring the existing DB test)
proving a scoped `--weeks 6` write leaves served W0–5 rows byte-identical and
`compare_db_to_payload` clean; write-scoping unit test (log restricted to the
publication week's games post-gate).

**Acceptance:** new tests + full suite green; ruff clean.

### Task 4 — Preview proof (dry runs first; `--apply` user-run or explicitly authorized)

1. Bridge dry run in Preview (w6live + 6A pins); DB gates must pass
   (selected-source gate passes: d2 selected).
2. `--apply`; `verify_matchup_data.py` exit 0 with the same pins.
3. Local site (`CFB_PUBLICATION_MODE=predictions zsh scripts/ops/run_web_local.sh preview`):
   W6 matchup page lineage `ready`; W0–5 matchup pages + Ratings unchanged.
4. Annotate contract `02` Task 1c complete-in-Preview with payload sha + verifier
   URI, plus the Task 5 ordering fix: matchup publish runs *after* select in
   each environment (the DB gate requires the manifest to be the selected source).

**Acceptance:** payload sha recorded; verifier URI recorded; local routes verified.

## Testing Strategy

1. Loader accept/reject matrix (Task 3) — shape, signature, sha and binding guards.
2. No-overwrite proof on disposable local Postgres (served fixture rows + scoped write).
3. Preview proof (Task 4) — gates, verifier exit 0, local route check.
4. Regression: full `pytest -q`, `ruff format . && ruff check .`,
   `make contracts-check`, web lint/typecheck/publication tests.

## Risks and Edge Cases

- **1e-12 snapshot gate:** met by construction (w6live roles frames feed both
  snapshots and components). If the dry run disagrees, stop — do not loosen
  the tolerance; return to Sol.
- **Stale-gate vs scoping:** the stale check sees the full payload (served keys
  present → passes); scoping applies at write only. If served keys ever fall
  out of the built payload, the gate fails closed — correct behavior.
- **Preseason components:** default `--weeks 6`. Terra verifies the W6 page
  renders `ready`; widen scope only with page evidence, never speculatively.
- **No Production writes** in this contract; Preview T4 apply needs explicit
  authorization. Never freeze/close any run here.

## Definition of Done

- [ ] Task 1: loader + flags merged; default path unchanged (tests prove it).
- [ ] Task 2: verifier script merged; refusal matrix green.
- [ ] Task 3: new tests + full suite + lint + contracts-check green.
- [ ] Task 4: Preview proof green (payload sha + verifier URI recorded; local
      routes verified); contract `02` annotated for resume.
- [ ] Contract status updated to `Implemented`; session log closed.

## Amendments

(Minor mechanical amendments may be appended by Terra per
`docs/plans/index.md` lifecycle rules. Material deviations stop and return to Sol.)
