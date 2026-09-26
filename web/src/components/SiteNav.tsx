import Link from "next/link";

const items = [
  ["Predictions", "/"],
  ["Ratings", "/ratings"],
] as const;

export function SiteNav() {
  return (
    <nav aria-label="Main navigation" className="border-b border-line bg-surface-card">
      <div className="mx-auto flex max-w-4xl gap-6 overflow-x-auto px-4 py-3 text-sm font-medium text-ink-muted">
        {items.map(([label, href]) => (
          <Link key={href} href={href} className="whitespace-nowrap hover:text-accent-ink focus-visible:rounded focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-accent">
            {label}
          </Link>
        ))}
      </div>
    </nav>
  );
}
