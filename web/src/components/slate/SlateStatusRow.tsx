import clsx from "clsx";
import { stamp } from "./format";

const STATE_LABEL: Record<string, string> = {
  preview: "Preview",
  published: "Published",
  frozen: "Frozen before kickoff",
  scored: "Scored",
};

const STATE_STYLES: Record<string, { pill: string; dot: string }> = {
  frozen: {
    pill: "border-accent-line/60 bg-accent-soft/70 text-accent-ink",
    dot: "bg-accent",
  },
  published: {
    pill: "border-win-line/60 bg-win-soft/70 text-win",
    dot: "bg-win",
  },
  preview: {
    pill: "border-warn-line/60 bg-warn-soft/70 text-warn",
    dot: "bg-warn",
  },
  scored: {
    pill: "border-line bg-surface-inset text-ink-muted",
    dot: "bg-ink-muted",
  },
};

/**
 * Compact slate metadata line: run state badge, retrospective flag, and publication
 * time. The model system chip and season already live in the global Header;
 * week navigation stays in WeekNav.
 */
export function SlateStatusRow({
  runState,
  retrospective,
  publishedAt,
}: {
  runState: string | null;
  retrospective: boolean;
  publishedAt: Date | null;
}) {
  if (!runState && !retrospective && !publishedAt) return null;
  return (
    <div className="contents sm:flex sm:flex-wrap sm:items-center sm:gap-2">
      {runState && (
        <span
          className={clsx(
            "inline-flex items-center gap-1.5 rounded-full border px-2 py-0.5 text-[11px] font-medium tracking-wide shadow-2xs",
            STATE_STYLES[runState]?.pill ?? "border-line bg-surface-inset text-ink-muted",
          )}
        >
          <span
            className={clsx(
              "h-1.5 w-1.5 rounded-full",
              STATE_STYLES[runState]?.dot ?? "bg-ink-muted",
            )}
            aria-hidden="true"
          />
          <span>{STATE_LABEL[runState] ?? runState}</span>
        </span>
      )}
      {retrospective && (
        <span className="inline-flex items-center gap-1.5 rounded-full border border-warn-line/60 bg-warn-soft/70 px-2 py-0.5 text-[11px] font-medium text-warn shadow-2xs">
          <span className="h-1.5 w-1.5 rounded-full bg-warn" aria-hidden="true" />
          Retrospective replay
        </span>
      )}
      {publishedAt && (
        <span className="basis-full text-[10px] text-ink-faint sm:basis-auto sm:text-[11px] sm:flex sm:items-center sm:gap-1.5">
          <span className="hidden sm:inline text-line-strong" aria-hidden="true">·</span>
          <span>Run published {stamp(publishedAt)}</span>
        </span>
      )}
    </div>
  );
}
