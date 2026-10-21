import { NextResponse, type NextRequest } from "next/server";
import { isChartsEnabled } from "@/lib/charts-gate";

/**
 * Gate Stats before ancestor loading can stream an HTTP 200 shell, and move the legacy
 * `/charts` URLs to `/stats`. This lives here, not in next.config.ts, because config
 * redirects run before the proxy and could not honor the flag.
 */
export function proxy(request: NextRequest) {
  if (!isChartsEnabled()) return NextResponse.rewrite(new URL("/_not-found", request.url), { status: 404 });
  const { pathname } = request.nextUrl;
  if (pathname === "/charts" || pathname.startsWith("/charts/")) {
    const url = request.nextUrl.clone();
    url.pathname = `/stats${pathname.slice("/charts".length)}`;
    return NextResponse.redirect(url, 307);
  }
  return NextResponse.next();
}

export const config = { matcher: ["/charts", "/charts/:path*", "/stats", "/stats/:path*"] };
