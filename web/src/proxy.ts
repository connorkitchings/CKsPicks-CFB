import { NextResponse, type NextRequest } from "next/server";
import { isChartsEnabled } from "@/lib/charts-gate";

/** Reject before ancestor loading can stream an HTTP 200 shell. */
export function proxy(request: NextRequest) {
  if (!isChartsEnabled()) return NextResponse.rewrite(new URL("/_not-found", request.url));
  return NextResponse.next();
}

export const config = { matcher: ["/charts", "/charts/:path*"] };
