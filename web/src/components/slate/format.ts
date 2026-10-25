import { etDateTime, etKickoff, etLongWeekdayDate, etWeekdayDate } from "@/lib/time-et";

/** Slate-facing names for the shared Eastern-time formatters. */

/** "7:30 PM ET", or "Time TBD" for a placeholder kickoff. */
export const kickoffTime = etKickoff;

/** "Saturday, Oct 24" */
export const dayLabel = etLongWeekdayDate;

/** "Oct 24, 7:30 PM ET" */
export const stamp = etDateTime;

/** "Sat, Oct 24" */
export const dayShort = etWeekdayDate;
