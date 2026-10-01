import Image from "next/image";
import Link from "next/link";
import clsx from "clsx";
import { logoUrl } from "@/lib/teams";

export function TeamLine({
  name,
  record,
  rank,
  home = false,
  score,
  leaning,
  size = 28,
}: {
  name: string;
  record: string | null;
  rank?: number;
  home?: boolean;
  score: number | null;
  /** True when the spread lean is on this team. */
  leaning: boolean;
  size?: number;
}) {
  return (
    <div className="flex items-center gap-2.5">
      <Image
        src={logoUrl(name)}
        alt=""
        width={size}
        height={size}
        className="shrink-0 object-contain"
        style={{ width: size, height: size }}
        unoptimized
      />
      <Link
        href={`/teams/${encodeURIComponent(name)}`}
        className={clsx(
          "min-w-0 truncate text-sm hover:text-accent-ink hover:underline focus-visible:rounded focus-visible:outline-2 focus-visible:outline-accent",
          leaning ? "font-semibold text-accent-ink" : "text-ink",
        )}
      >
        {name}
      </Link>
      {record && <span className="text-xs tabular-nums text-ink-faint">({record})</span>}
      {rank !== undefined && (
        <span
          title="V5 overall rating rank"
          className="rounded bg-surface-inset px-1 text-[10px] font-medium tabular-nums text-ink-muted"
        >
          #{rank}
        </span>
      )}
      {home && (
        <span className="text-[10px] uppercase tracking-wide text-ink-faint">home</span>
      )}
      {score !== null && (
        <span className="ml-auto font-mono text-base font-semibold tabular-nums text-ink">
          {score}
        </span>
      )}
    </div>
  );
}
