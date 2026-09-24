import { NextResponse } from "next/server";
import type { NextRequest } from "next/server";
import { db, schema } from "@/lib/db";
import { publicationScope } from "@/lib/publication";
import { getRunForWeek } from "@/lib/queries";
import { eq } from "drizzle-orm";

export const dynamic = "force-dynamic";

function parseIntParam(value: string | null): number | null {
  if (value === null) return null;
  const parsed = Number(value);
  return Number.isInteger(parsed) ? parsed : null;
}

/**
 * Explicitly requested season/week for selected-run health. A week outside
 * the allowed window is rejected fail-closed rather than silently clamped.
 */
function parseRequestedWeek(
  seasonParam: string | null,
  weekParam: string | null,
): { season: number; week: number } | { error: string } | null {
  if (seasonParam === null && weekParam === null) return null;
  if (seasonParam === null || weekParam === null) {
    return { error: "season and week must be requested together" };
  }
  const season = parseIntParam(seasonParam);
  const week = parseIntParam(weekParam);
  if (season === null || week === null) {
    return { error: "season and week must be integers" };
  }
  if (season < 2021 || season > 2100 || week < 0 || week > 23) {
    return { error: "requested season or week is out of range" };
  }
  return { season, week };
}

export async function GET(request: NextRequest) {
  const start = Date.now();
  const requested = parseRequestedWeek(
    request.nextUrl.searchParams.get("season"),
    request.nextUrl.searchParams.get("week"),
  );
  if (requested && "error" in requested) {
    return NextResponse.json(
      { status: "error", error: requested.error, latencyMs: Date.now() - start },
      { status: 400 },
    );
  }
  try {
    const currentRows = await db.select().from(schema.currentWeek)
      .where(eq(schema.currentWeek.id, 1)).limit(1);
    const current = currentRows[0];
    const runRows = current?.activeRunId
      ? await db.select().from(schema.predictionRuns)
          .where(eq(schema.predictionRuns.runId, current.activeRunId)).limit(1)
      : [];
    const run = runRows[0];

    // Selected-run health for an explicitly requested slate. A missing
    // selection stays null; it never falls back to the current-week pointer.
    let selectedWeek: Record<string, unknown> | null = null;
    if (requested) {
      const selection = await getRunForWeek(requested.season, requested.week);
      const sameSlate = current !== undefined
        && current.season === requested.season
        && current.week === requested.week;
      selectedWeek = {
        season: requested.season,
        week: requested.week,
        selection: selection
          ? {
              runId: selection.runId,
              modelId: selection.modelId,
              state: selection.state,
              evidenceClass: selection.evidenceClass,
              coverage: {
                expected: selection.expectedGames,
                predicted: selection.predictedGames,
                lined: selection.linedGames,
              },
              artifactFreshness: selection.createdAt.toISOString(),
            }
          : null,
        // Only comparable when the singleton points at the requested slate.
        agreesWithCurrentWeek: sameSlate
          ? selection !== null && current?.activeRunId === selection.runId
          : null,
      };
    }

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
      selectedWeek,
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
