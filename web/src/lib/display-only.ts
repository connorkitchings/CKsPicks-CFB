/**
 * A display-only run (Contract 04, Amendment 9) is a published prediction set generated while
 * its week was already under way. It covers only games that had not started, stays `pending`
 * and is never frozen, so it is not part of the prospective record. The publisher records
 * `display_only` in the run's `validation`; this module turns that into the visitor notice.
 */

export function isDisplayOnly(validation: unknown): boolean {
  return (
    typeof validation === "object" &&
    validation !== null &&
    (validation as Record<string, unknown>).display_only === true
  );
}

const DATE_FORMAT = new Intl.DateTimeFormat("en-US", {
  timeZone: "UTC",
  year: "numeric",
  month: "long",
  day: "numeric",
});

export function displayOnlyNotice(week: number, generatedAt: Date): string {
  if (Number.isNaN(generatedAt.getTime())) {
    throw new Error("display-only notice needs a valid generation date");
  }
  return (
    `Week ${week} picks were generated on ${DATE_FORMAT.format(generatedAt)} and cover only ` +
    "games that had not started. They are not part of the prospective record."
  );
}
