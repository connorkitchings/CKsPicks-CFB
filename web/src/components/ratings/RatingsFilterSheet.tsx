"use client";

import type { ReactNode } from "react";
import { BottomSheet, useSheet } from "@/components/ui/BottomSheet";

/**
 * The phone Filters button and its native-dialog bottom sheet (same pattern as the chart
 * settings sheet: body scroll lock with scroll restore, visualViewport sizing, focus returned
 * to the button on close, Escape). The dialog exists only while `mobile`, so the one set of
 * controls passed as `children` is never duplicated; the button stays disabled until then.
 */
export function RatingsFilterSheet({ mobile, active, children }: { mobile: boolean; active: boolean; children: ReactNode }) {
  const { dialogRef, triggerRef, titleId, open, close } = useSheet({ enabled: mobile });

  return (
    <div className="sm:hidden">
      <button
        ref={triggerRef}
        type="button"
        aria-label="Filters"
        aria-haspopup="dialog"
        aria-describedby={active ? `${titleId}-active` : undefined}
        disabled={!mobile}
        onClick={open}
        data-testid="ratings-filters-button"
        className="relative inline-flex min-h-11 min-w-11 items-center justify-center rounded-lg border border-line bg-surface-card text-ink focus-visible:outline-2 focus-visible:outline-accent disabled:cursor-not-allowed disabled:opacity-70"
      >
        <svg aria-hidden viewBox="0 0 24 24" width="20" height="20" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
          <path d="M4 6h10M18 6h2M4 12h2M10 12h10M4 18h12M20 18h0" />
          <circle cx="16" cy="6" r="2" />
          <circle cx="8" cy="12" r="2" />
          <circle cx="18" cy="18" r="2" />
        </svg>
        {active && <span id={`${titleId}-active`} className="sr-only">Filters active</span>}
        {active && <span aria-hidden data-testid="ratings-filters-dot" className="absolute right-1.5 top-1.5 size-2.5 rounded-full border-2 border-surface-card bg-accent" />}
      </button>
      {mobile && <BottomSheet dialogRef={dialogRef} titleId={titleId} onClose={close} title="Filters" data-testid="ratings-filters-dialog">{children}</BottomSheet>}
    </div>
  );
}
