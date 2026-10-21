import { neon, type NeonQueryFunction } from "@neondatabase/serverless";
import { drizzle, type NeonHttpDatabase } from "drizzle-orm/neon-http";
import { cache } from "react";
import type { Logger } from "drizzle-orm/logger";
import * as schema from "./schema";

/**
 * Neon serverless SQL driver wired through Drizzle ORM.
 *
 * Requires DATABASE_URL env var (Neon connection string). Example:
 *   postgres://user:password@ep-xxx.region.aws.neon.tech/dbname?sslmode=require
 *
 * In Vercel, set this via the Neon Vercel integration or manually at
 * https://vercel.com/.../settings/environment-variables.
 *
 * The client is initialized lazily so the module is importable during
 * `next build` before DATABASE_URL is configured. The error surfaces at the
 * first query, where callers (e.g. app/page.tsx) wrap it in try/catch.
 */

export type DB = NeonHttpDatabase<typeof schema>;

let _db: DB | null = null;

/**
 * `CFB_QUERY_LOG=1` logs every query with a per-request running count (React `cache` scopes
 * the counter to one server render; queries outside a render each count as request 1).
 */
let _requests = 0;
const requestCounter = cache(() => ({ id: ++_requests, count: 0 }));
const queryLogger: Logger = {
  logQuery(query) {
    const request = requestCounter();
    request.count += 1;
    console.log(`[cfb-query] req=${request.id} n=${request.count} ${query.replace(/\s+/g, " ").slice(0, 240)}`);
  },
};

function _buildClient(): DB {
  const connectionString = process.env.DATABASE_URL;
  if (!connectionString) {
    throw new Error(
      "DATABASE_URL is not set. Add it to web/.env locally, or via the Vercel project settings.",
    );
  }
  const sql: NeonQueryFunction<boolean, boolean> = neon(connectionString);
  return drizzle(sql, { schema, logger: process.env.CFB_QUERY_LOG === "1" ? queryLogger : undefined });
}

/** Lazily-initialized Drizzle client. Throws on first use if DATABASE_URL is missing. */
export const db = new Proxy({} as DB, {
  get(_target, prop) {
    if (!_db) _db = _buildClient();
    return Reflect.get(_db, prop);
  },
});

export { schema };
