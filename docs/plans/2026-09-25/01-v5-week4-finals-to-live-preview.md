# V5 Week 4 Finals to Live Preview Evidence

- **Status:** Approved
- **Created:** 2026-09-25
- **Planner:** Sol (plan-session)
- **Approval source:** The user explicitly authorized execution of this exact plan path on 2026-09-25 ("go"), after the Draft documented planning-only session earlier that day. This approval covers the gated execution sequence below; production V5 authorization and activation remain separate decisions.
- **Implementation log:** Create a dated log for each operational execution checkpoint, recording exact run IDs, immutable URIs/raw SHAs, reviewer decision, and result.
- **Commit policy:** Separate plan commit recommended before multi-session data and serving operations. The user executes Git operations.

## Goal and current state

Produce a current, independently verified V5 forecast and `ready` assessment for the first eligible 2026 slate, then prove serving and same-week V4 rollback on Preview. Finish with a reviewable exact production release packet. This plan stops before production authorization or V5 activation.

The manual V5 operator and restricted production release boundary are Implemented. Production migration 0014 is applied with zero authorization rows; V4 remains public. The active production Week 4 V4 run `2026w4-da5d98761831` is frozen at 58/58/58. At the 2026-09-25 13:43 UTC read-only check, Week 4 had no recorded finals and games were scheduled through 2026-09-27 03:00 UTC. The 24-hour post-final gate is closed. Contracts 07/08 are verified only through Week 3; Contract 09's live forecast and 05 readiness remain unrun on refreshed Week 4 parents. Week 5 is the intended first live slate if its pre-kickoff gates can still be met.

This plan sequences existing authority: [07](../2026-09-18/07-v5-2026-repair-and-measurement-extension.md), [08](../2026-09-18/08-v5-2026-rating-state-replay.md), [09](../2026-09-18/09-v5-2026-forecast-and-readiness.md), the [manual operator](../2026-09-24/02-v5-weekly-operator-and-release-gates.md), and the [site cutover contract](../2026-09-22/04-v5-authority-simplification-and-site-cutover.md). Their accepted model, timing, lineage, and release policies are unchanged.

## Ordered execution and acceptance

### 1. Certify Week 4 completion and close V4

Inspect the frozen run, canonical 58-game Week 4 population, latest versioned Silver `game_outcomes` and related completed-game refs, and final timestamps. No missing, postponed, duplicate, or non-final game may be silently counted as complete. Run the existing production V4 `close-week` path only after its finals gate passes; verify the selected frozen run is scored without moving the public week to V5. Record the exact outcome ref, checksum, last certified final time, and production score receipt. The V5 refresh may start only after **all** Week 4 finals are certified and 24 hours have elapsed since the last certified final. If a correction changes the final version or timestamp, re-evaluate that gate before the refresh.

**Acceptance:** Complete certified finals, V4 close receipt and score coverage, unchanged V4 public selection, and an explicit UTC stabilization calculation. A partial or ambiguous slate is a blocker, not a waiver.

### 2. Refresh Contracts 07 and 08 on Preview

Use the clean committed code SHA and new immutable IDs. Bind the 2026 Weeks 0–4 Silver source bundle and accepted Repair v2 anchor to a new `repair` component. After reviewed preflight, apply, independently verify `repaired_live_only`, and repeat idempotently. Use that exact verified repair manifest for a new `measurement` component, preserving the certified r9 settings and complete Week 0–4 population. After its independent verification and repeat, use the new measurement manifest, fixed historical rating identity, and immutable 2026 preseason refs for a new `rating` replay. Independently verify continuous Week 0–4 states and repeat. Record each URI/raw SHA and verifier receipt in the operator descriptor and execution log; advance only on verified evidence.

**Acceptance:** New 07 and 08 identities cover all certified Weeks 0–4 games with no omissions or future leakage; original historical and Weeks 0–3 artifacts stay immutable. No 2026 outcome refit, reselection, or production research write occurs.

### 3. Certify the next live forecast and readiness

