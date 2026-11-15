import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import test from "node:test";
import { periodBeforeKickoff, PRESEASON_META, type PeriodMeta } from "./rating-periods.ts";

test("SiteNav includes Games, Teams, Graphs, and Model in navigation items", () => {
  const source = readFileSync(new URL("../components/SiteNav.tsx", import.meta.url), "utf8");
  assert.match(source, /\["Games",\s*"\/"\]/);
  assert.match(source, /\["Teams",\s*"\/teams"\]/);
  assert.match(source, /\["Graphs",\s*"\/stats"\]/);
  assert.match(source, /\["Model",\s*"\/model"\]/);
});

test("the retired ratings page permanently redirects to Teams and keeps every query parameter", () => {
  const source = readFileSync(new URL("../app/ratings/page.tsx", import.meta.url), "utf8");
  assert.match(source, /permanentRedirect\(`\/teams/);
  assert.match(source, /query\.append\(name, item\)/);
  assert.match(source, /query\.set\(name, value\)/);
});

test("Teams hub keeps national ranks fixed, validates sort and direction, and exposes aria-sort", () => {
  const source = readFileSync(new URL("../components/ratings/TeamsHub.tsx", import.meta.url), "utf8");
  assert.match(source, /parseRatingsSort\(params\.get\("sort"\)/);
  assert.match(source, /National ranks stay fixed when you filter/);
  assert.match(source, /aria-sort=\{/);
  assert.match(source, /overflow-x-auto/);
  assert.match(source, /Wins above an average FBS team/);
  assert.match(source, /href="\/model\/method"/);
  assert.match(source, /searchParamsUrl\("\/teams"/);
});

test("ratings table orders by column headers with SOS ranked over every team before filtering", () => {
  const viewSource = readFileSync(new URL("../components/ratings/RatingsView.tsx", import.meta.url), "utf8");
  // The top segmented sort groups are gone; sorting lives in the table headers and the phone select.
  assert.doesNotMatch(viewSource, /Rating category|Résumé sort|Sort by résumé|SegmentedControl/);
  assert.match(viewSource, /aria-label=\{`Sort by \$\{label\}`\}/);
  assert.match(viewSource, /aria-sort=\{active \? \(direction === "desc" \? "descending" : "ascending"\) : "none"\}/);
  assert.match(viewSource, /<label htmlFor="rating-sort"[^>]*>Sort by<\/label>/);
  // SOS ranks come from the full period, and the search filter runs after ranking.
  assert.match(viewSource, /const sosRanks = useMemo\(\(\) => rankSosByTeam\(ratings\), \[ratings\]\);/);
  assert.match(viewSource, /ranked\.filter\(/);
  // Period links carry the direction only when it differs from the sort's best-first default.
  assert.match(viewSource, /if \(direction !== bestFirstDirection\(sort\)\) params\.set\("dir", direction\);/);
});

test("ratings table explains SOS and SOR rank tooltips and the note copy", () => {
  const viewSource = readFileSync(new URL("../components/ratings/RatingsView.tsx", import.meta.url), "utf8");
  assert.match(viewSource, /Schedule difficulty rank among FBS teams \(1 is hardest\), measured against an average FBS team\./);
  assert.match(viewSource, /Strength of record rank: 1 is the strongest résumé\./);
  assert.match(viewSource, /SOS ranks schedule difficulty for an average FBS team \(1 is hardest\)\./);
  assert.match(viewSource, /href="\/model\/method#elite-reference"/);
});

test("TeamPair shows team names as plain text, not links (slate cards never link to team pages)", () => {
  const source = readFileSync(new URL("../components/slate/TeamPair.tsx", import.meta.url), "utf8");
  assert.doesNotMatch(source, /\/teams\//);
  assert.doesNotMatch(source, /import Link from "next\/link";/);
  assert.match(source, /min-w-0 break-words text-sm/);
});

test("slate cards link to the matchup breakdown through the gated button instead", () => {
  for (const file of [
    "PredictionGameCard.tsx",
    "SlateGameRow.tsx",
    "MarketGameCard.tsx",
  ]) {
    const source = readFileSync(new URL(`../components/slate/${file}`, import.meta.url), "utf8");
    assert.doesNotMatch(source, /\/teams\//);
    assert.match(source, /<MatchupButton gameId=\{game\.gameId\} \/>/);
  }
});

test("ratings timeline labels generations from résumé rows and backfills early tabs from priors", () => {
  // Labels come from the projection, not a hand-maintained cutoff map.
  const periodsSource = readFileSync(new URL("./rating-periods.ts", import.meta.url), "utf8");
  assert.doesNotMatch(periodsSource, /WEEK_GENERATIONS/);
  assert.match(periodsSource, /Post-Week \$\{postWeek\}/);

  const source = readFileSync(new URL("./v5.ts", import.meta.url), "utf8");
  assert.doesNotMatch(source, /WEEK_GENERATIONS/);
  // The résumé facts are read once per request and shared by the period list and selection
  assert.equal([...source.matchAll(/const readResumePeriodFacts = cache\(/g)].length, 1);
  assert.match(source, /periodLabelFields\(cutoffUtc, facts\.get\(id\), index === 0\)/);

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
