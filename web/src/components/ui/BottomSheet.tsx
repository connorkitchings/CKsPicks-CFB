"use client";

import { useEffect, useId, useRef, type HTMLAttributes, type ReactNode, type RefObject } from "react";

/**
 * Native-dialog sheet logic: body scroll lock with scroll restore, visualViewport sizing, focus
 * returned to the trigger on close, Escape. `enabled` gates the dialog (render `<BottomSheet>`
 * only while enabled); `closeOn` values close the sheet whenever any of them changes.
 */
export function useSheet({ enabled, closeOn = [] }: { enabled: boolean; closeOn?: readonly unknown[] }) {
  const dialogRef = useRef<HTMLDialogElement>(null);
  const triggerRef = useRef<HTMLButtonElement>(null);
  const unlock = useRef<(() => void) | null>(null);
  const titleId = useId();
  const closeKey = JSON.stringify(closeOn);

  useEffect(() => {
    const sheet = dialogRef.current;
    if (!sheet) return;
    const restore = () => {
      unlock.current?.();
      unlock.current = null;
      triggerRef.current?.focus({ preventScroll: true });
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
  }, [enabled]);

  useEffect(() => {
    dialogRef.current?.close();
  }, [closeKey]);

  function open() {
    const sheet = dialogRef.current;
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

  const close = () => dialogRef.current?.close();

  return { dialogRef, triggerRef, titleId, open, close };
}

/** The full-height dialog of a `useSheet` (pass its `dialogRef`, `titleId` and `close`): title, Close button and a scrolling body. */
export function BottomSheet({ dialogRef, titleId, onClose, title, children, bodyProps, ...dialogProps }: {
  dialogRef: RefObject<HTMLDialogElement | null>;
  titleId: string;
  onClose: () => void;
  title: string;
  children: ReactNode;
  bodyProps?: HTMLAttributes<HTMLDivElement>;
} & Omit<HTMLAttributes<HTMLDialogElement>, "children" | "title">) {
  return (
    <dialog ref={dialogRef} aria-labelledby={titleId} className="fixed inset-x-0 bottom-auto m-0 h-dvh max-h-none w-full max-w-none border-0 bg-surface-card p-0 text-ink backdrop:bg-black/50" {...dialogProps}>
      <div className="flex h-full min-h-0 flex-col overscroll-contain px-4 pt-[max(1rem,env(safe-area-inset-top))] pb-[max(1rem,env(safe-area-inset-bottom))]">
        <header className="flex shrink-0 items-center justify-between gap-3 border-b border-line pb-3">
          <h2 id={titleId} className="text-lg font-bold">{title}</h2>
          <button type="button" autoFocus onClick={onClose} className="min-h-11 min-w-11 rounded-lg border border-line px-3 font-semibold focus-visible:outline-2 focus-visible:outline-accent">Close</button>
        </header>
        <div className="min-h-0 flex-1 space-y-4 overflow-y-auto overscroll-contain py-4" {...bodyProps}>{children}</div>
      </div>
    </dialog>
  );
}
