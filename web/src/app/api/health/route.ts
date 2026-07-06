import { NextResponse } from "next/server";
import { db, schema } from "@/lib/db";
import { count } from "drizzle-orm";

export const dynamic = "force-dynamic";

export async function GET() {
  const start = Date.now();
  try {
    const rows = await db
      .select({ count: count() })
      .from(schema.games);
    const gamesCount = rows[0]?.count ?? 0;
    return NextResponse.json({
      status: "ok",
      games: gamesCount,
      latencyMs: Date.now() - start,
    });
  } catch (err) {
    return NextResponse.json(
      {
        status: "error",
        error: err instanceof Error ? err.message : "unknown",
        latencyMs: Date.now() - start,
      },
      { status: 500 },
    );
  }
}
