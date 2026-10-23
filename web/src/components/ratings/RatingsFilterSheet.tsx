"use client";

import { useEffect, useId, useRef, type ReactNode } from "react";

/**
 * The phone Filters button and its native-dialog bottom sheet (same pattern as the chart
 * settings sheet: body scroll lock with scroll restore, visualViewport sizing, focus returned
 * to the button on close, Escape). The dialog exists only while `mobile`, so the one set of
 * controls passed as `children` is never duplicated; the button stays disabled until then.
 */
export function RatingsFilterSheet({ mobile, active, children }: { mobile: boolean; active: boolean; children: ReactNode }) {
  const dialog = useRef<HTMLDialogElement>(null);
  const trigger = useRef<HTMLButtonElement>(null);
  const unlock = useRef<(() => void) | null>(null);
  const titleId = useId();

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

  return (
    <div className="sm:hidden">
      <button
        ref={trigger}
        type="button"
        aria-label="Filters"
        aria-haspopup="dialog"
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
        {active && <span aria-hidden data-testid="ratings-filters-dot" className="absolute right-1.5 top-1.5 size-2.5 rounded-full border-2 border-surface-card bg-accent" />}
      </button>
      {mobile && (
        <dialog ref={dialog} aria-labelledby={titleId} className="fixed inset-x-0 bottom-auto m-0 h-dvh max-h-none w-full max-w-none border-0 bg-surface-card p-0 text-ink backdrop:bg-black/50" data-testid="ratings-filters-dialog">
          <div className="flex h-full min-h-0 flex-col overscroll-contain px-4 pt-[max(1rem,env(safe-area-inset-top))] pb-[max(1rem,env(safe-area-inset-bottom))]">
            <header className="flex shrink-0 items-center justify-between gap-3 border-b border-line pb-3">
              <h2 id={titleId} className="text-lg font-bold">Filters</h2>
              <button type="button" autoFocus onClick={() => dialog.current?.close()} className="min-h-11 min-w-11 rounded-lg border border-line px-3 font-semibold focus-visible:outline-2 focus-visible:outline-accent">Close</button>
            </header>
            <div className="min-h-0 flex-1 space-y-4 overflow-y-auto overscroll-contain py-4">{children}</div>
          </div>
        </dialog>
      )}
    </div>
  );
}
