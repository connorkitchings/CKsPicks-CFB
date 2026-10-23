"use client";

import { useEffect, useId, useRef, useSyncExternalStore, type ReactNode } from "react";
import { createPortal } from "react-dom";
import { usePathname, useSearchParams } from "next/navigation";
import { DEFAULT_CHART, SETTINGS_SLOT_ID } from "@/lib/chart-config";
import { useMobileChart } from "./useMobileChart";

// The slot lives in server-rendered page markup: null on the server and during hydration, found afterwards.
const subscribeNever = () => () => {};
const findSlot = () => document.getElementById(SETTINGS_SLOT_ID);

/**
 * One settings tree: inline on desktop, inside the native sheet on mobile. On phones the
 * trigger is portalled into the sticky bar's slot, the summary and finder flow as items of
 * the parent's controls row (this wrapper is `display: contents`), and the sheet is unchanged.
 */
export function MobileChartSettings({ children, summary, conference, finder }: { children: ReactNode; summary: ReactNode; conference: ReactNode; finder?: ReactNode }) {
  const mobile = useMobileChart();
  const dialog = useRef<HTMLDialogElement>(null);
  const trigger = useRef<HTMLButtonElement>(null);
  const unlock = useRef<(() => void) | null>(null);
  const titleId = useId();
  const slot = useSyncExternalStore(subscribeNever, findSlot, () => null);
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
    if (!sheet || sheet.open) return; // no dialog yet: leave the body unlocked
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
          <button ref={trigger} type="button" aria-haspopup="dialog" aria-label="Chart settings" onClick={open} className="inline-flex min-h-11 min-w-11 items-center justify-center gap-2 rounded-lg border border-line bg-surface-card px-3 text-sm font-semibold text-ink focus-visible:outline-2 focus-visible:outline-accent">
            <svg aria-hidden viewBox="0 0 24 24" width="20" height="20" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"><circle cx="12" cy="12" r="3" /><path d="M19.4 15a1.7 1.7 0 0 0 .3 1.8l.1.1a2 2 0 1 1-2.8 2.8l-.1-.1a1.7 1.7 0 0 0-1.8-.3 1.7 1.7 0 0 0-1 1.5V21a2 2 0 1 1-4 0v-.1a1.7 1.7 0 0 0-1.1-1.5 1.7 1.7 0 0 0-1.8.3l-.1.1a2 2 0 1 1-2.8-2.8l.1-.1a1.7 1.7 0 0 0 .3-1.8 1.7 1.7 0 0 0-1.5-1H3a2 2 0 1 1 0-4h.1a1.7 1.7 0 0 0 1.5-1.1 1.7 1.7 0 0 0-.3-1.8l-.1-.1a2 2 0 1 1 2.8-2.8l.1.1a1.7 1.7 0 0 0 1.8.3H9a1.7 1.7 0 0 0 1-1.5V3a2 2 0 1 1 4 0v.1a1.7 1.7 0 0 0 1 1.5 1.7 1.7 0 0 0 1.8-.3l.1-.1a2 2 0 1 1 2.8 2.8l-.1.1a1.7 1.7 0 0 0-.3 1.8V9a1.7 1.7 0 0 0 1.5 1H21a2 2 0 1 1 0 4h-.1a1.7 1.7 0 0 0-1.5 1z" /></svg>
            <span className="hidden min-[440px]:inline">Settings</span>
          </button>,
          slot,
        )}
        {mobile && finder && <div className="order-3 basis-full">{finder}</div>}
        {mobile && (
      <dialog ref={dialog} aria-labelledby={titleId} className="fixed inset-x-0 bottom-auto m-0 h-dvh max-h-none w-full max-w-none border-0 bg-surface-card p-0 text-ink backdrop:bg-black/50" data-testid="chart-settings-dialog">
        <div className="flex h-full min-h-0 flex-col overscroll-contain px-4 pt-[max(1rem,env(safe-area-inset-top))] pb-[max(1rem,env(safe-area-inset-bottom))]">
          <header className="flex shrink-0 items-center justify-between gap-3 border-b border-line pb-3">
            <h2 id={titleId} className="text-lg font-bold">Chart settings</h2>
            <button type="button" autoFocus onClick={() => dialog.current?.close()} className="min-h-11 min-w-11 rounded-lg border border-line px-3 font-semibold focus-visible:outline-2 focus-visible:outline-accent">Close</button>
          </header>
          <div className="min-h-0 flex-1 space-y-4 overflow-y-auto overscroll-contain py-4" role="group" aria-label="Chart controls">{conference}{children}</div>
        </div>
      </dialog>
        )}
      </div>
    </>
  );
}
