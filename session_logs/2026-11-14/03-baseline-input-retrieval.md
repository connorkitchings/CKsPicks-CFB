# Session: Baseline input retrieval (read-only)

## TL;DR

- **Worked On:** The owner-approved retrieval named in the baseline audit contract: Historical V5 control inputs, the serving bridge manifest and bundle, and the `6a` rebuild manifests.
- **Outcome:** 338 objects mirrored locally with hashes recorded. The Historical V5 control inputs now load offline. The serving bridge's fitting is established from its manifest. Historical rating states for the operational recipe exist in storage but were not fetched.
- **Plan Contract:** [`docs/plans/2026-11-14/01-v5-baseline-audit-and-analysis-framework.md`](../../docs/plans/2026-11-14/01-v5-baseline-audit-and-analysis-framework.md)
- **Approval / Status:** Owner approved the retrieval on 2026-11-14 ("Approve retrieval"). Contract stays `Draft`.
- **Blockers:** The 12 row-level outputs of the 2026-09-28 repair experiment were not located.
- **Next:** Owner decides the next executable scope in the contract: fetch `historical-states.parquet` and the `w5` rebuild manifests, and choose the route for step 2's historical reproduction.

**tags:** ["model-research", "baseline-audit", "retrieval", "ratings-lab"]

## Context and Decisions

- Preview read credential only; GET, HEAD and LIST only. The `CFB_R2_SOURCE_*` credential was used for four HEAD probes, which returned 404; everything needed is in the Preview bucket. The default `CFB_R2_*` credential was not used.
- The control inputs were retrieved by running the project's own loader (`load_v5_control`) against a recording reader, so the mirror holds exactly the objects that loader reads and each child passed the loader's hash check.
- Parquet data files of the rebuild run and `historical-states.parquet` were listed but not fetched; the approved scope named manifests.
- No replay, scoring or model run. The loader was run only to read and verify inputs.

## Work Completed

- Mirrored 319 control-input objects (10.0 MB) to `~/cfb_ratings_lab_v6/source/`; both pinned manifests match; an offline reload from the mirror alone returns the same three tables.
- Mirrored the serving bundle (hash equals the model-manifest pin), its bridge manifest and verifier manifest, and the `w6` rebuild root manifest plus 15 summaries.
- Recorded how the serving bridge was fitted and five observations from the files in the contract's retrieval section.

## Files Modified

- `docs/plans/2026-11-14/01-v5-baseline-audit-and-analysis-framework.md` — retrieval section, updated capability table and next scope
- `docs/plans/index.md` — state line
- Outside the repository: `~/cfb_ratings_lab_v6/source/` (mirror and two index files)

## Validation

- [x] `uv run mkdocs build --strict`
- [x] `git diff --check`
- [x] Pinned hashes: measurement manifest, rating manifest and serving bundle equal their pins
- [x] Offline reload of the control inputs equals the online load (row and column counts)

## Amendments and Blockers

- The earlier inventory statement that no historical replay of Operational V5 exists is corrected in the contract: historical states exist in the serving bridge run; earlier-only predictions were not found.

## Handoff Notes

- **Resume at:** "Next executable scope" in the contract.
- **Watch out for:** the serving bundle is fitted through 2025 and must not be used to score 2022 to 2025. The serving bridge parent is the `w5` rebuild while serving priors come from the `w6` rebuild; treat consistency as an open question.
