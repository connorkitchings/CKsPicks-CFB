# CFBD retrospective lines for three Week 6 games

- **Status:** In Progress
- **Created:** 2026-11-09
- **Planner:** Owner instruction relayed by the orchestrating agent (fast-path contract)
- **Approval source:** Owner request of 2026-11-09, Preview only; Production activation needs separate approval
- **Implementation log:** `session_logs/2026-11-09/03-cfbd-retrospective-lines-phase1.md` (candidate) and `session_logs/2026-11-09/04-cfbd-retrospective-lines-release.md` (carry-forward, parity allowance, Preview release)
- **Commit policy:** Commit with implementation (the revision manifest must be committed before `prepare`)

## Goal and acceptance

Three Week 6 games have no market quote captured before kickoff, so they are ungraded in the active release: Southern Miss at Troy (`401871090`), Jacksonville State at Kennesaw State (`401871051`) and New Mexico State at Florida International (`401871066`). Grade them with the documented, explicitly supplied `cfbd_retrospective` fallback ([record methodology](../../modeling/record_methodology.md)). The grade stays labeled retrospective; it is not pre-kickoff evidence.

Phase 1 (this contract) ends at a verified, prepared candidate. Done when:

- a new immutable `market_quotes` Silver version holds only the three games' CFBD rows, each tagged `source_provider = cfbd`;
- `revision_manifest_w11_v2.json` equals `revision_manifest_w11_v1.json` except for `revision_id` and the new `historical_lines` input;
- `make season-prepare` from the clean committed tree passes every verification check;
- against the active Preview release, predictions, variances, ratings and every other grade are identical, and only the three games gain a consensus snapshot plus spread and total grades labeled `cfbd_retrospective`.

## Baseline and constraints

- Branch `connorkitchings/cfbd-retrospective-lines` off `origin/dev` at `493ac897`; active week is 11 (live), newest manifest `revision_manifest_w11_v1.json`.
- The lines are already in the lake: registered CFBD betting-lines capture `da13ee7e18d34b0a90c9344a4c9ebc36` (Week 6, fetched 2026-10-08T16:19Z, after kickoff) holds Bovada and DraftKings rows for all three games. Building from that registered capture needs no provider call, no new capture and no overwrite of the compatibility raw partition (which `ingest_week.py` would rewrite for every Week 6 game). The brief asked for a fresh fetch; the existing immutable capture carries the same values and a real capture time, so it is used instead.
- No provider is queried. Excluded: other games, other weeks, football inputs, completed-week cutoffs, score exceptions, the cumulative `market_quotes` input, any release (Preview or Production), `docs/status.md`.
- Canonical line: no Consensus provider exists for these games, so `select_market_snapshot` takes the provider median (`provider_median`). CFBD spreads are home-signed, matching `normalize_quotes`.
- Stop gates: any change to another game's grade, any prediction difference, any failed verification check.

## Ordered changes

1. `scripts/pipeline/build_market_revision.py`: `derive_manifest` takes optional `quotes_input` and `historical_lines`; football inputs still must be unchanged. Validation: `tests/test_build_market_revision.py`.
2. `scripts/pipeline/build_historical_lines_revision.py` (new): reads the named registered capture, keeps the named games, tags `source_provider`, registers the Silver version, writes the manifest. Validation: `tests/test_build_historical_lines_revision.py`.
3. Run the builder to produce `conf/season/2026/revision_manifest_w11_v2.json`; commit it with the code, test and these documents.
4. `make season-prepare WEEK=11 AS_OF=2026-11-08T18:03:33Z MANIFEST=conf/season/2026/revision_manifest_w11_v2.json`. `captured_at` and the Week 11 cutoff stay as in the base, because the new input is an October capture and no Week 11 input changed; the live slate is reproduced exactly.
5. Compare the candidate with the active Preview release, read-only.

## Validation

- `uv run pytest tests/test_build_historical_lines_revision.py tests/test_build_market_revision.py`, `make lint`, `make contracts-check`.
- Positive: three games gain grades labeled `cfbd_retrospective`. Negative: a game absent from the capture is refused; a non-CFBD or unregistered capture is refused; an existing target manifest is never overwritten. Boundary: other games and live-week grades unchanged.
- `git diff --check`.

## Handoff/amendments

- **Resume gate:** Phase 2 (Preview release, parity, Production) needs the orchestrator's explicit go-ahead and the weekly runbook release steps; nothing is activated in Phase 1.
- **Follow-up risk:** `build_season_revision.revision_manifest` does not carry `historical_lines`; the next close-week manifest would drop the three grades unless that input is carried forward.
- **Amendments:** none yet.
