import Link from "next/link";
import clsx from "clsx";
import { MobileStickyBar } from "@/components/ui/MobileStickyBar";

const TABS = [
  { key: "record", label: "Record", href: "/model" },
  { key: "method", label: "How it works", href: "/model/method" },
] as const;

export type ModelTab = (typeof TABS)[number]["key"];

/** Sub-navigation shared by the Model section's pages; each page passes its own tab. */
export function ModelTabs({ active }: { active: ModelTab }) {
  return (
    <MobileStickyBar as="nav" aria-label="Model sections" className="flex gap-1 border-b border-line max-sm:pb-0">
      {TABS.map(tab => (
        <Link
          key={tab.key}
          href={tab.href}
          aria-current={tab.key === active ? "page" : undefined}
          className={clsx(
            "-mb-px inline-flex min-h-11 items-center border-b-2 px-3 text-sm font-semibold focus-visible:outline-2 focus-visible:outline-accent",
            tab.key === active
              ? "border-accent text-ink"
              : "border-transparent text-ink-muted hover:text-ink",
          )}
        >
          {tab.label}
        </Link>
      ))}
    </MobileStickyBar>
  );
}
