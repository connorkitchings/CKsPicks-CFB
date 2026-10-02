import { stamp } from "./format";

const STATE_LABEL: Record<string, string> = {
  preview: "Preview",
  published: "Published",
  frozen: "Frozen before kickoff",
  scored: "Scored",
};

/**
 * Compact slate metadata line: run state, retrospective flag, and publication
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
    <p className="flex flex-wrap items-center gap-x-2.5 gap-y-1 px-1 text-[11px] text-ink-faint">
      {runState && <span className="font-medium text-ink-muted">{STATE_LABEL[runState] ?? runState}</span>}
      {retrospective && <span className="font-medium text-warn">Retrospective replay</span>}
      {publishedAt && <span>Run published {stamp(publishedAt)}</span>}
    </p>
  );
}
