# Session: v5 Shadow Contract Amendment 2 (Sol)

## TL;DR
- **Worked On:** Revised the twice-stopped v5 shadow contract per the fresh Terra run's parity-gate findings.
- **Outcome:** Amendment 2 incorporated — byte-parity replaced with a two-tier gate (diff confinement + prediction-level control), W0 v5 `as_of` pinned to the publish cutoff. Status Draft, pending user re-approval for a fresh Terra run.
- **Plan Contract:** `docs/plans/2026-09-10/2026-v5-shadow-rebuild-diagnostic.md` (Draft + Amendments 1–2)
- **Approval / Status:** Pending re-approval. Terra must not resume without it.
- **Blockers:** None for planning. Implementation blocked until re-approval.
- **Next:** User re-approves (or amends); then a fresh Terra task executes Tasks 1–5 under the two-tier gate.

## Context and Decisions
- The fresh Terra run executed Amendment 1 faithfully and stopped honestly on byte-parity: W0 rerun from immutable parents → `cc6b1a03…` vs prod `1f32fc0f…`. Diagnosis is deterministic code drift, not corrupt lineage — the stop rule worked, but the gate was the wrong test at HEAD.
- Sol verified the amendment's load-bearing claims before writing it: bundle manifest feature union (329 features; all 5 extra columns disjoint; 16 drifted prior columns ARE bundle inputs, so inspection alone cannot clear them) and the inference loader (`model_bundle_v3.py:179-202`: reads only listed features, ignores extras; shrinkage computed at inference from base columns — hence the empirical Tier-2 control is required, not optional).
- Tier 2 (prediction-level control on rebuilt v4 vs official predictions) is the keystone: a match proves current-code outputs equal original-code outputs, so the shadow-vs-official comparison isolates the feature effect with zero code-effect confounding. Stronger than byte-parity for the causal question.
- Also fixed Terra's `as_of` catch: W0 v5 pinned to publish cutoff `2026-08-20T13:19:14Z` (dominates 08-17 preseason parent, stays pre-kickoff). W1/W2 cutoffs already dominate.
- Preserved `M docs/ops/production_runbook.md` and `?? .opencode/` untouched.

## Work Completed
- Read Terra's `09-…` log in full; verified bundle features, loader behavior, and drift classification.
- Rewrote Task 2 as two-tier gate with per-week sequencing; adjusted Task 3 (W0 as_of), Risks (drift containment, recency labeling), Amendments (Amendment 2; repaired Amendment 1 header).
- Updated `docs/plans/index.md`; this log.

## Files Modified
- `docs/plans/2026-09-10/2026-v5-shadow-rebuild-diagnostic.md` - Amendment 2, status Draft pending re-approval
- `docs/plans/index.md` - entry tracks amendment
- `session_logs/2026-09-10/10-v5-shadow-amendment-2.md` - this log

## Validation
- [x] Bundle-manifest + loader source verification recorded above
- [x] `git diff --check`
- [x] `uv run mkdocs build --quiet`
- [ ] User re-approval of the amended contract (pending)

## Amendments and Blockers
- Amendment 2 to the v5 shadow contract (see contract). No other blockers.

## Handoff Notes
- **Resume at:** User reviews Amendment 2; on re-approval, launch a fresh Terra task (not a resume) executing Tasks 1–5 under the two-tier gate. Reusable: shadow ref-files, `c89b4567` (quarantined W0 subject), guard baselines in log `09-…`.
- **Watch out for:** Tier-2 equality is on parsed float values; formatting-only diffs must be proven value-identical or stop.

**tags:** ["planning", "v5-shadow", "amendment", "sol"]
