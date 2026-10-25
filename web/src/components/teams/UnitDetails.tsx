"use client";

import { useEffect, useRef, type DetailsHTMLAttributes } from "react";

/**
 * A `<details>` whose `<summary>` is a static heading from `sm:` up (the content is forced open
 * in globals.css): there it leaves the tab order and cannot toggle. On phones it is a normal disclosure.
 */
export function UnitDetails(props: DetailsHTMLAttributes<HTMLDetailsElement>) {
  const ref = useRef<HTMLDetailsElement>(null);
  useEffect(() => {
    const summary = ref.current?.querySelector("summary");
    if (!summary) return;
    const wide = window.matchMedia("(min-width: 40rem)");
    const sync = () => (wide.matches ? summary.setAttribute("tabindex", "-1") : summary.removeAttribute("tabindex"));
    const block = (event: Event) => {
      if (wide.matches) event.preventDefault();
    };
    sync();
    wide.addEventListener("change", sync);
    summary.addEventListener("click", block);
    return () => {
      wide.removeEventListener("change", sync);
      summary.removeEventListener("click", block);
    };
  }, []);
  return <details ref={ref} {...props} />;
}
