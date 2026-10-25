import { notFound } from "next/navigation";
import { resolveTeam } from "@/lib/team-routes";

/**
 * Resolves the team above the route's loading boundary: once `loading.tsx` has streamed its
 * shell the status is already 200, so an unknown team must be rejected here to get a real 404.
 */
export default async function TeamLayout({ children, params }: { children: React.ReactNode; params: Promise<{ team: string }> }) {
  if (!resolveTeam((await params).team)) notFound();
  return children;
}
