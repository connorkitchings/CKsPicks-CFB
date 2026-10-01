import clsx from "clsx";

/** Three-bar strength meter for an edge tier (1 small, 2 medium, 3 large). */
export function EdgeMeter({ tier }: { tier: 0 | 1 | 2 | 3 }) {
  return (
    <span
      role="img"
      aria-label={`Edge strength ${tier} of 3`}
      className="inline-flex items-end gap-0.5"
    >
      {[1, 2, 3].map((i) => (
        <span
          key={i}
          className={clsx(
            "w-1 rounded-sm",
            i === 1 ? "h-1.5" : i === 2 ? "h-2.5" : "h-3.5",
            i <= tier ? "bg-accent" : "bg-line-strong",
          )}
        />
      ))}
    </span>
  );
}
