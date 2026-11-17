import assert from "node:assert/strict";
import test from "node:test";
import { canBoundHistoryByRelease, normalizeRatingPeriod } from "./rating-request.ts";

const known = [{ id: "abc123@2026-10-12T00:00:00.000Z", postWeek: 3 }, { id: "preseason-id" }];

test("fixed tabs, known period ids and retired week params pass through", () => {
  for (const value of ["current", "preseason", "pre", known[0].id, "3", "post-3", "week-3"]) {
    assert.equal(normalizeRatingPeriod(value, known), value);
  }
});

test("unknown period strings fall back to current", () => {
  for (const value of ["", "nope", "post-", "week-3; drop table", "4", "1000001", "post-99", "abc123@2099-01-01T00:00:00.000Z"]) {
    assert.equal(normalizeRatingPeriod(value, known), "current");
  }
});

const bound = { period: "abc123@2026-10-12T00:00:00.000Z", ratingCount: 10, hasRelease: true };

test("history is bounded by the release when a non-preseason period has ratings and a release is active", () => {
  assert.equal(canBoundHistoryByRelease(bound), true);
});

test("history is only the selected period with no active release, no ratings, or the preseason tab", () => {
  assert.equal(canBoundHistoryByRelease({ ...bound, hasRelease: false }), false);
  assert.equal(canBoundHistoryByRelease({ ...bound, ratingCount: 0 }), false);
  assert.equal(canBoundHistoryByRelease({ ...bound, period: "preseason" }), false);
});
