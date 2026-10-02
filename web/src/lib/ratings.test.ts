import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import test from "node:test";
import { periodBeforeKickoff, PRESEASON_META, type PeriodMeta } from "./rating-periods.ts";

test("SiteNav includes Picks, Results, Ratings, and Performance in navigation items", () => {
  const source = readFileSync(new URL("../components/SiteNav.tsx", import.meta.url), "utf8");
  assert.match(source, /\["Picks",\s*"\/"\]/);
  assert.match(source, /\["Results",\s*"\/results"\]/);
  assert.match(source, /\["Ratings",\s*"\/ratings"\]/);
  assert.match(source, /\["Performance",\s*"\/performance"\]/);
});

test("ratings page includes rank column, methodology explainer, and disambiguated empty states", () => {
  const source = readFileSync(new URL("../app/ratings/page.tsx", import.meta.url), "utf8");

  // Rank column in table header and body (computed pre-filter)
  assert.match(source, /<th scope="col"[^>]*>#<\/th>/);
  assert.match(source, /\{rank\}/);
  assert.match(source, /rank computed pre-filter/);
  assert.match(source, /aria-label="Ratings timeline"/);
  assert.match(source, /aria-current=/);

  // Methodology explainer citing possession scoring efficiency (PPP) and Ridge bridge
  assert.match(source, /scoring efficiency per possession \(PPP\)/);
  assert.match(source, /average FBS opponent under standard conditions/);
  assert.match(source, /Both offense and defense are oriented so higher is better/);
  assert.match(source, /through-2025 Ridge regression bridge with earlier-only non-offense offsets/);
  assert.match(source, /Uncertainty \(±\) is one rating standard deviation/);

  // Disambiguated empty states
  assert.match(source, /No certified ratings published for the \{season\} season yet\./);
  assert.match(source, /No teams match &ldquo;\{query\}&rdquo;\./);

  // Season parameterization and ISR
  assert.match(source, /revalidate = 300/);
  assert.match(source, /requestedSeason = params\.season \? Number\(params\.season\) : 2026/);
});

test("GameRow TeamLine shows team names as plain text, not links (team pages are not ready)", () => {
  const source = readFileSync(new URL("../components/GameRow.tsx", import.meta.url), "utf8");
  assert.doesNotMatch(source, /\/teams\//);
  assert.doesNotMatch(source, /import Link from "next\/link";/);
  assert.match(source, /min-w-0 truncate text-sm text-ink/);
  // The card links to the matchup breakdown through the gated button instead.
  assert.match(source, /<MatchupButton gameId=\{game\.gameId\} \/>/);
});

test("ratings timeline labels certified post-week generations and backfills early tabs from priors", () => {
  // Certified week map lives in the dependency-free rating-periods module so
  // behavioral tests can import it without the drizzle/Neon client chain.
  const periodsSource = readFileSync(new URL("./rating-periods.ts", import.meta.url), "utf8");

  // Certified week map keyed by exact generation cutoff
  assert.match(periodsSource, /WEEK_GENERATIONS/);
  assert.match(periodsSource, /2026-09-03T04:00:00\.000Z/);
  assert.match(periodsSource, /2026-09-08T15:35:00\.000Z/);
  assert.match(periodsSource, /2026-09-13T18:18:22\.000Z/);
  assert.match(periodsSource, /2026-09-22T14:58:00\.000Z/);
  assert.match(periodsSource, /2026-09-27T14:15:00\.000Z/);
  assert.match(periodsSource, /Post-Week \$\{known\.postWeek\}/);

  // Serving layer binds frozen tabs and backfill to explicit sources
  const source = readFileSync(new URL("./v5.ts", import.meta.url), "utf8");

  // Frozen tabs backfill teams missing from early generations via priors
  assert.match(source, /getPreseasonPriors/);
  assert.match(source, /Backfill the rest from preseason priors/);

  // Retired week-style params resolve to the certified generation
  assert.match(source, /p\.postWeek === week/);
});

test("periodBeforeKickoff picks the latest generation at or before kickoff", () => {
  const gen = (id: string, iso: string): PeriodMeta => ({
    id, label: id, shortLabel: id, description: "", cutoffUtc: new Date(iso),
  });
  const periods = [
    gen("w4", "2026-09-27T14:15:00Z"),
    PRESEASON_META,
    gen("w3", "2026-09-22T14:58:00Z"),
  ];
  assert.equal(periodBeforeKickoff(periods, new Date("2026-10-03T16:00:00Z"))?.id, "w4");
  assert.equal(periodBeforeKickoff(periods, new Date("2026-09-27T14:15:00Z"))?.id, "w4");
  assert.equal(periodBeforeKickoff(periods, new Date("2026-09-24T00:00:00Z"))?.id, "w3");
  assert.equal(periodBeforeKickoff(periods, new Date("2026-08-29T00:00:00Z")), null);
});
