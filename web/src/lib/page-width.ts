/** Page container widths, defined once. Values are full class names so Tailwind can see them. */
export const PAGE_WIDTHS = {
  slate: "max-w-6xl",
  wide: "max-w-5xl",
  narrow: "max-w-4xl",
} as const;

export type PageWidth = keyof typeof PAGE_WIDTHS;

/**
 * Width for a route: slate for Picks, Results and Charts; wide for Matchup,
 * Ratings and Performance; narrow for everything else.
 */
export function pageWidthFor(pathname: string): PageWidth {
  if (pathname === "/" || pathname.startsWith("/results") || pathname.startsWith("/charts")) return "slate";
  if (
    pathname.startsWith("/matchup") ||
    pathname.startsWith("/ratings") ||
    pathname.startsWith("/performance")
  ) {
    return "wide";
  }
  return "narrow";
}
