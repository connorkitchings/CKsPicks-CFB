"use client";

import { SearchField } from "@/components/ui/SearchField";
import { SegmentedControl } from "@/components/ui/SegmentedControl";

export type SlateLayout = "grid" | "list";

export function SlateToolbar<T extends string>({
  query,
  onQueryChange,
  sort,
  onSortChange,
  sortLabels,
  predictionsVisible,
  view,
  onViewChange,
}: {
  query: string;
  onQueryChange: (value: string) => void;
  sort: T;
  onSortChange: (value: T) => void;
  sortLabels: Record<T, string>;
  predictionsVisible: boolean;
  view: SlateLayout;
  onViewChange: (value: SlateLayout) => void;
}) {
  return (
    <div className="flex flex-wrap items-center gap-2 rounded-xl border border-line bg-surface-card p-2 shadow-sm">
      <SearchField
        id="slate-search"
        label="Filter by team"
        placeholder="Filter by team…"
        value={query}
        onChange={onQueryChange}
        className="min-w-0 flex-[1_1_9rem]"
      />
      {predictionsVisible && (
        <div className="min-w-0 flex-[1_1_8rem] sm:flex-none">
          <label htmlFor="slate-sort" className="sr-only">Sort by</label>
          <select
            id="slate-sort"
            value={sort}
            onChange={(event) => onSortChange(event.target.value as T)}
            className="min-h-11 w-full rounded-lg border border-line bg-surface-card px-2 text-base font-medium text-ink sm:text-sm focus-visible:outline-2 focus-visible:outline-accent"
          >
            {(Object.keys(sortLabels) as T[]).map((key) => (
              <option key={key} value={key}>{sortLabels[key]}</option>
            ))}
          </select>
        </div>
      )}
      <SegmentedControl
        label="Layout"
        value={view}
        onChange={onViewChange}
        options={[{ value: "grid", label: "grid" }, { value: "list", label: "list" }]}
        className="hidden shrink-0 sm:flex"
      />
    </div>
  );
}
