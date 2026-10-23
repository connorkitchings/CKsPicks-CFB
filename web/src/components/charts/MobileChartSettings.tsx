"use client";

import { useSyncExternalStore, type ReactNode } from "react";
import { createPortal } from "react-dom";
import { usePathname, useSearchParams } from "next/navigation";
import { DEFAULT_CHART, SETTINGS_SLOT_ID } from "@/lib/chart-config";
import { BottomSheet, useSheet } from "@/components/ui/BottomSheet";
import { useIsPhone } from "@/lib/use-is-phone";

// The slot lives in server-rendered page markup: null on the server and during hydration, found afterwards.
const subscribeNever = () => () => {};
const findSlot = () => document.getElementById(SETTINGS_SLOT_ID);

/**
 * One settings tree: inline on desktop, inside the native sheet on mobile. On phones the
 * trigger is portalled into the sticky bar's slot, the summary and finder flow as items of
 * the parent's controls row (this wrapper is `display: contents`), and the sheet is unchanged.
 */
export function MobileChartSettings({ children, summary, conference, finder }: { children: ReactNode; summary: ReactNode; conference: ReactNode; finder?: ReactNode }) {
  const mobile = useIsPhone();
  const slot = useSyncExternalStore(subscribeNever, findSlot, () => null);
  const pathname = usePathname();
  const params = useSearchParams();
  const currentChart = params.get("chart") ?? DEFAULT_CHART;

  // URL-backed chart switching or navigating away closes the sheet.
  // In-sheet settings (week, side, metric, conf) stay open so changes apply immediately without dismissing the sheet.
  const { dialogRef, triggerRef, titleId, open, close } = useSheet({ enabled: mobile, closeOn: [pathname, currentChart] });

  // One tree for both states so the summary and trigger keep their DOM nodes (and focus) when
  // `mobile` flips after hydration. The server renders `mobile === false`; the dialog only exists
  // once it is true, so the trigger is disabled until `open()` can actually open it.
  return (
    <>
      {!mobile && (
        <div className="hidden sm:flex flex-wrap items-center gap-x-2.5 gap-y-2" role="group" aria-label="Chart controls">
          {conference}
          {finder}
          {children}
        </div>
      )}
      <div className="contents sm:hidden" data-testid="mobile-chart-settings">
        <p className="order-1 min-w-0 flex-1 text-xs leading-relaxed text-ink-muted" data-testid="chart-settings-summary">{summary}</p>
        {mobile && slot && createPortal(
          <button ref={triggerRef} type="button" aria-haspopup="dialog" aria-label="Chart settings" onClick={open} className="inline-flex min-h-11 min-w-11 items-center justify-center gap-2 rounded-lg border border-line bg-surface-card px-3 text-sm font-semibold text-ink focus-visible:outline-2 focus-visible:outline-accent">
            <svg aria-hidden viewBox="0 0 24 24" width="20" height="20" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"><circle cx="12" cy="12" r="3" /><path d="M19.4 15a1.7 1.7 0 0 0 .3 1.8l.1.1a2 2 0 1 1-2.8 2.8l-.1-.1a1.7 1.7 0 0 0-1.8-.3 1.7 1.7 0 0 0-1 1.5V21a2 2 0 1 1-4 0v-.1a1.7 1.7 0 0 0-1.1-1.5 1.7 1.7 0 0 0-1.8.3l-.1.1a2 2 0 1 1-2.8-2.8l.1-.1a1.7 1.7 0 0 0 .3-1.8 1.7 1.7 0 0 0-1.5-1H3a2 2 0 1 1 0-4h.1a1.7 1.7 0 0 0 1.5-1.1 1.7 1.7 0 0 0-.3-1.8l-.1-.1a2 2 0 1 1 2.8-2.8l.1.1a1.7 1.7 0 0 0 1.8.3H9a1.7 1.7 0 0 0 1-1.5V3a2 2 0 1 1 4 0v.1a1.7 1.7 0 0 0 1 1.5 1.7 1.7 0 0 0 1.8-.3l.1-.1a2 2 0 1 1 2.8 2.8l-.1.1a1.7 1.7 0 0 0-.3 1.8V9a1.7 1.7 0 0 0 1.5 1H21a2 2 0 1 1 0 4h-.1a1.7 1.7 0 0 0-1.5 1z" /></svg>
            <span className="hidden min-[440px]:inline">Settings</span>
          </button>,
          slot,
        )}
        {mobile && finder && <div className="order-3 basis-full">{finder}</div>}
        {mobile && (
          <BottomSheet dialogRef={dialogRef} titleId={titleId} onClose={close} title="Chart settings" data-testid="chart-settings-dialog" bodyProps={{ role: "group", "aria-label": "Chart controls" }}>{conference}{children}</BottomSheet>
        )}
      </div>
    </>
  );
}
