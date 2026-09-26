import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import test from "node:test";

test("SiteNav includes Predictions and Ratings in navigation items", () => {
  const source = readFileSync(new URL("../components/SiteNav.tsx", import.meta.url), "utf8");
  assert.match(source, /\["Predictions",\s*"\/"\]/);
  assert.match(source, /\["Ratings",\s*"\/ratings"\]/);
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

test("GameRow TeamLine links team names to /teams/[team] with accessibility and focus styles", () => {
  const source = readFileSync(new URL("../components/GameRow.tsx", import.meta.url), "utf8");

  // Import Link
  assert.match(source, /import Link from "next\/link";/);

  // TeamLine wraps name in Link
  assert.match(source, /href=\{`\/teams\/\$\{encodeURIComponent\(name\)\}`\}/);
  assert.match(source, /hover:text-accent-ink/);
  assert.match(source, /focus-visible:outline-accent/);
  assert.match(source, /min-w-0 truncate text-sm text-ink/);
});
