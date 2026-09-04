# Session: Fresh Preview Offseason-Context Admission

## TL;DR

- **Worked On:** Materialized and admitted the post-repair, Preview-only offseason context corpus bound to commit `786580ec58b76ade6489251f4c2b18af80e0430e`.
- **Outcome:** The context report is admitted and reconstructed-only. Returning production, recruiting, and coaching pass coverage; transfers and talent remain explicitly rejected. No direct/R2 model artifact has been written.
- **Plan Contract:** `docs/plans/2026-09-02/early-week-strength-prior-research.md`
- **Approval / Status:** User authorized staged implementation on 2026-09-04. Contract remains `In Progress`; the evidence checkpoint commit precedes direct/R2 reports.
- **Blockers:** User executes the evidence/status commit before direct or R2 research runs.
- **Next:** Run the direct Game 1–3 research report and the R2 prior tournament in Preview after Commit 2.

## Immutable Evidence

- **R1 coverage report:** `artifacts/research/rating-successor-v2/r1/r1-full-corpus-20260831-5f2a384/coverage.json` (`tournaments_permitted: true`).
- **Context source manifest:** `artifacts/research/rating-successor-v2/early-week-context-20260904-786580ec-r2/source-manifest.json`.
- **Admission report:** `artifacts/research/rating-successor-v2/early-week-context-20260904-786580ec-r2/admission-report.json`.
- **Admitted context ref:** `artifacts/research/rating-successor-v2/early-week-context-20260904-786580ec-r2/context-ref.json` (content SHA `6430bf713637cadb6bb27d71af4ab204936091638c647276d4b4b7e15b3d8a2a`).

## Context and Decisions

- The input R1 foundation is the certified `r1-full-corpus-20260831-5f2a384` artifact. The 2026 team universe uses the checksum-verified Silver games dataset `ff88396c6a6d3999d33e4dbd`; its immutable ref is retained under the new prefix.
- Historical CFBD retrievals retain their execution-time provenance and are reconstructed. Authentic 2026 pre-kickoff snapshots were reused rather than refetched.
- `returning_production`, `recruiting`, and `coaching` are admitted as reconstructed. Their minimum permitted-season coverage is 98.46%, 99.24%, and 100%, respectively; all exceed the 90% threshold.
- `transfer_portal` is rejected because CFBD lacks 2015 data. `talent` is rejected because no authentic nonempty 2026 pre-kickoff capture exists.
- The report is `activation_eligible: false`; it cannot support locked validation, refit, bundles, readiness, Neon activation, publication, or V4 changes.

## Validation

- [x] Preview R2 credentials and CFBD API key present without exposing values.
- [x] New immutable prefix preflighted empty.
- [x] Certified R1 foundation and 2026 Silver games parent resolved read-only.
- [x] Materialization completed with a complete source manifest.
- [x] Admission report is `state: admitted`, `feature_track: reconstructed`, and has the intended three admitted families.

## Amendments and Blockers

- None. The source/admission result matches the approved family boundary and preserves all research-only restrictions.

## Handoff Notes

- **Resume at:** User executes the evidence/status commit, then run the direct selection-only report and R2 tournament from the report/ref above.
- **Watch out for:** Use `--allow-reconstructed-context` only for the R2 Preview run. Do not read 2026 outcomes or use any report in a strict/locked/refit/publication flow.

**tags:** ["modeling", "ratings", "preseason", "research", "r2"]
