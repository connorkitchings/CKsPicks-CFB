import { createHmac, timingSafeEqual } from "node:crypto";
import { revalidatePath } from "next/cache";
import { NextRequest, NextResponse } from "next/server";

export const dynamic = "force-dynamic";

export async function POST(request: NextRequest) {
  const secret = process.env.REVALIDATION_SECRET;
  if (!secret) {
    return NextResponse.json({ status: "disabled" }, { status: 503 });
  }
  const raw = await request.text();
  const signature = request.headers.get("x-cks-signature") ?? "";
  const expected = createHmac("sha256", secret).update(raw).digest("hex");
  const suppliedBuffer = Buffer.from(signature, "utf8");
  const expectedBuffer = Buffer.from(expected, "utf8");
  if (
    suppliedBuffer.length !== expectedBuffer.length ||
    !timingSafeEqual(suppliedBuffer, expectedBuffer)
  ) {
    return NextResponse.json({ status: "unauthorized" }, { status: 401 });
  }
  const payload = JSON.parse(raw) as { timestamp?: number; path?: string };
  if (!payload.timestamp || Math.abs(Date.now() - payload.timestamp) > 300_000) {
    return NextResponse.json({ status: "expired" }, { status: 401 });
  }
  const path = payload.path ?? "/";
  if (!path.startsWith("/") || path.includes("..")) {
    return NextResponse.json({ status: "invalid_path" }, { status: 400 });
  }
  revalidatePath(path);
  return NextResponse.json({ status: "revalidated", path });
}
