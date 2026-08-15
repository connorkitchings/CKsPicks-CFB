import { NextResponse } from "next/server";
import { db, schema } from "@/lib/db";
import { publicationScope } from "@/lib/publication";
import { eq } from "drizzle-orm";

export const dynamic = "force-dynamic";

export async function GET() {
  const start = Date.now();
  try {
    const currentRows = await db.select().from(schema.currentWeek)
      .where(eq(schema.currentWeek.id, 1)).limit(1);
    const current = currentRows[0];
    const runRows = current?.activeRunId
      ? await db.select().from(schema.predictionRuns)
          .where(eq(schema.predictionRuns.runId, current.activeRunId)).limit(1)
      : [];
    const run = runRows[0];
    return NextResponse.json({
      status: "ok",
      schemaVersion: "data_platform_v1",
      publication: {
        season: publicationScope.season,
        weeks: publicationScope.weeks,
        mode: publicationScope.mode,
      },
      activeRun: run ? {
        runId: run.runId,
        season: run.season,
        week: run.week,
        state: run.state,
      } : null,
      coverage: run ? {
        expected: run.expectedGames,
        predicted: run.predictedGames,
        lined: run.linedGames,
      } : null,
      artifactFreshness: run ? run.createdAt.toISOString() : null,
      dataAsOf: run?.dataAsOf.toISOString() ?? null,
      lastSuccessfulPublish: run?.publishedAt?.toISOString() ?? null,
      latencyMs: Date.now() - start,
    });
  } catch (err) {
    console.error("Health database check failed", err);
    return NextResponse.json(
      {
        status: "error",
        error: "database_unavailable",
        latencyMs: Date.now() - start,
      },
      { status: 500 },
    );
  }
}
