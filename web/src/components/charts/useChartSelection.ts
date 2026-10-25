"use client";

import { useCallback, useEffect, useRef, useState, type KeyboardEvent, type PointerEvent } from "react";

/**
 * Tooltip selection and arrow-key movement shared by the chart marks. `keys` are the
 * focusable marks in sort order; arrow keys wrap around.
 */
export function useChartSelection(keys: readonly string[], { manualTouch = false }: { manualTouch?: boolean } = {}) {
  const [selected, setSelected] = useState<string | null>(null);
  const refs = useRef(new Map<string, SVGGElement>());
  const isTouchRef = useRef(false);
  const wasSelectedRef = useRef(false);
  const touchStart = useRef<{ x: number; y: number } | null>(null);
  const cancelled = useRef(false);
  useEffect(() => {
    const cancel = () => { if (touchStart.current) cancelled.current = true; };
    document.addEventListener("scroll", cancel, true);
    return () => document.removeEventListener("scroll", cancel, true);
  }, []);

  const register = useCallback(
    (key: string) => (node: SVGGElement | null) => {
      if (node) refs.current.set(key, node);
      else refs.current.delete(key);
    },
    [],
  );

  const handlers = (key: string) => ({
    onPointerDown: (event: PointerEvent<SVGGElement>) => {
      isTouchRef.current = event.pointerType === "touch";
      wasSelectedRef.current = selected === key;
      touchStart.current = isTouchRef.current ? { x: event.clientX, y: event.clientY } : null;
      cancelled.current = false;
    },
    onPointerMove: (event: PointerEvent<SVGGElement>) => {
      const start = touchStart.current;
      if (start && Math.hypot(event.clientX - start.x, event.clientY - start.y) > 8) cancelled.current = true;
    },
    onPointerCancel: () => { cancelled.current = true; touchStart.current = null; },
    onMouseEnter: () => {
      if (!isTouchRef.current) setSelected(key);
    },
    onMouseLeave: () => {
      if (!isTouchRef.current) {
        setSelected((current) => (current === key ? null : current));
      }
    },
    onFocus: () => {
      if (!isTouchRef.current) setSelected(key);
    },
    onBlur: () => {
      // A touch tap highlights the mark, reordering it in the DOM and firing a spurious blur;
      // keep the touch selection until the next tap toggles it.
      if (isTouchRef.current) return;
      setSelected((current) => (current === key ? null : current));
    },
    onClick: () => {
      // Focus (on pointerdown) has already selected the mark, so a touch tap toggles from
      // the selection held before the tap.
      if (isTouchRef.current && (manualTouch || cancelled.current)) return;
      touchStart.current = null;
      if (isTouchRef.current) setSelected(wasSelectedRef.current ? null : key);
      else setSelected(key);
    },
    onKeyDown: (event: KeyboardEvent<SVGGElement>) => {
      isTouchRef.current = false;
      touchStart.current = null;
      const index = keys.indexOf(key);
      const go = (step: number) => {
        event.preventDefault();
        if (index < 0 || !keys.length) return;
        refs.current.get(keys[(index + step + keys.length) % keys.length])?.focus();
      };
      if (event.key === "ArrowRight" || event.key === "ArrowDown") go(1);
      else if (event.key === "ArrowLeft" || event.key === "ArrowUp") go(-1);
      else if (event.key === "Home") {
        event.preventDefault();
        refs.current.get(keys[0])?.focus();
      } else if (event.key === "End") {
        event.preventDefault();
        refs.current.get(keys[keys.length - 1])?.focus();
      } else if (event.key === "Escape") setSelected(null);
      else if (event.key === "Enter" || event.key === " ") {
        event.preventDefault();
        setSelected((current) => (current === key ? null : key));
      }
    },
  });

  return { selected, setSelected, clearSelection: () => setSelected(null), register, handlers };
}
