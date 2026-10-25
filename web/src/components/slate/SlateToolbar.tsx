"use client";

import type { ReactNode } from "react";
import clsx from "clsx";
import { SearchField } from "@/components/ui/SearchField";
import { SegmentedControl } from "@/components/ui/SegmentedControl";
import { Card } from "@/components/ui/Card";
import { MobileStickyBar } from "@/components/ui/MobileStickyBar";
import { useIsPhone } from "@/lib/use-is-phone";
import { SlateFilterSheet } from "./SlateFilterSheet";

export type SlateLayout = "grid" | "list";

const SELECT_CLASS =
  "min-h-11 w-full min-w-0 truncate rounded-lg border border-line bg-surface-card px-2 text-base font-medium text-ink sm:min-h-9 sm:w-auto sm:text-sm focus-visible:outline-2 focus-visible:outline-accent";

/**
 * Search, conference, sort and layout. On phones this is the pinned bar: the week navigator centered
 * on one row, the search field and the Filters button below it; conference and sort live in the
 * Filters sheet. From 640px up it is the single toolbar card, unchanged.
 */
export function SlateToolbar<T extends string>({
  query,
  onQueryChange,
  conference = "all",
  onConferenceChange,
  conferences = [],
  sort,
  onSortChange,
  sortLabels,
  predictionsVisible,
  view,
  onViewChange,
  weekNav,
}: {
  query: string;
  onQueryChange: (value: string) => void;
  conference?: string;
  onConferenceChange?: (value: string) => void;
  conferences?: readonly string[];
  sort: T;
  onSortChange: (value: T) => void;
  sortLabels: Record<T, string>;
  predictionsVisible: boolean;
  view: SlateLayout;
  onViewChange: (value: SlateLayout) => void;
  /** The phone copy of the week navigator, shown beside the Filters button. */
  weekNav?: ReactNode;
}) {
  const mobile = useIsPhone();
  const filtersActive = conference !== "all" || (predictionsVisible && sort !== "kickoff");

  // One control tree: in the sheet on phones, inline in the card from 640px. Before hydration
  // the inline copy renders and is hidden on phones by CSS.
  const field = (label: string, control: ReactNode) => (
    <div className={clsx(!mobile && "min-w-0 flex-1 max-sm:hidden sm:flex-none")}>
      {mobile && <span className="mb-1 block text-sm font-semibold text-ink">{label}</span>}
      {control}
    </div>
  );
  const conferenceSelect = conferences.length > 0 && onConferenceChange && field("Conference", (
    <>
      <label htmlFor="slate-conference" className="sr-only">Filter by conference</label>
      <select
        id="slate-conference"
        data-testid="conference-filter"
        aria-label="Filter by conference"
        title="Shows games where either team is in the conference"
        value={conference}
        onChange={(event) => onConferenceChange(event.target.value)}
        className={SELECT_CLASS}
      >
        <option value="all">All FBS</option>
        <option value="p4">Power Four + Notre Dame</option>
        {conferences.map((conf) => (
          <option key={conf} value={conf}>{conf}</option>
        ))}
      </select>
    </>
  ));
  const sortSelect = predictionsVisible && field("Sort by", (
    <>
      <label htmlFor="slate-sort" className="sr-only">Sort by</label>
      <select
        id="slate-sort"
        value={sort}
        onChange={(event) => onSortChange(event.target.value as T)}
        className={SELECT_CLASS}
      >
        {(Object.keys(sortLabels) as T[]).map((key) => (
          <option key={key} value={key}>{sortLabels[key]}</option>
        ))}
      </select>
    </>
  ));

  return (
    <MobileStickyBar data-testid="slate-bar" className="max-sm:space-y-1.5 max-sm:pt-1! max-sm:pb-1.5!">
      <div className="flex justify-center sm:hidden">{weekNav}</div>
      <Card padding="none" className="flex items-center gap-1.5 p-2 max-sm:border-0 max-sm:bg-transparent max-sm:p-0 max-sm:shadow-none sm:flex-wrap sm:gap-2">
        <SearchField
          id="slate-search"
          label="Filter by team"
          placeholder="Filter by team…"
          value={query}
          onChange={onQueryChange}
          className="min-w-0 flex-[1.2_1_0%] sm:flex-[1_1_9rem]"
        />
        <SlateFilterSheet mobile={mobile} active={filtersActive}>
          {conferenceSelect}
          {sortSelect}
        </SlateFilterSheet>
        {!mobile && conferenceSelect}
        {!mobile && sortSelect}
        <div className="hidden shrink-0 sm:block">
          <SegmentedControl
            label="Layout"
            value={view}
            onChange={onViewChange}
            options={[{ value: "grid", label: "Grid" }, { value: "list", label: "List" }]}
          />
        </div>
      </Card>
    </MobileStickyBar>
  );
}
