"use client";

import { useRouter, useSearchParams } from "next/navigation";

export function SeasonSelector({
  season,
  allowedSeasons,
}: {
  season: number;
  allowedSeasons: number[];
}) {
  const router = useRouter();
  const params = useSearchParams();

  if (allowedSeasons.length <= 1) return null;

  function onSelect(e: React.ChangeEvent<HTMLSelectElement>) {
    const s = Number(e.target.value);
    if (Number.isFinite(s)) {
      const q = new URLSearchParams(params.toString());
      q.set("season", String(s));
      q.delete("week");
      router.push(`/?${q.toString()}`);
    }
  }

  return (
    <div className="flex items-center gap-2">
      <label htmlFor="season-select" className="sr-only">
        Season
      </label>
      <select
        id="season-select"
        value={season}
        onChange={onSelect}
        className="rounded-md border border-line bg-surface-card px-2 py-1 text-sm font-medium text-ink focus:outline-none focus:ring-2 focus:ring-accent"
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
