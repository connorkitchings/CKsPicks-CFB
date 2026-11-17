/** Page container widths, defined once. Values are full class names so Tailwind can see them. */
export const PAGE_WIDTHS = {
  slate: "max-w-[1200px]",
  wide: "max-w-[1200px]",
  narrow: "max-w-[760px]",
} as const;

/**
 * Phone page rhythm, defined once: top padding, bottom padding and the gap between a page's
 * sections. Every `<main>` starts from these (the horizontal padding is `px-4` everywhere) and sets
 * its own desktop values with `sm:` classes; pages that lay sections out with `gap` use the same
 * three values.
 */
export const PHONE_PAGE_RHYTHM = "space-y-6 pt-5 pb-8";

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
