import type { Metadata } from "next";
import { BRAND_FULL } from "@/lib/brand";

// The shared generated image (`app/opengraph-image.tsx`); a route that sets `openGraph` drops the inherited one.
const SHARE_IMAGE = "/opengraph-image";

export const SITE_DESCRIPTION = "College football forecasts, team ratings and season performance.";

/** Every public title: the page name, then the brand. */
export function fullTitle(page: string): string {
  return `${page} · ${BRAND_FULL}`;
}

/**
 * One route's metadata. `title` is the page name only: the root layout's `title.template` adds the brand to
 * the document title, while Open Graph and Twitter tags (which skip the template) get the full title here.
 * A route's `openGraph` replaces the root's wholesale, so the site-level fields are repeated.
 * `path` is the canonical, site-relative URL; `extra` carries route-specific fields such as `robots`.
 */
export function pageMetadata(
  title: string,
  description: string,
  path: string,
  extra: Metadata = {},
): Metadata {
  const full = fullTitle(title);
  return {
    title,
    description,
    alternates: { canonical: path },
    openGraph: { title: full, description, url: path, siteName: BRAND_FULL, type: "website", images: [SHARE_IMAGE] },
    twitter: { card: "summary_large_image", title: full, description, images: [SHARE_IMAGE] },
    ...extra,
  };
}

/** What every 404 (and a route whose game or team cannot be found) is titled. */
const NOT_FOUND_DESCRIPTION = "This page could not be found.";

export const notFoundMetadata: Metadata = {
  title: "Page not found",
  description: NOT_FOUND_DESCRIPTION,
  openGraph: { title: fullTitle("Page not found"), description: NOT_FOUND_DESCRIPTION, siteName: BRAND_FULL, type: "website", images: [SHARE_IMAGE] },
  twitter: { card: "summary_large_image", title: fullTitle("Page not found"), description: NOT_FOUND_DESCRIPTION, images: [SHARE_IMAGE] },
  robots: { index: false, follow: false },
};
