"use client";

import Link from "next/link";
import { useSearchParams } from "next/navigation";
import type { ComponentProps } from "react";
import { withChartState } from "@/lib/chart-config";

/**
 * A `/stats` link that carries the current `team=` highlight, which the chart view
 * updates in place without a server render.
 */
export function ChartLink({ href, ...props }: Omit<ComponentProps<typeof Link>, "href"> & { href: string }) {
  const params = useSearchParams();
  return <Link href={withChartState(href, params.toString())} {...props} />;
}
