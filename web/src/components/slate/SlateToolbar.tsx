"use client";

import { SearchField } from "@/components/ui/SearchField";
import { SegmentedControl } from "@/components/ui/SegmentedControl";
import { Card } from "@/components/ui/Card";

export type SlateLayout = "grid" | "list";

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
}) {
  return (
    <Card padding="none" className="flex items-center gap-1.5 p-2 sm:flex-wrap sm:gap-2">
      <SearchField
        id="slate-search"
        label="Filter by team"
        placeholder="Filter by team…"
        value={query}
        onChange={onQueryChange}
        className="min-w-0 flex-[1.2_1_0%] sm:flex-[1_1_9rem]"
      />
      {conferences.length > 0 && onConferenceChange && (
        <div className="min-w-0 flex-1 sm:flex-none">
          <label htmlFor="slate-conference" className="sr-only">Filter by conference</label>
          <select
            id="slate-conference"
            data-testid="conference-filter"
            aria-label="Filter by conference"
            title="Shows games where either team is in the conference"
            value={conference}
            onChange={(event) => onConferenceChange(event.target.value)}
            className="min-h-11 w-full min-w-0 truncate rounded-lg border border-line bg-surface-card px-2 text-base font-medium text-ink sm:min-h-9 sm:w-auto sm:text-sm focus-visible:outline-2 focus-visible:outline-accent"
          >
            <option value="all">All FBS</option>
            <option value="p4">Power Four + Notre Dame</option>
            {conferences.map((conf) => (
              <option key={conf} value={conf}>{conf}</option>
            ))}
          </select>
        </div>
      )}
      {predictionsVisible && (
        <div className="min-w-0 flex-1 sm:flex-none">
          <label htmlFor="slate-sort" className="sr-only">Sort by</label>
          <select
            id="slate-sort"
            value={sort}
            onChange={(event) => onSortChange(event.target.value as T)}
            className="min-h-11 w-full min-w-0 truncate rounded-lg border border-line bg-surface-card px-2 text-base font-medium text-ink sm:min-h-9 sm:w-auto sm:text-sm focus-visible:outline-2 focus-visible:outline-accent"
          >
            {(Object.keys(sortLabels) as T[]).map((key) => (
              <option key={key} value={key}>{sortLabels[key]}</option>
            ))}
          </select>
        </div>
      )}
      <div className="hidden shrink-0 sm:block">
        <SegmentedControl
          label="Layout"
          value={view}
          onChange={onViewChange}
          options={[{ value: "grid", label: "Grid" }, { value: "list", label: "List" }]}
        />
      </div>
    </Card>
  );
}
