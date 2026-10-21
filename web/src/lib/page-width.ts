/** Page container widths, defined once. Values are full class names so Tailwind can see them. */
export const PAGE_WIDTHS = {
  slate: "max-w-6xl",
  wide: "max-w-5xl",
  narrow: "max-w-4xl",
} as const;

export type PageWidth = keyof typeof PAGE_WIDTHS;

/**
 * Width for a route: slate for Games and Stats; wide for Ratings, Model and Matchup;
 * narrow for team pages and everything else.
 */
export function pageWidthFor(pathname: string): PageWidth {
  if (pathname === "/" || pathname.startsWith("/stats")) return "slate";
  if (
    pathname.startsWith("/ratings") ||
    pathname.startsWith("/model") ||
    pathname.startsWith("/matchup")
  ) {
    return "wide";
  }
  return "narrow";
}
