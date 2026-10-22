"use client";

import { useEffect, useId, useRef, type ReactNode } from "react";
import { usePathname, useSearchParams } from "next/navigation";
import { DEFAULT_CHART } from "@/lib/chart-config";
import { useMobileChart } from "./useMobileChart";

/** One settings tree: inline on desktop, inside the native sheet on mobile. */
export function MobileChartSettings({ children, summary, conference, finder }: { children: ReactNode; summary: ReactNode; conference: ReactNode; finder?: ReactNode }) {
  const mobile = useMobileChart();
  const dialog = useRef<HTMLDialogElement>(null);
  const trigger = useRef<HTMLButtonElement>(null);
  const unlock = useRef<(() => void) | null>(null);
  const titleId = useId();
  const pathname = usePathname();
  const params = useSearchParams();
  const currentChart = params.get("chart") ?? DEFAULT_CHART;

  useEffect(() => {
    const sheet = dialog.current;
    if (!sheet) return;
    const restore = () => {
      unlock.current?.();
      unlock.current = null;
      trigger.current?.focus({ preventScroll: true });
    };
    const size = () => {
      const viewport = window.visualViewport;
      sheet.style.height = `${viewport?.height ?? window.innerHeight}px`;
      sheet.style.top = `${viewport?.offsetTop ?? 0}px`;
    };
    size();
    sheet.addEventListener("close", restore);
    window.addEventListener("resize", size);
    window.visualViewport?.addEventListener("resize", size);
    window.visualViewport?.addEventListener("scroll", size);
    return () => {
      sheet.removeEventListener("close", restore);
      window.removeEventListener("resize", size);
      window.visualViewport?.removeEventListener("resize", size);
      window.visualViewport?.removeEventListener("scroll", size);
      sheet.close();
      unlock.current?.();
      unlock.current = null;
    };
  }, [mobile]);

  // URL-backed chart switching or navigating away closes the sheet.
  // In-sheet settings (week, side, metric, conf) stay open so changes apply immediately without dismissing the sheet.
  useEffect(() => {
    dialog.current?.close();
  }, [pathname, currentChart]);

  function open() {
    const sheet = dialog.current;
    if (!sheet || sheet.open) return;
    const body = document.body;
    const x = window.scrollX;
    const y = window.scrollY;
    const previous = { position: body.style.position, top: body.style.top, left: body.style.left, width: body.style.width, overflow: body.style.overflow };
    Object.assign(body.style, { position: "fixed", top: `${-y}px`, left: `${-x}px`, width: "100%", overflow: "hidden" });
    unlock.current = () => {
      Object.assign(body.style, previous);
      window.scrollTo({ left: x, top: y, behavior: "instant" });
    };
    sheet.showModal();
  }

  if (!mobile) {
    return (
      <>
        <div className="hidden sm:flex flex-wrap items-center gap-x-2.5 gap-y-2" role="group" aria-label="Chart controls">
          {conference}
          {finder}
          {children}
        </div>
        <div className="min-w-0 flex-1 basis-full space-y-2 sm:hidden" data-testid="mobile-chart-settings">
          <p className="text-xs leading-relaxed text-ink-muted" data-testid="chart-settings-summary">{summary}</p>
          <button ref={trigger} type="button" aria-haspopup="dialog" onClick={open} className="min-h-11 rounded-lg border border-line bg-surface-card px-4 text-sm font-semibold text-ink focus-visible:outline-2 focus-visible:outline-accent">
            Chart settings
          </button>
        </div>
      </>
    );
  }

  return (
    <div className="min-w-0 flex-1 basis-full space-y-2 sm:hidden" data-testid="mobile-chart-settings">
      <p className="text-xs leading-relaxed text-ink-muted" data-testid="chart-settings-summary">{summary}</p>
      <button ref={trigger} type="button" aria-haspopup="dialog" onClick={open} className="min-h-11 rounded-lg border border-line bg-surface-card px-4 text-sm font-semibold text-ink focus-visible:outline-2 focus-visible:outline-accent">Chart settings</button>
      {finder}
      <dialog ref={dialog} aria-labelledby={titleId} className="fixed inset-x-0 bottom-auto m-0 h-dvh max-h-none w-full max-w-none border-0 bg-surface-card p-0 text-ink backdrop:bg-black/50" data-testid="chart-settings-dialog">
        <div className="flex h-full min-h-0 flex-col overscroll-contain px-4 pt-[max(1rem,env(safe-area-inset-top))] pb-[max(1rem,env(safe-area-inset-bottom))]">
          <header className="flex shrink-0 items-center justify-between gap-3 border-b border-line pb-3">
            <h2 id={titleId} className="text-lg font-bold">Chart settings</h2>
            <button type="button" autoFocus onClick={() => dialog.current?.close()} className="min-h-11 min-w-11 rounded-lg border border-line px-3 font-semibold focus-visible:outline-2 focus-visible:outline-accent">Close</button>
          </header>
          <div className="min-h-0 flex-1 space-y-4 overflow-y-auto overscroll-contain py-4" role="group" aria-label="Chart controls">{conference}{children}</div>
        </div>
      </dialog>
    </div>
  );
}
