"use client";

import { useCallback, useRef, useState, type KeyboardEvent } from "react";

/**
 * Tooltip selection and arrow-key movement shared by the chart marks. `keys` are the
 * focusable marks in sort order; arrow keys wrap around.
 */
export function useChartSelection(keys: readonly string[]) {
  const [selected, setSelected] = useState<string | null>(null);
  const refs = useRef(new Map<string, SVGGElement>());

  const register = useCallback(
    (key: string) => (node: SVGGElement | null) => {
      if (node) refs.current.set(key, node);
      else refs.current.delete(key);
    },
    [],
  );

  const handlers = (key: string) => ({
    onMouseEnter: () => setSelected(key),
    onMouseLeave: () => setSelected((current) => (current === key ? null : current)),
    onFocus: () => setSelected(key),
    onBlur: () => setSelected((current) => (current === key ? null : current)),
    onClick: () => setSelected((current) => (current === key ? null : key)),
    onKeyDown: (event: KeyboardEvent<SVGGElement>) => {
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

  return { selected, register, handlers };
}
