"use client";

import { useState, type ComponentProps } from "react";
import type { MetricSection } from "@/lib/team-stats";
import { UnitMatchupTable } from "./UnitMatchupTable";

type Unit = ComponentProps<typeof UnitMatchupTable>;

/** Keep selection through resizes while showing both comparisons on larger screens. */
export function UnitMatchups({ away, home, selected = "away" }: { away: Unit; home: Unit; selected?: "away" | "home" }) {
  const [collapsedSections, setCollapsedSections] = useState<ReadonlySet<MetricSection>>(() => new Set());

  function toggleSection(section: MetricSection) {
    if (section === "possession") return;
    setCollapsedSections((current) => {
      const next = new Set(current);
      if (next.has(section)) next.delete(section);
      else next.add(section);
      return next;
    });
  }

  return (
    <div className="space-y-4">
      <h2 className="sr-only">Unit comparisons</h2>
      <UnitMatchupTable {...(selected === "away" ? away : home)} collapsedSections={collapsedSections} onToggleSection={toggleSection} />
    </div>
  );
}
