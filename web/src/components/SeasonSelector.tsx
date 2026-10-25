"use client";

import { useId } from "react";
import { useRouter, useSearchParams } from "next/navigation";

export function SeasonSelector({
  season,
  allowedSeasons,
}: {
  season: number;
  allowedSeasons: readonly number[];
}) {
  const router = useRouter();
  const params = useSearchParams();
  const id = useId();

  if (allowedSeasons.length <= 1) return null;

  function onSelect(e: React.ChangeEvent<HTMLSelectElement>) {
    const s = Number(e.target.value);
    if (Number.isFinite(s)) {
      const q = new URLSearchParams(params.toString());
      q.set("season", String(s));
      q.delete("week");
      router.push(`/?${q.toString()}`, { scroll: false });
    }
  }

  return (
    <div className="flex items-center gap-2">
      <label htmlFor={id} className="sr-only">
        Season
      </label>
      <select
        id={id}
        value={season}
        onChange={onSelect}
        className="min-h-11 sm:min-h-9 rounded-md border border-line bg-surface-card px-2 py-1 text-sm font-medium text-ink focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-accent"
      >
        {allowedSeasons.map((s) => (
          <option key={s} value={s}>
            {s}
          </option>
        ))}
      </select>
    </div>
  );
}
