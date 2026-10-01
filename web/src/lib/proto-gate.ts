import { notFound } from "next/navigation";

/**
 * The /test-picks and /test-results design prototypes are for local work. In a
 * production build they 404 unless CFB_ENABLE_TEST_PAGE=1.
 */
export function assertPrototypeEnabled(): void {
  if (process.env.NODE_ENV === "production" && process.env.CFB_ENABLE_TEST_PAGE !== "1") {
    notFound();
  }
}
