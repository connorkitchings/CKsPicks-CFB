"use client";

import { useState, useRef, useEffect, useId, useMemo } from "react";
import clsx from "clsx";
import { matchesSearch } from "@/lib/charts";

export type TeamHighlightComboboxProps = {
  teams: readonly { team: string; conference: string | null }[];
  highlight: string | null;
  onSelect: (team: string | null) => void;
  className?: string;
};

export function TeamHighlightCombobox({
  teams,
  highlight,
  onSelect,
  className,
}: TeamHighlightComboboxProps) {
  const [isOpen, setIsOpen] = useState(false);
  const [query, setQuery] = useState("");
  const containerRef = useRef<HTMLDivElement>(null);
  const inputRef = useRef<HTMLInputElement>(null);
  const listId = useId();
  const [activeIndex, setActiveIndex] = useState(0);
  const [listHeight, setListHeight] = useState(240);
  const [listAbove, setListAbove] = useState(false);
  const listRef = useRef<HTMLUListElement>(null);

  // Close when clicking outside
  useEffect(() => {
    function handleClickOutside(event: MouseEvent) {
      if (containerRef.current && !containerRef.current.contains(event.target as Node)) {
        setIsOpen(false);
        setQuery("");
      }
    }
    document.addEventListener("mousedown", handleClickOutside);
    return () => document.removeEventListener("mousedown", handleClickOutside);
  }, []);

  const filteredTeams = useMemo(() => {
    const q = query.trim().toLowerCase();
    if (!q) return teams;
    return teams.filter((t) => matchesSearch(q, t.team));
  }, [teams, query]);

  const options = useMemo(() => [
    ...(highlight && !query.trim() ? [{ team: null, label: "None (clear highlight)", conference: null }] : []),
    ...filteredTeams.map((team) => ({ ...team, label: team.team })),
  ], [highlight, filteredTeams, query]);
  const active = Math.min(activeIndex, options.length - 1);

  useEffect(() => {
    if (!isOpen) return;
    const viewport = window.visualViewport;
    const update = () => {
      const input = inputRef.current?.getBoundingClientRect();
      if (!input) return;
      const top = viewport?.offsetTop ?? 0;
      const bottom = top + (viewport?.height ?? window.innerHeight);
      const below = bottom - input.bottom - 12;
      const above = input.top - top - 12;
      const openAbove = below < 132 && above > below;
      setListAbove(openAbove);
      setListHeight(Math.max(0, Math.min(240, openAbove ? above : below)));
    };
    update();
    viewport?.addEventListener("resize", update);
    viewport?.addEventListener("scroll", update);
    window.addEventListener("resize", update);
    window.addEventListener("scroll", update, true);
    return () => {
      viewport?.removeEventListener("resize", update);
      viewport?.removeEventListener("scroll", update);
      window.removeEventListener("resize", update);
      window.removeEventListener("scroll", update, true);
    };
  }, [isOpen]);

  useEffect(() => {
    if (isOpen) listRef.current?.querySelector<HTMLElement>(`[id="${listId}-${active}"]`)?.scrollIntoView({ block: "nearest" });
  }, [active, isOpen, listId]);

  const handleSelect = (teamName: string | null) => {
    onSelect(teamName);
    setIsOpen(false);
    setQuery("");
  };

  const displayValue = isOpen ? query : (highlight ?? "");

  return (
    <div ref={containerRef} className={clsx("relative min-w-0 sm:w-48", className)} data-testid="team-highlight-combobox">
      <div className="relative flex items-center">
        <input
          ref={inputRef}
          type="text"
          role="combobox"
          aria-expanded={isOpen}
          aria-controls={listId}
          aria-label="Highlight a team"
          aria-autocomplete="list"
          aria-haspopup="listbox"
          aria-activedescendant={isOpen && active >= 0 ? `${listId}-${active}` : undefined}
          suppressHydrationWarning
          value={displayValue}
          placeholder="Highlight a team..."
          onFocus={() => {
            setIsOpen(true);
            setQuery("");
            setActiveIndex(0);
          }}
          onChange={(e) => {
            setQuery(e.target.value);
            setActiveIndex(0);
            if (!isOpen) setIsOpen(true);
          }}
          onKeyDown={(e) => {
            if (e.key === "Escape") {
              e.preventDefault();
              e.stopPropagation();
              setIsOpen(false);
              setQuery("");
            } else if (e.key === "ArrowDown" || e.key === "ArrowUp") {
              e.preventDefault();
              setIsOpen(true);
              setActiveIndex(isOpen && options.length ? (active + (e.key === "ArrowDown" ? 1 : -1) + options.length) % options.length : 0);
            } else if (e.key === "Enter" && isOpen && options[active]) {
              e.preventDefault();
              handleSelect(options[active].team);
            } else if (e.key === "Tab") {
              setIsOpen(false);
              setQuery("");
            }
          }}
          className="min-h-11 sm:min-h-9 w-full rounded-lg border border-line bg-surface-card pl-3 pr-12 sm:pr-8 py-1.5 text-base sm:text-xs text-ink placeholder:text-ink-muted focus:outline-none focus:ring-2 focus:ring-accent"
          data-testid="team-search"
        />

        {highlight ? (
          <button
            type="button"
            onClick={(e) => {
              e.stopPropagation();
              handleSelect(null);
            }}
            className="absolute right-0 sm:right-2 flex min-h-11 min-w-11 sm:min-h-0 sm:min-w-0 items-center justify-center text-ink-muted hover:text-ink p-0.5 rounded focus-visible:outline-2 focus-visible:outline-accent"
            aria-label="Clear team highlight"
            title="Clear highlight"
          >
            <svg className="w-3.5 h-3.5" viewBox="0 0 20 20" fill="currentColor">
              <path fillRule="evenodd" d="M4.293 4.293a1 1 0 011.414 0L10 8.586l4.293-4.293a1 1 0 111.414 1.414L11.414 10l4.293 4.293a1 1 0 01-1.414 1.414L10 11.414l-4.293 4.293a1 1 0 01-1.414-1.414L8.586 10 4.293 5.707a1 1 0 010-1.414z" clipRule="evenodd" />
            </svg>
          </button>
        ) : (
          <div className="pointer-events-none absolute right-2.5 text-ink-muted">
            <svg className="w-3.5 h-3.5" viewBox="0 0 20 20" fill="currentColor">
              <path fillRule="evenodd" d="M8 4a4 4 0 100 8 4 4 0 000-8zM2 8a6 6 0 1110.89 3.476l4.817 4.817a1 1 0 01-1.414 1.414l-4.816-4.816A6 6 0 012 8z" clipRule="evenodd" />
            </svg>
          </div>
        )}
      </div>

      {/* Hidden toggle select (kept for scripted access): it rests on the placeholder so
          choosing the highlighted team again fires a change and unhighlights it. */}
      <select
        id={`${listId}-select`}
        className="sr-only"
        tabIndex={-1}
        aria-hidden="true"
        value="choose"
        onChange={(e) => onSelect(e.target.value ? e.target.value : null)}
        data-testid="team-highlight"
      >
        <option value="choose" disabled>Choose a team to toggle</option>
        <option value="">None</option>
        {teams.map((t) => (
          <option key={t.team} value={t.team}>
            {t.team}
          </option>
        ))}
      </select>

      {/* Floating Dropdown List */}
      {isOpen && (
        <ul
          id={listId}
          ref={listRef}
          role="listbox"
          aria-label="Teams"
          style={{ maxHeight: listHeight, bottom: listAbove ? "calc(100% + 4px)" : undefined }}
          className="absolute z-50 mt-1 max-h-60 w-full overflow-y-auto rounded-xl border border-line bg-surface-card p-1 shadow-lg focus:outline-none"
        >
          {options.length === 0 ? (
            <li className="px-2.5 py-2 text-xs text-ink-muted">No teams found</li>
          ) : options.map((option, index) => (
            <li
              id={`${listId}-${index}`}
              key={option.team ?? "clear"}
              role="option"
              aria-selected={index === active}
              onMouseDown={(event) => event.preventDefault()}
              onClick={() => handleSelect(option.team)}
              className={clsx(
                "flex min-h-11 sm:min-h-0 items-center justify-between gap-2 cursor-pointer rounded-lg px-2.5 py-1.5 text-xs transition-colors",
                index === active ? "bg-accent/10 font-semibold text-accent-ink" : "text-ink hover:bg-surface-inset",
              )}
            >
              <span>{option.label}</span>
              {option.conference && <span className="text-[10px] text-ink-muted">{option.conference}</span>}
            </li>
          ))}
        </ul>
      )}
    </div>
  );
}
