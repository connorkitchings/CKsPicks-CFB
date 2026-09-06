# Session: Phase 2d Recertification Planning

## TL;DR

- **Worked On:** Investigated and documented the Phase 2d recertification,
  eligibility, and Preview capture-activation contract.
- **Outcome:** The Phase 2c ref set is the sole certification root; legacy
  blockers remain historical exclusions. The user selected full staged rollout,
  user-managed GitHub secrets, and a normal fast-forward of `main`.
- **Plan Contract:** `docs/plans/2026-09-06/04-phase2d-recertification-eligibility-and-capture-activation.md`
- **Approval / Status:** User explicitly authorized the exact plan on 2026-09-06; implementation begins after this documentation checkpoint.
- **Blockers:** GitHub remote activation later requires the user’s normal push
  and six user-managed repository secrets.
- **Next:** Implement the committed-code checkpoint; do not run audit writes,
  provider calls, or remote activation until that checkpoint is committed.

## Context and Decisions

- Phase 2c completed with 80 verified outputs, zero blocking reconciliation
  conflicts, no 2020 rows, and a sealed ref-set SHA-256
  `b3023ab5b7a304ddbc81ae2feca56238959520a54b3a75ed9be136f5d8f51df3`.
- Current observed minima exceed the inherited strict coverage gates: 98.19%
  FBS-FBS regular detail coverage and 97.35% FBS-FCS regular detail coverage;
  all observed postseason detail is 100%.
- The old Phase 1 v3 audit retains two non-canonical research parquet blockers
  and unsupported historical results. Phase 2 Amendment 2 permits their exact
  historical exclusion; they do not block selected Phase 2c certification.
- GitHub `main` is an ancestor of local `main` but 115 commits behind. The
  automation workflow and enable variable are absent remotely, and GitHub has
  no repository secrets configured.

## Validation

- [x] Inspected the Phase 2c ref set, Phase 1 v3 outputs, coverage, existing
  audit/eligibility/capture code, workflow, session logs, local branch, and
  GitHub read-only state.
- [x] `git status --short --branch` shows only unrelated `.opencode/`.

## Handoff Notes

- **Resume at:** Use the repository-local `implement-plan` skill against the
  linked Phase 2d contract.
- **Watch out for:** Preserve Preview-only routing and V4; do not expose secret
  values, enable the schedule early, or begin Phase 3.

**tags:** ["data-first", "phase2", "recertification", "eligibility", "automation"]
