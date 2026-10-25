/**
 * The one place the site formats dates and times. Everything is US Eastern
 * (America/New_York, daylight-saving aware) with an explicit locale, so the
 * server and the browser render identical text. Clock times carry an "ET"
 * label; date-only values do not. Parts are assembled by hand because Node and
 * Safari join date and time with different words and narrow no-break spaces.
 */
export const SITE_TIME_ZONE = "America/New_York";

type Field = "weekday" | "month" | "day" | "year" | "hour" | "minute" | "dayPeriod";

function parts(d: Date, options: Intl.DateTimeFormatOptions): Record<Field, string> {
  const out = { weekday: "", month: "", day: "", year: "", hour: "", minute: "", dayPeriod: "" };
  for (const part of new Intl.DateTimeFormat("en-US", { ...options, timeZone: SITE_TIME_ZONE }).formatToParts(d)) {
    if (part.type in out) out[part.type as Field] = part.value;
  }
  return out;
}

const CLOCK = { hour: "numeric", minute: "2-digit" } as const;

/** "Oct 24" */
export function etDate(d: Date): string {
  const p = parts(d, { month: "short", day: "numeric" });
  return `${p.month} ${p.day}`;
}

/** "Oct 24, 2026" */
export function etDateYear(d: Date): string {
  const p = parts(d, { month: "short", day: "numeric", year: "numeric" });
  return `${p.month} ${p.day}, ${p.year}`;
}

/** "October 24, 2026" */
export function etLongDate(d: Date): string {
  const p = parts(d, { month: "long", day: "numeric", year: "numeric" });
  return `${p.month} ${p.day}, ${p.year}`;
}

/** "Sat, Oct 24" */
export function etWeekdayDate(d: Date): string {
  const p = parts(d, { weekday: "short", month: "short", day: "numeric" });
  return `${p.weekday}, ${p.month} ${p.day}`;
}

/** "Saturday, Oct 24" */
export function etLongWeekdayDate(d: Date): string {
  const p = parts(d, { weekday: "long", month: "short", day: "numeric" });
  return `${p.weekday}, ${p.month} ${p.day}`;
}

/** "7:30 PM" with no zone label, for rows under a heading that already says times are ET. */
export function etClock(d: Date): string {
  const p = parts(d, CLOCK);
  return `${p.hour}:${p.minute} ${p.dayPeriod}`;
}

/** "7:30 PM ET" */
export function etTime(d: Date): string {
  return `${etClock(d)} ET`;
}

/** "Oct 24, 7:30 PM ET" */
export function etDateTime(d: Date): string {
  return `${etDate(d)}, ${etTime(d)}`;
}

/** "Oct 24, 2026, 7:30 PM ET" */
export function etDateYearTime(d: Date): string {
  return `${etDateYear(d)}, ${etTime(d)}`;
}

/** "Sat, Oct 24, 7:30 PM ET" */
export function etWeekdayDateTime(d: Date): string {
  return `${etWeekdayDate(d)}, ${etTime(d)}`;
}

/**
 * True when the Eastern wall clock reads exactly 00:00. The data source sends a placeholder at
 * midnight Eastern for games whose kickoff time is not announced yet (a real 12:30 AM game is not one).
 */
export function isTimeTbd(d: Date): boolean {
  const p = parts(d, { hour: "numeric", minute: "2-digit", hourCycle: "h23" });
  return Number(p.hour) % 24 === 0 && p.minute === "00" && d.getTime() % 60_000 === 0;
}

/** "Time TBD" for a placeholder, else "7:30 PM ET". */
export function etKickoff(d: Date): string {
  return isTimeTbd(d) ? "Time TBD" : etTime(d);
}

/** "Sat, Oct 24, time TBD" for a placeholder, else "Sat, Oct 24, 7:30 PM ET". */
export function etWeekdayDateKickoff(d: Date): string {
  return isTimeTbd(d) ? `${etWeekdayDate(d)}, time TBD` : etWeekdayDateTime(d);
}

/** Midnight Eastern that ends the Eastern calendar day containing `d`. */
export function nextEtDayStart(d: Date): Date {
  const day = (t: number) => etDateYear(new Date(t));
  const hour = 3_600_000;
  const today = day(d.getTime());
  // Eastern offsets are whole hours, so midnight falls on an hour boundary.
  let t = Math.floor(d.getTime() / hour) * hour + hour;
  while (day(t) === today) t += hour;
  return new Date(t);
}
