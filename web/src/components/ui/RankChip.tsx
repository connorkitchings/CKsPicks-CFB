import type { ComponentPropsWithoutRef, CSSProperties } from "react";
import clsx from "clsx";

import { RANK_TOTAL, rankColorMix } from "@/lib/rank-color";

/*
 * RankChip: a team rank on the shared green -> red scale (see lib/rank-color.ts).
 *   <RankChip rank={14} />                        "#14"
 *   <RankChip rank={3} total={16} prefix="" />    "3"
 *   <RankChip rank={null} />                      neutral "—"
 * The rank is always printed as text in --ink, so color is never the only signal.
 * `label` replaces the printed text (e.g. "T-3") while `rank` still picks the color.
 */
export type RankChipProps = {
  rank: number | null | undefined;
  total?: number;
  prefix?: string;
  label?: string;
  className?: string;
} & Omit<ComponentPropsWithoutRef<"span">, "className" | "children">;

export function RankChip({ rank, total = RANK_TOTAL, prefix = "#", label, className, style, ...rest }: RankChipProps) {
  const mix = rankColorMix(rank, total);
  const chipStyle = mix === null ? style : ({ ...style, "--rank-t": mix } as CSSProperties);
  return (
    <span
      {...rest}
      data-rank-chip=""
      {...(mix === null ? { "data-rank-none": "" } : {})}
      style={chipStyle}
      className={clsx(
        "rank-chip inline-flex h-5 min-w-5 items-center justify-center whitespace-nowrap rounded px-1 font-mono text-xs tabular-nums",
        className,
      )}
    >
      {label ?? (mix === null ? "—" : `${prefix}${rank}`)}
    </span>
  );
}
