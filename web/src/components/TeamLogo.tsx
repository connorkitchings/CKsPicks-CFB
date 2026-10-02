import clsx from "clsx";
import { logoSrc, teamInitials, type LogoSize } from "@/lib/team-logos";

/**
 * Team logo at `px` CSS pixels. Serves the sharp v2 WebP pair (light/dark swap
 * via the `dark:` variant) and an initials tile for unknown teams.
 */
export default function TeamLogo({
  name,
  px,
  size,
  className,
  decorative = true,
}: {
  name: string;
  px: number;
  /** Asset size; defaults to `lg` above 32 px (36 px x 3 needs more than 96), else `sm`. */
  size?: LogoSize;
  className?: string;
  decorative?: boolean;
}) {
  // width/height attributes give the intrinsic size and aspect ratio; unlike
  // inline styles, Tailwind size classes (e.g. `h-16 w-16 sm:h-20 sm:w-20`) can
  // still override them for responsive sizing.
  const box = { width: px, height: px };
  const sizedByClass = /(^|\s)(\w+:)?[wh]-/.test(className ?? "");
  const alt = decorative ? "" : name;
  const cls = clsx("shrink-0 object-contain", className);

  const asset = size ?? (px > 32 ? "lg" : "sm");
  const light = logoSrc(name, asset, "light");
  const dark = logoSrc(name, asset, "dark");
  if (!light || !dark) {
    return (
      <span
        aria-hidden={decorative || undefined}
        role={decorative ? undefined : "img"}
        aria-label={decorative ? undefined : name}
        style={{ ...(sizedByClass ? {} : box), fontSize: Math.max(8, Math.round(px * 0.38)) }}
        className={clsx(
          "inline-flex shrink-0 items-center justify-center rounded-full bg-surface-inset font-semibold text-ink-muted",
          className,
        )}
      >
        {teamInitials(name)}
      </span>
    );
  }
  return (
    <>
      {/* eslint-disable-next-line @next/next/no-img-element */}
      <img src={light} alt={alt} {...box} data-logo className={clsx(cls, "dark:hidden")} />
      {/* eslint-disable-next-line @next/next/no-img-element */}
      <img src={dark} alt="" aria-hidden {...box} data-logo className={clsx(cls, "hidden dark:block")} />
    </>
  );
}
