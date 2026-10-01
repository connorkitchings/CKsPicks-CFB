# Session: Fan-facing Week 0 predictions UI

## TL;DR

- **Worked On:** Simplified the public predictions page after user review of
  the header and model-quality panel.
- **Outcome:** Production now prioritizes the picks, removes implementation
  identifiers, and explains early-season model quality in ordinary language.
- **Plan Contract:** N/A (approved, localized public UI refinement)
- **Approval / Status:** User explicitly approved the redesign on 2026-08-21.
- **Blockers:** None.
- **Next:** Continue the established manual snapshot and final-freeze process
  before Week 0 kickoff.

## Context and Decisions

- Public run/model IDs are operational metadata, not fan-facing information;
  the header now retains model name, publication state, and update time only.
- The early-season panel must show model population without requiring terms
  such as MAE, holdout, or out-of-sample selection to be understood.
- Detailed methodology remains available through a native disclosure for
  users who want it, while the default presentation emphasizes typical miss,
  comparable-game counts, and the fact that smaller is better.

## Work Completed

- Removed the public model ID from the header and simplified its labels.
- Replaced the route-backtest card with a fan-facing `Early-Season Model
  Context` panel:
  - explains why current-season evidence is limited;
  - shows the 2025 check (83 comparable games) and 2022–24 track record (243
    comparable games) side by side;
  - labels spread and total as a typical point miss; and
  - places technical evaluation language inside `How These Numbers Are
    Measured`.
- Simplified the public edge definition and reduced the visual separation of
  the supporting model projection on game cards.
- Deployed production successfully:
  `https://c-ks-picks-2b9q4jqct-connorkitchings-projects.vercel.app`.

## Files Modified

- `web/src/app/page.tsx` - Removed model-ID presentation and clarified edge
  copy.
- `web/src/components/Header.tsx` - Simplified public metadata.
- `web/src/components/GameRow.tsx` - Tightened model-projection placement.
- `web/src/components/ModelAccuracyPanel.tsx` - Reframed model quality for a
  general audience.

## Validation

- [x] `npm run lint`
- [x] `npm run typecheck`
- [x] `npm run test:publication`
- [x] `npm run build` (rerun outside the sandbox after a local Turbopack
  worker-port restriction)
- [x] `git diff --check`
- [x] Production render check for simplified header/model-quality copy.
- [x] Production health: predictions mode, active run
  `2026w0-55de0317120d`, 8 expected / 8 predicted / 8 lined.

## Handoff Notes

- **Resume at:** Before each desired market observation, run a manual publish
  and record the new immutable run/capture details; review and freeze the
  final run before kickoff.
- **Watch out for:** This presentation change does not alter data lineage,
  scoring, prediction values, publication mode, or final-freeze authority.

**tags:** ["week0", "predictions", "web", "fan-facing", "ui"]
