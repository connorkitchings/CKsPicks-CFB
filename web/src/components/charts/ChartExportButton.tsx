"use client";

import type { ReactNode } from "react";
import { ExportActions } from "@/components/ui/ExportActions";

export { settleImages, type ExportReport } from "@/components/ui/ExportActions";

const TEST_IDS = {
  container: "chart-export",
  download: "chart-download",
  copy: "chart-copy",
  share: "chart-share",
} as const;

/**
 * Exports the chart as one fixed-size image through the site's shared export actions. The
 * export card (`children`, laid out at `width` x `height` CSS pixels and captured at 2x) is
 * mounted off-screen only while an image is being made, so the page itself is unchanged.
 */
export function ChartExportButton({
  filename,
  shareTitle,
  width,
  height,
  contentKey,
  children,
}: {
  filename: string;
  shareTitle: string;
  width: number;
  height: number;
  /** Fingerprint of the chart's current view (filter, highlight, metric, week, side); see `ExportActions`. */
  contentKey: string;
  children: ReactNode;
}) {
  return (
    <ExportActions filename={filename} shareTitle={shareTitle} width={width} height={height} contentKey={contentKey} testIds={TEST_IDS}>
      {children}
    </ExportActions>
  );
}
