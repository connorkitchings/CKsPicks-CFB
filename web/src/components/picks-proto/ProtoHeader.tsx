import Link from "next/link";
import clsx from "clsx";
import { displaySystemName } from "@/lib/publication";
import { ThemeToggle } from "../ThemeToggle";
import { stamp } from "./format";

const TABS = [
  ["Picks", "/"],
  ["Results", "/results"],
  ["Ratings", "/ratings"],
  ["Performance", "/performance"],
] as const;

const STATE_LABEL: Record<string, string> = {
  preview: "Preview",
  published: "Published",
  frozen: "Frozen before kickoff",
  scored: "Scored",
};

/**
 * One sticky row (brand, tabs, season, theme) plus a status line, replacing the
 * two stacked bands on the live page.
 */
export function ProtoHeader({
  season,
  week,
  weeks,
  systemName,
  runState,
  retrospective,
  publishedAt,
}: {
  season: number;
  week: number;
  weeks: number[];
  systemName: string | null;
  runState: string | null;
  retrospective: boolean;
  publishedAt: Date | null;
}) {
  return (
    <header className="sticky top-0 z-30 border-b border-line bg-surface-card/90 backdrop-blur">
      <div className="mx-auto flex max-w-6xl flex-wrap items-center gap-x-6 gap-y-1 px-4 pt-3">
        <h1 className="text-lg font-bold tracking-tight text-ink">
          CK&rsquo;s Picks
          <span className="ml-1.5 text-xs font-normal text-ink-faint">CFB</span>
        </h1>
        <nav aria-label="Main navigation" className="order-3 flex w-full gap-5 overflow-x-auto text-sm font-medium sm:order-none sm:w-auto">
          {TABS.map(([label, href]) => (
            <Link
              key={href}
              href={href}
              aria-current={href === "/" ? "page" : undefined}
              className={clsx(
                "whitespace-nowrap border-b-2 py-2 transition-colors",
                href === "/"
                  ? "border-accent font-semibold text-accent-ink"
                  : "border-transparent text-ink-muted hover:text-ink",
              )}
            >
              {label}
            </Link>
          ))}
        </nav>
        <div className="ml-auto flex items-center gap-3">
          <span className="text-sm font-medium tabular-nums text-ink-muted">{season}</span>
          <ThemeToggle />
        </div>
      </div>
      <div className="mx-auto flex max-w-6xl flex-wrap items-center gap-x-2.5 gap-y-1 px-4 pb-2 pt-1 text-[11px] text-ink-faint">
        {systemName && (
          <span className="rounded bg-accent-soft px-1.5 py-0.5 font-semibold text-accent-ink">
            {displaySystemName(systemName)}
          </span>
        )}
        {weeks.length > 0 ? (
          <span className="flex items-center gap-1" aria-label="Week">
            {weeks.map((w) => (
              <Link
                key={w}
                href={`/test?week=${w}`}
                aria-current={w === week ? "true" : undefined}
                className={clsx(
                  "rounded px-1.5 py-0.5 tabular-nums",
                  w === week ? "bg-surface-inset font-semibold text-ink" : "hover:text-ink-muted",
                )}
              >
                Wk {w}
              </Link>
            ))}
          </span>
        ) : (
          <span>Week {week}</span>
        )}
        {runState && <span className="font-medium text-ink-muted">{STATE_LABEL[runState] ?? runState}</span>}
        {retrospective && <span className="font-medium text-warn">Retrospective replay</span>}
        {publishedAt && <span>Run published {stamp(publishedAt)}</span>}
      </div>
    </header>
  );
}
