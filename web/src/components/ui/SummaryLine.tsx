import type { HTMLAttributes } from "react";
import { groupLabel } from "@/lib/chart-config";
import type { ConferenceFilter, Side } from "@/lib/charts";

type Part = string | null | undefined | false;

/** Joins the non-empty parts with "·" (never repeating the season, which the site header shows). */
export function summaryText(...parts: Part[]): string {
  return parts.filter(Boolean).join(" · ");
}

/** The one-line summary of a phone view. */
export function SummaryLine({ parts, ...props }: { parts: Part[] } & HTMLAttributes<HTMLParagraphElement>) {
  return <p {...props}>{summaryText(...parts)}</p>;
}

/**
 * The phone summary of every chart: `Alabama · Offense · Through Week 7 · All FBS · 20+ yard rate`.
 * `scope` stands in for an unfiltered conference ("FBS opponents" on the game log).
 */
export function chartSummary({ team, side, week, filter, scope, metric }: {
  team?: string | null;
  side?: Side | null;
  week?: { n: number; through: boolean } | null;
  filter: ConferenceFilter;
  scope?: string;
  metric?: string | null;
}): string {
  return summaryText(
    team,
    side ? (side === "offense" ? "Offense" : "Defense") : null,
    week ? `${week.through ? "Through Week" : "Week"} ${week.n}` : null,
    scope && filter === "all" ? scope : groupLabel(filter),
    metric,
  );
}
