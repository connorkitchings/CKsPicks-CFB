"use client";

import Link from "next/link";
import { useSearchParams } from "next/navigation";
import type { ComponentProps } from "react";
import { withTeamParam } from "@/lib/chart-config";

/**
 * A `/charts` link that carries the current `team=` highlight, which the chart view
 * updates in place without a server render.
 */
export function ChartLink({ href, ...props }: Omit<ComponentProps<typeof Link>, "href"> & { href: string }) {
  const team = useSearchParams().get("team");
  return <Link href={withTeamParam(href, team)} {...props} />;
}
