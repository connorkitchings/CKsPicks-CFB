import { logoSrc, teamInitials } from "@/lib/team-logos";

/**
 * A team logo as an SVG `<image>` pair (light and dark variants, swapped by the `dark:`
 * variant like TeamLogo), or an initials disc for a school without a logo. Centered on
 * (cx, cy).
 */
export function TeamMark({ team, cx, cy, size }: { team: string; cx: number; cy: number; size: number }) {
  const light = logoSrc(team, "sm", "light");
  const dark = logoSrc(team, "sm", "dark");
  const x = cx - size / 2;
  const y = cy - size / 2;
  if (!light || !dark) {
    return (
      <g data-mark="initials">
        <circle cx={cx} cy={cy} r={size / 2} fill="var(--surface-inset)" stroke="var(--line-strong)" />
        <text
          x={cx}
          y={cy}
          textAnchor="middle"
          dominantBaseline="central"
          fontSize={Math.max(7, size * 0.38)}
          fontWeight={600}
          fill="var(--ink-muted)"
        >
          {teamInitials(team)}
        </text>
      </g>
    );
  }
  return (
    <g data-mark="logo">
      <image href={light} x={x} y={y} width={size} height={size} className="dark:hidden" />
      {/* One thin light glow on every dark-theme logo (following its outline) keeps near-black marks visible. */}
      <image href={dark} x={x} y={y} width={size} height={size} className="hidden dark:block dark:[filter:drop-shadow(0_0_1.2px_rgb(255_255_255/0.55))]" />
    </g>
  );
}
