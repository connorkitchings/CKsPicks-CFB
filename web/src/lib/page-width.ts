/** Page container widths, defined once. Values are full class names so Tailwind can see them. */
export const PAGE_WIDTHS = {
  slate: "max-w-6xl",
  wide: "max-w-5xl",
  narrow: "max-w-4xl",
} as const;

/**
 * Phone page rhythm, defined once: top padding, bottom padding and the gap between a page's
 * sections. Every `<main>` starts from these (the horizontal padding is `px-4` everywhere) and sets
 * its own desktop values with `sm:` classes; pages that lay sections out with `gap` use the same
 * three values.
 */
export const PHONE_PAGE_RHYTHM = "space-y-2 pt-2 pb-4";

export type PageWidth = keyof typeof PAGE_WIDTHS;

/**
 * Width for a route: slate for Games, Stats and team pages; wide for Ratings, Model and Matchup;
 * narrow for everything else.
 */
export function pageWidthFor(pathname: string): PageWidth {
  if (pathname === "/" || pathname.startsWith("/stats") || pathname.startsWith("/teams")) return "slate";
  if (
    pathname.startsWith("/ratings") ||
    pathname.startsWith("/model") ||
    pathname.startsWith("/matchup")
  ) {
    return "wide";
  }
  return "narrow";
}
