"use client";

import { useState } from "react";
import { SegmentedControl } from "@/components/ui/SegmentedControl";
import { TeamSection } from "@/components/teams/TeamSection";
import { RatingTimeline } from "@/components/ratings/RatingTimeline";
import type { RatingHistoryPeriod, RatingMetric } from "@/lib/team-analysis";
import type { TeamRankPoint } from "@/lib/team-rank-history";

/** Profile and Teams hub share the exact-period component/rank presentation. */
export function RatingTrend({ history = [], team }: { points?: readonly TeamRankPoint[]; history?: RatingHistoryPeriod[]; team: string }) {
  const [measure, setMeasure] = useState<"rating" | "rank">("rating");
  const [metric, setMetric] = useState<RatingMetric>("overall");
  return <TeamSection id="team-rating-trend" title="Rating trend"><div className="mb-4 space-y-2"><SegmentedControl label="Rating component" value={metric} onChange={setMetric} options={[{ value: "overall", label: "Overall" }, { value: "offense", label: "Offense" }, { value: "defense", label: "Defense" }]} size="sm" /><SegmentedControl label="Trend measure" value={measure} onChange={setMeasure} options={[{ value: "rating", label: "Rating" }, { value: "rank", label: "Rank" }]} size="sm" testId="trend-measure" /></div><RatingTimeline history={history} teams={[team]} metric={metric} measure={measure} /></TeamSection>;
}
