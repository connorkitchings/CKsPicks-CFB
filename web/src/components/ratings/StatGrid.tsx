export interface StatCell {
  label: string;
  title: string;
  value: string;
}

/** A rating as a signed two-decimal number: "+0.53", "-1.20". */
export const ratingText = (value: number) => `${value >= 0 ? "+" : ""}${value.toFixed(2)}`;

/** A row of four labelled stat cells; the Ratings phone cards and the team page header share it. */
export function StatGrid({ cells, className }: { cells: readonly StatCell[]; className?: string }) {
  return (
    <dl className={`grid grid-cols-4 gap-1 border-t border-line pt-2 ${className ?? ""}`}>
      {cells.map((cell) => (
        <div key={cell.label} title={cell.title} aria-label={cell.title} role="group" className="min-w-0 text-center">
          <dt className="text-[10px] uppercase tracking-wide text-ink-muted">{cell.label}</dt>
          <dd className="font-mono text-sm font-semibold tabular-nums text-ink">{cell.value}</dd>
        </div>
      ))}
    </dl>
  );
}
