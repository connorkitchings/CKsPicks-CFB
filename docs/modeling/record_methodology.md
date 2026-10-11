# 2026 record methodology

> **Status:** Active (decided 2026-10-10). This is the internal statement of how the public 2026 V5 record is admitted and what it does and does not guarantee. Live numbers are in [`status.md`](../status.md); the decision is in the [decision log](../decisions/decision_log.md).

## Policy

The demonstrated 2026 record is **one continuous, cumulative V5 record from Week 0 onward**, presented as if V5 had been the active model for the whole season. Weeks 0 and later are scored the same way: a pick is the model side against the best eligible pre-kickoff line, graded win, loss or push against the certified final. The public site shows one record and does not split it by how each week was produced; the provenance below lives here, in the database and in the contract amendments.

## Admission criterion: strict point-in-time inputs

A game enters the record only if every check of the point-in-time audit (`scripts/pipeline/audit_point_in_time_leakage.py`) passes for it. The audit measures **event time**, never build time: replays were generated after the games, so "generated before kickoff" is not the test. The test is that every input was available at the forecast `as_of`, and the `as_of` is not after kickoff.

| Rule | What must hold |
|---|---|
| a. Rating inputs | every observation behind a team's state became available (source kickoff + 6 h) at or before the forecast `as_of`; none from the same or a later week |
| b. Rating state | the state's cutoff is at or before the forecast `as_of` |
| c. Forecast time | the forecast `as_of` is at or before kickoff (Week 6: before 2026-10-07T00:00:00Z, the first Week 6 kickoff, so all 58 games are forecast without Week 6 results in the ratings) |
| d. Quote time | the selected quote was captured before kickoff and no later than the market cutoff, **or** it is on the declared accepted-late list below |
| e. Model parameters | the inference bundle was developed on 2015-2019 and 2021-2025 only: no 2026 outcome and no 2020 |
| f. Team stats | matchup statistics for a week-w game use `as_of_week <= w`; the builder counts only games completed before `as_of_week` |
| g. Cutoff coherence | both Week 6 cutoffs (forecast and market) are recorded, and the forecast one is at or before the first kickoff |

The audit writes a checksummed receipt; the cutover packet must carry a passing receipt that covers every selected run.

## Declared exception: CFBD lines fetched after kickoff

A line captured at or after kickoff is normally ineligible. CFBD publishes one line per provider per game with no timestamp of its own, and our capture time is the fetch time. For a game that had already kicked off when we fetched, the CFBD line is accepted as the game's pregame consensus line if, and only if:
- the quote is on the market lock's accepted-late list with `reason: "cfbd_pregame_consensus_fetched_post_kickoff"`, provider `cfbd` and source entity `betting_lines` (no Odds API or in-game feed);
- the empirical check (re-fetching current CFBD lines for already-completed Weeks 0-5 games and comparing them with the stored pre-kickoff captures) supports that a post-game fetch returns the pregame line.

**Assumption, stated plainly:** that CFBD's lines endpoint returns pregame lines only. Its documentation was not found to say so; the comparison above is the evidence. If it fails, the exception is withdrawn and those games are ungraded.

Games covered (late-quote exception currently disabled): Week 6 games 401871051, 401871066 and 401871090. Week 3 Houston @ Texas Tech total (401856811) is covered only if a CFBD total exists in a capture and the Week 3 replay is rebuilt.

## What the guarantee does not cover (known caveats)

These are facts about how the record was produced, kept here so the claim is not stronger than the evidence:
- **Later data corrections were adopted.** The corrected rebuild uses CFBD's updated play-by-play for past weeks (Stage 1 Option B). Event-time cutoffs hold, but a correction published after the original week is used.
- **CFBD capture times are fetch times.** The audit can show a line was fetched before kickoff, not when the book posted it.
- **Design choices were made with results known.** The V5 repair, the B2 bundle and the removal of the edge thresholds were decided after Weeks 0-3 had been played. No 2026 outcome was used to fit parameters; the choices themselves are not blind.
- **Week 6 has two cutoffs.** The forecast `as_of` is before 2026-10-07T00:00Z; the only market snapshot was captured 2026-10-08T16:19Z. Both are recorded in the receipt.
- **Verified gaps stay ungraded.** A game with no eligible line has no selection and no grade.

## Provenance that is still recorded

Evidence class (`replay`, `pending`, `live`), freeze receipts and the Week 5 legacy attestation, run manifests and authorizations remain in the database and artifacts. The frozen Week 5 run and its receipt are immutable; after the cutover the counted run for every week 0-6 is the corrected replay. Hard rules that do not change: training strictly precedes prediction, no 2026 outcome refits the V5 identity, no freeze receipt is created after kickoff, and market data never enters model inputs.

## Audit execution and October 10 findings

Run `uv run python scripts/pipeline/audit_point_in_time_leakage.py --environment preview --season 2026 --through-week 6` from the repository root. It reads R2 and the serving database without writes, verifies hashes and source-game histories, checks both cutoffs, and independently excludes all same/later-week games before rebuilding statistics from their recorded Silver versions. The receipt is created at `artifacts/audit/leakage_audit_receipt_2026.json`; an existing receipt is preserved, so use a fresh `--output` for a subsequent audit. Exact run, source-lock, rating and bridge arguments must follow the reviewed lineage when it changes. Environment is explicit; the default evidence names the current Preview corrected candidates, not a Production activation.

Completed-week replays use the pregame cutoff of each game's bound rating state; their serving `data_as_of` records the separately captured market cutoff. Both appear in the receipt. Forecast generation time is not substituted for event time.

The October 10 read-only execution passed all seven rules for the 271 corrected Week 0–5 games. Including the existing Week 6 display run failed: its 220 rating-role cutoffs are after its declared forecast time, that time is after the required October 7 boundary, and its slate omits three games. No future outcome was found in the rating histories. The receipt remains failed until a complete corrected Week 6 replay passes; it cannot authorize a cutover.

`verify_cfbd_closing_lines.py` sampled three completed games from each of Weeks 0–5 and compared 59 pre-kickoff provider/target captures with fresh CFBD lines: 19 matched, 40 differed. The comparison **does not support enabling the declared late-quote exception**. Differences may be legitimate pregame movement after our capture, so they do not establish post-kickoff line movement either. The three early Week 6 games remain ungraded unless new evidence satisfies the acceptance gate. Exact late-quote declarations are supported by the market lock and serving paths, but a failed or missing signed comparison is refused.
