# V5 intended-update 2026 production release packet

**Decision status:** Pending. This packet is the separate exact release decision required by [Task 6](v5-intended-update-2026-production-repair.md). Its machine-readable [payload](v5-intended-update-production-release-packet.json) has SHA-256 `deb1fd34ebd98410eedce6e7ae7088e54da95dd6d36ca6a1d7ac90a595781fcc`. No successor production authorization, prediction publication, rating projection, score publication, or selection has occurred.

## Proposed production result

Select the repaired V5 rating source `e80ae3473d88d0c458325c19343e7dae6447924d9abad29b15089bc19cacd26b` and refitted bundle `30c4f1eb0ef5b3c1e30b2a877b4553923c3b5ff68832eea0282e37e625b13531` across all six displayed weeks. Weeks 0–4 are **retrospective replay**: 215 replaced predictions, 199 spread and 159 total grades, and new season totals 93–103–3 spread and 82–77–0 total. Original production totals are 94–105–3 spread and 87–78–0 total. Week 5 is a pre-kickoff live run with 56 predictions and 112 quote selections; it has no grades. This is a specification repair and historical replacement, not evidence that betting performance improved prospectively.

| Week | Current production run (rollback) | Replacement run | Games | Production run-manifest SHA-256 |
| --- | --- | --- | ---: | --- |
| 0 | `2026w0-v5replay-bestquote-20260926-r3` | `2026w0-v5repair-20260929-p1` | 8 | `60118f87853c9c04eee86d3b3608a97aeca8a38d813b997e729150b7f9d3a11b` |
| 1 | `2026w1-v5replay-bestquote-20260926-r3` | `2026w1-v5repair-20260929-p1` | 43 | `7c264bfd212b90e089d780a5a5076e87d0b57d01bafb21cc27cede6689da5f3d` |
| 2 | `2026w2-v5replay-bestquote-20260926-r3` | `2026w2-v5repair-20260929-p1` | 49 | `1d44e0a8864a843163af7ba27c14129ad9a316ba50601d49a3761a9c276b59b7` |
| 3 | `2026w3-v5replay-bestquote-20260926-r3` | `2026w3-v5repair-20260929-p1` | 57 | `a7b49a5300d5e971122598b7d09da2320966be12c553f1826341ccf889a35588` |
| 4 | `2026w4-v5replay-bestquote-20260926-r3` | `2026w4-v5repair-20260929-p1` | 58 | `58464ed732288195ffaef0fcb2e214e2cc47f48b2adfb265287347e0a7af1dc5` |
| 5 | `2026w5-5d436e58c072` | `2026w5-v5repair-20260929-p2` | 56 | `490c09b4cb67b6161a91e5920bd6091dae28619a08edc5247ea5ebb033c6bc8d` |

The exact packet includes each production-namespace prediction/scored artifact URI and checksum, six run-specific authorization records, the model-pair approval, the all-six-week selection, and the reverse rollback selection. The production and Preview artifact credentials intentionally target the **same approved R2 bucket**; environment separation is enforced by Neon branch and immutable `artifacts/production/` versus `artifacts/preview/` paths. Signed rating, bridge, forecast, serving, verifier, and Silver parents already exist in that shared bucket. The new production-namespace run and scored files have been constructed and independently validated in local preflight only.

## Evidence and timing

- [Preview rehearsal](v5-intended-update-preview-rehearsal.md) selected the exact replacement set, froze Week 5 at `2026-09-29T20:43:53.376950Z` before `2026-10-02T00:00:00Z` first kickoff, rolled back all six weeks, and reactivated them. Preview readback matched ratings, game cards, grades, and season totals.
- The p2 market capture occurred at `2026-09-29T20:28:55Z`; all 56 scheduled games had spread and total lines. A subsequent source check at `2026-09-30T02:10:51Z` still found all 112 matching provider quotes, with six quote values moving across five games. The packet represents the timestamped p2 snapshot. A new market capture and publication may be needed before final Week 5 freeze; Week 5 must remain ungraded until certified finals.
- A read-only production check found migration 0018 present, zero successor authorizations, the six original runs selected, and original season scores. The exact six-week batch packet passed the production selector's read-only current-state preflight. The 1,370-row rating projection passed its verified-source dry run. Run authorization validators passed against an overlay containing the proposed production prediction bytes.
- The local web build and Preview-backed ratings, predictions, and performance pages passed. Vercel production deployment `dpl_55FXEHdkUWy2CPoTfuTzxqEVK2Vt` is READY at commit `8a12e98efa24b6a3acbbfd11a43f74fcb4120eb6`. The web CI job passed. The Python formatting job found a single formatting-only issue in `scripts/pipeline/build_v5_intended_update_2026.py`; it was corrected locally and must pass CI after the correction is pushed before production activation.

## Ordered execution after exact approval

1. Push/deploy the reviewed code and verify its deployed SHA, selected-source ratings queries, and performance-page behavior. Recheck production branch identity, six rollback IDs, first kickoff, certified finals, and live market coverage. A changed game population, model lineage, or closed kickoff gate voids this packet. Record any quote movement and schedule the final market refresh/freeze; do not call the p2 lines current if they have moved.
2. Write the packet's six prediction CSVs/manifests and five scored CSVs/manifests to `artifacts/production/` in the shared R2 bucket with write-once exact-hash readback. Do not overwrite any existing object.
3. Using the verified production admin branch, insert the exact successor model-pair approval and six run authorizations from the payload. The restricted pipeline role cannot do this. Apply the 1,370 verified rating snapshots with the restricted production pipeline role.
4. Publish all six authorized prediction runs with `--no-update-current`, score the five completed replay runs from their exact scored artifacts, and verify game/quote/grade counts without changing selection.
5. Atomically select all six replacement runs using the payload's `batch_selection`; verify the six pointers, current-week pointer, selected rating SHA, 215 completed-game predictions, 199/159 grades, season statistics, and live site pages. If any invariant fails, atomically apply `batch_rollback` and verify the original public record.

## Decision — 2026-09-29

Pending the user's explicit decision on packet SHA `deb1fd34ebd98410eedce6e7ae7088e54da95dd6d36ca6a1d7ac90a595781fcc`. Approval authorizes only the exact run IDs, artifacts, score replacements, and rollback above, subject to the listed pre-activation checks. It does not authorize grading Week 5 or skipping its final market/freeze workflow.
