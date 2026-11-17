"use client";

import { useEffect, useState } from "react";

/** Measures a container's CSS width so an SVG viewBox can match it 1:1 (text keeps its true size). `ref` goes on the container. */
export function useMeasuredWidth(enabled: boolean, fallback: number) {
  const [node, setNode] = useState<HTMLElement | null>(null);
  const [width, setWidth] = useState(fallback);
  useEffect(() => {
    if (!enabled || !node) return;
    const observer = new ResizeObserver(([entry]) => setWidth(Math.round(entry.contentRect.width) || fallback));
    observer.observe(node);
    return () => observer.disconnect();
  }, [enabled, node, fallback]);
  return { ref: setNode, width };
}