For Week 5 only if the cutoff is still pre-kickoff, bind the new verified 07/08 parents, immutable complete schedule ref, and fixed through-2025 11C bridge. Run Contract 09 `forecast` preflight, review future-slate population and timestamps, then apply, independently verify, and repeat under a new immutable ID. Prepare and verify a same-week V4 comparison artifact and Preview serving run through the existing V4 path if they do not already exist; bind their exact identities before readiness or rollback. Use the exact V5 forecast, 07/08/Repair parents, V4 comparison predictions, and slate/input refs for Contract 05 `readiness`; run reviewed preflight, apply, independent verification, and repeat. Preserve `production_activation_authorized: false` and truthful live/pending evidence labels. If readiness is verified `blocked`, record the exact missing source and stop serving work. If Week 5's pre-kickoff window is missed, do not backdate or claim prospective evidence: record a missed/blocked Week 5 attempt and use the next eligible slate under new identities and a new descriptor.

**Acceptance:** Signed, independently verified forecast and `ready` receipt for the same future slate, complete margin/total pairs, pre-cutoff sources, and no fitted quantity from 2026 outcomes. `ready` opens the existing Contract 06 prospective-collection gate; it does not authorize production release.

### 4. Rehearse Preview serving and prepare the release review

Pin the verified live forecast in a reviewed Preview serving config. Use the operator's `prepare` component to create a byte-checked immutable prediction candidate without selection, then publish it on Preview and verify schedule coverage, model/line sign conventions, health, and populated browser pages. Freeze only inside the existing T−2h target/T−1h hard lead and paired-coverage gates. Re-select the reviewed same-week V4 run and verify that the Preview view and health return to V4; restore V5 only as a separately recorded Preview action. Preserve exact run IDs, timing, checksums, and rollback observations. If the first-kickoff gate is missed, record the rehearsal as incomplete; do not manufacture a live freeze.

Assemble and run the read-only exact release-packet validator with the verified 09/05 receipts, candidate artifact URI/raw SHA, config SHA, model/bundle identity, season/week/run, and V4 fallback. Present that packet and Preview evidence for a **separate production activation decision**. This plan stops before an admin authorization insert, production V5 publication/selection, or V4 retirement.

**Acceptance:** Real Preview serving and same-week V4 rollback proof, exact packet validation, and a written list of any remaining blockers. No production V5 authorization row or public change.

## Validation and stop conditions

- At every operator component, preserve separate preflight review and apply invocations, exact descriptor/code/config/parent SHA bindings, leases, independent verifier receipts, and idempotent repeat. An altered parent or failed step stops downstream components; resume only with the identical identity or start a new immutable run after diagnosis.
- Reconcile the canonical schedule and outcome population against source manifests, not only Neon counts. Check the 24-hour stabilization window, first kickoff, T−2h/T−1h freeze limits, and same-slate parent IDs at execution time. Never reuse the fixture rehearsal or Weeks 0–3 replay as a fresh parent.
- Run the contract-specific verifier and receipt checks for 07/08/09/05, Preview publication/rollback health and browser checks, scoped tests for any code correction, contract/schema checks if touched, strict MkDocs, and `git diff --check`. Record actual commands, IDs, SHAs, counts, and results in execution logs.
- Stop for renewed Sol review on a material change to model math, lineage, population, timing, authorization identity, or release policy. A verified `blocked` readiness is evidence, not permission to publish. Preserve V4 operations while the gate is closed.

## Definition of done

- [ ] Week 4 finals and V4 close are certified; the 24-hour V5 refresh gate is proven from exact outcome timestamps.
- [ ] New 07/08 Week 0–4 parents pass preflight/apply/independent verify/repeat on Preview.
- [ ] Contract 09 forecast and Contract 05 `ready` pass on an eligible future slate. A truthful blocked/missed Week 5 record is a checkpoint that retargets the plan; it does not satisfy this item.
- [ ] Real Preview serving, freeze timing, V4 rollback, and exact packet validation are recorded where eligible.
- [ ] The packet is presented for a separate activation decision; no production V5 authorization, selection, or V4 retirement occurs under this plan.
- [ ] Execution logs and current status docs record actual evidence and blockers. Keep the plan In Progress after a missed slate until an eligible slate completes or a reviewed amendment changes its disposition.

## Amendments

None. This is an execution sequence for existing approved contracts, not a new model or production release authority.
