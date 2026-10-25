# Session: V5 Possession R5 Over-Limit Apply Handoff

## TL;DR

- **Worked On:** Re-ran V5-02 under committed SHA
  `627cd7be4c27fa31bf7278947a7baf32d6f20e76` using the Amendment 3 bounded
  concurrent Preview writer.
- **Outcome:** The r5 dry preflight passed in about 25 minutes and exactly
  matched the reviewed rows, digests, and certification. The r5 apply produced
  a valid-looking immutable Preview manifest, but took 2,171.445 seconds—over
  the fixed 30-minute cap. It is therefore ineligible and must not be verified,
  idempotently replayed, or used as a V5-03 parent.
- **Plan Contract:**
  `docs/plans/2026-09-13/02-v5-possession-measurement-certification.md`
  (Amendment 3).
- **Approval / Status:** Contract remains **In Progress**; V5-03 remains
  blocked.
- **Blockers:** A new mechanical amendment must make the complete applied
  invocation finish within 1,800 seconds before a fresh SHA/run identity can
  proceed. No gate may be weakened.

## Frozen R5 Evidence

- Run ID: `possession-v1-measurements-20260915-627cd7b-r5`.
- Shared `as_of`: `2026-09-15T15:21:04Z`; environment: Preview R2.
- Identity SHA:
  `0fcda65a3051eec1f80a0eeab7645f8ad9738e8f5e8c57cf4aecf3f79d78c0cc`.
- Approved Repair v2 parent raw/canonical checksums:
  `b55af0dd7952a4b5e0d663b82182b351ec5496a292246a934a857c354058e0b4` /
  `2fefcb95a2e8b4ae27e8fb2bf740328413aa576bcd725ebd9a18378edd50ac48`.
- Preflight and apply certification SHA:
  `be4fcb6ec1e50356f1230b5831bb775e5383507f2c51cc736476a15badd15fa1`.
- Output rows: adjusted history 24,223,998; coverage 160; observations
  285,952; population 8,936; possessions 316,257; scoring events 78,418;
  snapshots 142,960; terminal 8,580. All eight output record digests matched
  the r5 preflight and earlier reviewed deterministic evidence.
- The final r5 run prefix has 12 immutable control objects, including
  `measurement-manifest.json`; it is retained as failed/ineligible Preview
  evidence. No verifier or idempotency operation was performed.

## Timing Diagnosis

The bounded concurrent part writer preserved deterministic output but did not
bring the complete write-time replay under the hard deadline. Its final
`preflight_complete` progress event occurred at 2,164.232 seconds and
`apply_complete` at 2,171.445 seconds. The invocation exceeded the cap before
the producer could be accepted, irrespective of its output agreement.

## Validation

- [x] R5 dry preflight completed under its separate 30-minute cap and matched
  the reviewed population invariant, output rows, record digests, and
  certification SHA.
- [x] R5 apply output agreement was inspected, but the invocation exceeded its
  separate 30-minute cap and is explicitly rejected.
- [x] Preview run-prefix inventory confirmed 12 immutable control objects and
  no verifier/idempotency follow-up.
- [x] Prior Amendment 3 scoped checks: Ruff format/lint and 24 targeted
  data-lake/runner tests passed with warnings treated as errors.
- [x] `git diff --check` at session close.

## Resume

Use a new plan amendment and committed SHA to address the timing architecture.
First diagnose the 25-minute reconstruction baseline versus the 30-minute
end-to-end limit; do not reuse the r4 or r5 prefixes or treat their data as
certification evidence. A future attempt must restart at empty-prefix
preflight, then complete apply, independent verification, and idempotency
within their separate limits.

**tags:** ["v5", "possession", "certification", "r2", "preview", "timeout"]
