import { test } from "node:test";
import assert from "node:assert/strict";
import { displayOnlyNotice, isDisplayOnly, isDisplayOnlyNoticeEnabled } from "./display-only.ts";

test("only an explicit true marks a run display-only", () => {
  assert.equal(isDisplayOnly({ display_only: true }), true);
  for (const value of [{}, { display_only: false }, { display_only: "true" }, null, undefined, "x", 1]) {
    assert.equal(isDisplayOnly(value), false);
  }
});

test("the notice names the week and the UTC generation date", () => {
  assert.equal(
    displayOnlyNotice(6, new Date("2026-10-08T23:30:00Z")),
    "Week 6 picks were generated on October 8, 2026 and cover only games that had not started. " +
      "They are not part of the prospective record.",
  );
  // A time just after midnight UTC is the next day, whatever the viewer's zone.
  assert.match(displayOnlyNotice(6, new Date("2026-10-09T00:30:00Z")), /October 9, 2026/);
});

test("an invalid date is refused rather than shown as Invalid Date", () => {
  assert.throws(() => displayOnlyNotice(6, new Date("nope")));
});

test("the notice renders unless explicitly disabled with CFB_DISPLAY_ONLY_NOTICE=0", () => {
  const prior = process.env.CFB_DISPLAY_ONLY_NOTICE;
  try {
    delete process.env.CFB_DISPLAY_ONLY_NOTICE;
    assert.equal(isDisplayOnlyNoticeEnabled(), true);
    process.env.CFB_DISPLAY_ONLY_NOTICE = "1";
    assert.equal(isDisplayOnlyNoticeEnabled(), true);
    process.env.CFB_DISPLAY_ONLY_NOTICE = "0";
    assert.equal(isDisplayOnlyNoticeEnabled(), false);
  } finally {
    if (prior === undefined) delete process.env.CFB_DISPLAY_ONLY_NOTICE;
    else process.env.CFB_DISPLAY_ONLY_NOTICE = prior;
  }
});
