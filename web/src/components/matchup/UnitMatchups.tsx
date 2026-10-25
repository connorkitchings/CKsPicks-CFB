"use client";

import { useState, type ComponentProps } from "react";
import clsx from "clsx";
import { SegmentedControl } from "@/components/ui/SegmentedControl";
import type { MetricSection } from "@/lib/team-stats";
import { UnitMatchupTable } from "./UnitMatchupTable";

type Unit = ComponentProps<typeof UnitMatchupTable>;

/** Keep selection through resizes while showing both comparisons on larger screens. */
export function UnitMatchups({ away, home }: { away: Unit; home: Unit }) {
  const [selected, setSelected] = useState<"away" | "home">("away");
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
      <SegmentedControl
        label="Offense comparison"
        value={selected}
        onChange={setSelected}
        options={[
          { value: "away", label: away.offenseTeam },
          { value: "home", label: home.offenseTeam },
        ]}
        fill
        className="lg:hidden"
      />
      <div className="grid gap-4 lg:grid-cols-2">
        <div className={clsx("min-w-0", selected !== "away" && "hidden lg:block")}>
          <UnitMatchupTable {...away} collapsedSections={collapsedSections} onToggleSection={toggleSection} />
        </div>
        <div className={clsx("min-w-0", selected !== "home" && "hidden lg:block")}>
          <UnitMatchupTable {...home} collapsedSections={collapsedSections} onToggleSection={toggleSection} />
        </div>
      </div>
    </div>
  );
}
