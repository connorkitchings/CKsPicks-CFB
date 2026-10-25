import { test } from "node:test";
import assert from "node:assert/strict";
import {
  etClock, etDate, etDateTime, etDateYear, etDateYearTime, etKickoff, etLongDate, etLongWeekdayDate, etTime, etWeekdayDate, etWeekdayDateKickoff, etWeekdayDateTime,
  isTimeTbd, nextEtDayStart,
} from "./time-et.ts";

const autumn = new Date("2026-10-24T23:30:00Z"); // EDT, UTC-4

test("formats a clock time with an ET label and plain spaces", () => {
  assert.equal(etTime(autumn), "7:30 PM ET");
  assert.equal(etClock(autumn), "7:30 PM");
  assert.equal(etDateTime(autumn), "Oct 24, 7:30 PM ET");
  assert.equal(etWeekdayDateTime(autumn), "Sat, Oct 24, 7:30 PM ET");
  assert.equal(etDateYearTime(autumn), "Oct 24, 2026, 7:30 PM ET");
  assert.ok(!/[  ]/.test(etDateYearTime(autumn)));
});

test("formats date-only values without a zone label", () => {
  assert.equal(etDate(autumn), "Oct 24");
  assert.equal(etDateYear(autumn), "Oct 24, 2026");
  assert.equal(etLongDate(autumn), "October 24, 2026");
  assert.equal(etWeekdayDate(autumn), "Sat, Oct 24");
  assert.equal(etLongWeekdayDate(autumn), "Saturday, Oct 24");
});

test("a UTC evening that is already the next UTC day stays on the Eastern date", () => {
  assert.equal(etDate(new Date("2026-10-21T01:30:00Z")), "Oct 20");
  assert.equal(etDate(new Date("2026-10-20T03:00:00Z")), "Oct 19");
  assert.equal(etDate(new Date("2026-10-20T04:00:00Z")), "Oct 20");
  assert.equal(etWeekdayDateTime(new Date("2026-10-25T02:00:00Z")), "Sat, Oct 24, 10:00 PM ET");
});

test("follows daylight saving at the fall-back change (Nov 1 2026)", () => {
  assert.equal(etTime(new Date("2026-11-01T05:30:00Z")), "1:30 AM ET"); // still EDT (UTC-4)
  assert.equal(etTime(new Date("2026-11-01T06:30:00Z")), "1:30 AM ET"); // repeated hour, now EST (UTC-5)
  assert.equal(etTime(new Date("2026-11-01T17:00:00Z")), "12:00 PM ET");
  assert.equal(etDate(new Date("2026-11-02T04:59:00Z")), "Nov 1");
  assert.equal(etDate(new Date("2026-11-02T05:00:00Z")), "Nov 2");
});

test("follows daylight saving at the spring-forward change (Mar 8 2026)", () => {
  assert.equal(etTime(new Date("2026-03-08T06:59:00Z")), "1:59 AM ET"); // EST (UTC-5)
  assert.equal(etTime(new Date("2026-03-08T07:00:00Z")), "3:00 AM ET"); // 2:00 AM does not exist
  assert.equal(etDate(new Date("2026-03-09T03:59:00Z")), "Mar 8"); // EDT (UTC-4)
  assert.equal(etDate(new Date("2026-03-09T04:00:00Z")), "Mar 9");
});

test("a midnight Eastern placeholder is time TBD in both daylight and standard time", () => {
  assert.equal(isTimeTbd(new Date("2026-10-24T04:00:00Z")), true); // EDT
  assert.equal(isTimeTbd(new Date("2026-12-05T05:00:00Z")), true); // EST
  assert.equal(etKickoff(new Date("2026-10-24T04:00:00Z")), "Time TBD");
  assert.equal(etWeekdayDateKickoff(new Date("2026-10-24T04:00:00Z")), "Sat, Oct 24, time TBD");
});

test("real kickoffs are not time TBD", () => {
  assert.equal(isTimeTbd(new Date("2026-10-24T04:30:00Z")), false); // 12:30 AM EDT
  assert.equal(isTimeTbd(new Date("2026-10-24T16:00:00Z")), false); // noon EDT
  assert.equal(isTimeTbd(new Date("2026-10-24T05:00:00Z")), false); // 1:00 AM EDT
  assert.equal(etKickoff(new Date("2026-10-24T04:30:00Z")), "12:30 AM ET");
  assert.equal(etWeekdayDateKickoff(autumn), "Sat, Oct 24, 7:30 PM ET");
});

test("the end of an Eastern day is the next midnight, across a daylight-saving change", () => {
  assert.equal(nextEtDayStart(new Date("2026-10-24T04:00:00Z")).toISOString(), "2026-10-25T04:00:00.000Z");
  assert.equal(nextEtDayStart(new Date("2026-10-31T04:00:00Z")).toISOString(), "2026-11-01T04:00:00.000Z");
  assert.equal(nextEtDayStart(new Date("2026-11-01T04:00:00Z")).toISOString(), "2026-11-02T05:00:00.000Z"); // 25-hour day
  assert.equal(nextEtDayStart(new Date("2026-10-24T23:30:00Z")).toISOString(), "2026-10-25T04:00:00.000Z");
});
