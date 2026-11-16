"use client";

import { useId, useState } from "react";
import { useRouter } from "next/navigation";
import { searchAnnouncement, searchTeams } from "@/lib/team-search";
import { teamHref } from "@/lib/team-routes";


/** Canonical local team finder. No request or credentials leave the site. */
export function TeamSearch({ season, onNavigate }: { season: number | null; onNavigate?: () => void }) {
  const id = useId();
  const router = useRouter();
  const [query, setQuery] = useState("");
  const [open, setOpen] = useState(false);
  const [active, setActive] = useState(0);
  const matches = searchTeams(query);
  const showing = open && query.trim().length > 0;
  const expanded = showing && matches.length > 0;
  const go = (team: string) => {
    setOpen(false);
    setQuery("");
    onNavigate?.();
    router.push(`${teamHref(team)}${season === null ? "" : `?season=${season}`}`);
  };
  return <div className="relative w-full sm:w-56" onBlur={(event) => { if (!event.currentTarget.contains(event.relatedTarget)) setOpen(false); }}>
    <label htmlFor={id} className="sr-only">Find a team</label>
    <input id={id} role="combobox" aria-autocomplete="list" aria-expanded={expanded} aria-controls={expanded ? `${id}-results` : undefined} aria-activedescendant={open && matches[active] ? `${id}-${active}` : undefined}
      autoComplete="off" type="text" placeholder="Find a team…" value={query}
      className="min-h-11 w-full rounded-lg border border-line bg-surface-inset px-3 text-sm text-ink outline-offset-2 focus-visible:outline-2 focus-visible:outline-accent"
      onFocus={() => setOpen(true)} onChange={(event) => { setQuery(event.target.value); setActive(0); setOpen(true); }}
      onKeyDown={(event) => {
        if (event.key === "Escape" && open) { event.preventDefault(); event.stopPropagation(); setOpen(false); }
        if (event.key === "ArrowDown") { event.preventDefault(); setOpen(true); setActive((index) => open ? Math.min(index + 1, Math.max(0, matches.length - 1)) : 0); }
        if (event.key === "ArrowUp") { event.preventDefault(); setActive((index) => Math.max(0, index - 1)); }
        if (event.key === "Enter" && open && matches[active]) { event.preventDefault(); go(matches[active]); }
      }} />
    <div aria-live="polite" className="sr-only">{searchAnnouncement(query, matches.length)}</div>
    {expanded && <ul id={`${id}-results`} role="listbox" aria-label="Matching teams" className="absolute inset-x-0 top-full z-50 mt-1 max-h-80 overflow-y-auto rounded-lg border border-line bg-surface-card p-1 shadow-lg">
      {matches.map((team, index) => <li key={team} id={`${id}-${index}`} role="option" aria-selected={index === active} onMouseDown={(event) => event.preventDefault()} onClick={() => go(team)} className={`cursor-pointer rounded px-3 py-3 text-sm text-ink ${index === active ? "bg-surface-inset" : ""}`}>{team}</li>)}
    </ul>}
    {showing && matches.length === 0 && <p aria-hidden="true" className="absolute inset-x-0 top-full z-50 mt-1 rounded-lg border border-line bg-surface-card px-3 py-3 text-sm text-ink-muted shadow-lg">No matching team.</p>}
  </div>;
}
