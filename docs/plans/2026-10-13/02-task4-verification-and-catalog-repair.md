# Task 4 Verification and Catalog Registration Repair (6a-task4-w6-r2)

- **Status:** In Progress
- **Author:** Sol (reconstructed) / Terra Implementation Contract
- **Approved By:** User (2026-10-13)
- **Implementation Session Log:** `session_logs/2026-10-13/03-task4-verification-repair.md`
- **Scope:** Repair Task 4 population scope across chained extensions, two-lineage rating controls, kickoff revision evidence binding, recover Preview catalog registration for published 6A root, and generate/verify/publish 6a-task4-w6-r2.

---

## Context & Principles

1. **Preserve Failed r1:** The failed `6a-task4-w6-r1` and its verification record are preserved as immutable create-once evidence. We produce `6a-task4-w6-r2` for corrected evidence.
2. **Preserve Published 6A Root:** The published 6A root (`6a-rebuild-w6-20261012-r2`, raw sha256 `9d218543eec7eda149bbb5ba446b5f73f33b8ae107d5a7da20bdbe00f8d007c3`) and its 11-stage build remain completely unchanged.
3. **Environment Security:** Use `with_preview_env.sh` for Preview operations. Read comparison tables and publication metadata in consistent, read-only snapshots.

---

## Baseline Reconciliation

- **6A Rebuild Run:** `6a-rebuild-w6-20261012-r2`
  - Published to Preview R2 key: `rebuild/6a/6a-rebuild-w6-20261012-r2/root-manifest.json`
  - Raw Root SHA-256: `9d218543eec7eda149bbb5ba446b5f73f33b8ae107d5a7da20bdbe00f8d007c3`
  - Embedded Manifest Checksum: `d5b0d07f59d48b1111ca99ff1eec2476d1e44f5bfcb3f28d89a74aa9fb8814ad`
- **Task 4 r1 (Failed Baseline):**
  - Run ID: `6a-task4-w6-r1`
  - Preflight SHA: `08dc6816484b1362870925d7a133582fd07347f44028fb7cf0397b97709e577d`
  - Verification Verdict: Failed (`verify.json` SHA `ba2dc3434f7888a614249ea6947c7e264fbc3e2acb0f9a4170ed0ab7fcc77ec2`)
  - Attribution: Passed (`f7417d8c…`)
  - Published comparison: Failed on missing Week 5 measurements and baseline history control (`matches_published: false`)
  - Receipt: Failed on catalog verification (`0` of `49` versions present)

---

## Five Repair Steps

### 1. Repair Population Scope Across Chained Extensions
Update `lock_scope()` to traverse `previous_extension` (or base locks recursively), collecting all added games and recorded kickoff revisions. Reject malformed history, conflicting revisions, and inconsistent game identities.
Derive addition scope per table, bound to the inspected publication baseline:
- **Measurements:** account for the 56 Week 5 and 58 Week 6 games absent from that published population (`team_game_measurements` only contains games up through Week 4 in Preview).
- **Rating components:** continue comparing the 508 published Week 6 rows; retain the separately identified 276 new rows as additions.
- **Other tables:** establish their own coverage rather than applying a global week boundary.
Do not define acceptable additions merely as whatever happens to be missing from the database.
- **Validation:** chained-extension fixtures, mixed table coverage, unexpected missing historical rows, conflicting revisions, and published rows incorrectly placed in addition scope.
- **Acceptance:** expected additions are completely enumerated; no unexpected population difference is suppressed.

### 2. Repair the Two-Lineage Rating Controls
Partition published components by their recorded rating-manifest provenance:
- `v5-intended-update-2026-ratings-v1`: reconstruct using its `r9` lineage.
- `v5-intended-update-2026-corrected-w6live-r1`: reconstruct using its corrected lineage.
Resolve full manifest URIs and hashes from publication metadata. Verify the manifest parents and reconstruct controls using their bound historical inputs, observations, priors, and cutoff policy. Assign the correct run identity when generating component keys.
Require every compared component to belong to exactly one control. Keep control reproduction separate from attribution of changes introduced by the new rebuild.
- **Validation:** both lineages together, incorrect manifest bindings, unknown runs, overlapping partitions, missing partitions, and a deliberately altered Week 6 rating value.
- **Acceptance:** both controls reproduce their published values, apart from the exact timestamp differences covered by Step 3. All 512 previously differing rows are accounted for.

### 3. Bind the Four Kickoff Revisions to Evidence
Recover the recorded Week 5 revision through extension history. For the three Week 6 revisions, create a comparison-evidence artifact that binds the published source and pinned Silver/lock source by full hashes:

| Game ID | Matchup | Published UTC | Built/locked UTC |
|---|---|---|---|
| `401862787` | Charlotte @ Memphis | Oct 3, 19:30Z | Oct 3, 15:00Z |
| `401862797` | Rice @ East Carolina | Oct 10, 20:00Z | Oct 10, 17:00Z |
| `401856827` | Kansas @ Utah | Oct 11, 02:15Z | Oct 11, 00:00Z |
| `401856808` | Hawaii @ Arizona State | Oct 11, 01:30Z | Oct 11, 02:30Z |

Pin this evidence in the new Task 4 plan (`conf/rebuild/6a_task4_w6_v2.yaml`). Attribute only matching `cutoff_utc` cells; rating-value changes remain subject to the controls.
- **Validation:** all 16 expected cells, reversed timestamps, altered timestamps, unlisted games, conflicting evidence, and numeric drift accompanying a valid timestamp revision.
- **Acceptance:** exactly the evidenced timestamp changes are explained. The immutable source lock and published 6A root remain untouched.

### 4. Recover Catalog Registration for the Existing 6A Publication
Add a narrow catalog-only recovery command (e.g. `scripts/pipeline/recover_6a_catalog.py`), reusing `catalog_publish.collect_entries()` and `register_entries()`. It should default to dry-run and require the exact root URI, full raw root hash, expected code SHA, and explicit `--apply`.
The command must:
- Validate the signed root and hash-check its referenced objects.
- Derive the expected dataset-version set and reconcile the reported 49 versions.
- Check external dependencies and existing catalog rows for conflicts.
- Register schemas, versions, dependencies, captures, and recorded quality results in one Preview transaction.
- Write no R2 objects and change no serving tables.
This avoids republishing the root whose publisher SHA is absent. Preserve that historical limitation in a separate recovery record.
- **Validation:** wrong role/bucket/hash, conflicting existing rows, missing parents, transaction rollback, and an identical retry.
- **Acceptance:** independent readback confirms all expected versions and metadata; the retry writes zero rows; the 6A root’s bytes remain identical.

### 5. Generate, Verify, and Publish Corrected Task 4 Evidence (6a-task4-w6-r2)
After the repair code, evidence pins, and new plan are reviewed and committed through git workflow:
- Preflight `6a-task4-w6-r2` from a clean committed baseline.
- Build its three Task 4 stages against the existing published 6A root. No 11-stage 6A rebuild is planned.
- Regenerate comparison and receipt artifacts after catalog recovery.
- Run focused scope, comparison, receipt, catalog, publisher, and immutability tests.
- Run full Task 4 verification. Partial verification cannot authorize publication.
- Dry-run the designed publisher, publish only after all required checks pass, independently read back every published hash, and prove an identical retry writes nothing.
- **Acceptance:** attribution, published comparison, and receipt all pass; catalog coverage is complete; publication readback and idempotence pass. The original failed r1 evidence remains intact.
