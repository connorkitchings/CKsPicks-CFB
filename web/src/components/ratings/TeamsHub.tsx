"use client";

import Link from "next/link";
import { useRouter, useSearchParams } from "next/navigation";
import { useMemo } from "react";
import TeamLogo from "@/components/TeamLogo";
import { SegmentedControl } from "@/components/ui/SegmentedControl";
import { Notice } from "@/components/ui/Notice";
import { SearchField } from "@/components/ui/SearchField";
import { teamHref, resolveTeam } from "@/lib/team-routes";
import { buildConferenceMap, conferenceOptions, matchesTeamConference, type RosterRow } from "@/lib/conferences";
import { bestFirstDirection, parseRatingsSort, rankSosByTeam, type RatingsSort } from "@/lib/sos-rank";
import { nationalRanks, ratingField, weeklyMovement, type AnalysisRating, type RatingHistoryPeriod, type RatingMetric } from "@/lib/team-analysis";
import { searchParamsUrl } from "@/lib/url-state";
import { RatingTimeline } from "./RatingTimeline";

const VIEWS = [{ value: "rankings", label: "Rankings" }, { value: "trends", label: "Trends" }, { value: "resume", label: "Strength vs résumé" }, { value: "compare", label: "Compare" }] as const;
const METRICS = [{ value: "overall", label: "Overall" }, { value: "offense", label: "Offense" }, { value: "defense", label: "Defense" }] as const;
const MEASURES = [{ value: "rating", label: "Rating" }, { value: "rank", label: "Rank" }] as const;
const CONTROL = "min-h-11 min-w-0 max-w-full rounded-lg border border-line bg-surface-card px-3 text-sm text-ink";
const CELL = "whitespace-nowrap px-3 py-3 text-right tabular-nums";
const number = (n: number | null | undefined, places = 2) => n === null || n === undefined || !Number.isFinite(n) ? "—" : n.toFixed(places);
const signed = (n: number | null | undefined, places = 2) => n === null || n === undefined || !Number.isFinite(n) ? "—" : `${n > 0 ? "+" : ""}${n.toFixed(places)}`;
const record = (r: AnalysisRating) => r.wins == null || r.losses == null ? "—" : `${r.wins}–${r.losses}`;
const rankText = (n: number | null | undefined) => n == null ? "—" : `#${n}`;
const SORT_LABEL: Record<RatingsSort, string> = { overall: "Overall", offense: "Offense", defense: "Defense", sor: "SOR", sos_played: "SOS Played", sos_remaining: "SOS Remaining", sos_full: "SOS Full" };

type Props = { current: RatingHistoryPeriod; history: RatingHistoryPeriod[]; timeline: { id: string; label: string }[]; roster: RosterRow[]; season: number };

/** Shared period and URL-backed state for every Teams analysis view. */
export function TeamsHub({ current, history, timeline, roster, season }: Props) {
  const params = useSearchParams();
  const router = useRouter();
  const view = VIEWS.find((v) => v.value === params.get("view"))?.value ?? "rankings";
  const metric: RatingMetric = METRICS.find((m) => m.value === params.get("metric"))?.value ?? "overall";
  const measure = params.get("measure") === "rank" ? "rank" : "rating";
  const { sort, dir } = parseRatingsSort(params.get("sort") ?? undefined, params.get("dir") ?? undefined);
  const query = (params.get("q") ?? "").slice(0, 80);
  const confOptions = useMemo(() => conferenceOptions(roster), [roster]);
  const requestedConference = params.get("conf") ?? "all";
  const conference = ["all", "p4", ...confOptions].includes(requestedConference) ? requestedConference : "all";
  const group = params.get("group") === "resume" || (!params.has("group") && !["overall", "offense", "defense"].includes(sort)) ? "resume" : "strength";
  const resolveSelection = (value: string | null) => {
    const resolved = value && resolveTeam(value);
    return current.ratings.find((r) => r.team === (resolved ? resolved.ratingName : value))?.team ?? "";
  };
  const selected = resolveSelection(params.get("team"));
  const compared = resolveSelection(params.get("compare"));
  const team = selected || (view === "trends" && !params.has("team") ? current.ratings[0]?.team ?? "" : "");
  const compare = compared === team ? "" : compared;
  const unrecognized = ([["team", selected], ["compare", compared]] as const)
    .map(([key, found]) => ({ key, value: (params.get(key) ?? "").trim(), found }))
    .filter(({ value, found }) => value && !found)
    .map(({ value }) => value.slice(0, 60));
  const conferenceMap = useMemo(() => buildConferenceMap(roster), [roster]);
  const ranks = useMemo(() => ({ overall: nationalRanks(current.ratings, "overall"), offense: nationalRanks(current.ratings, "offense"), defense: nationalRanks(current.ratings, "defense") }), [current]);
  const sosRanks = useMemo(() => rankSosByTeam(current.ratings), [current]);
  const movement = useMemo(() => weeklyMovement(current, history), [current, history]);
  const eligible = current.ratings.filter((r) => matchesTeamConference(conference, r.team, conferenceMap) && r.team.toLowerCase().includes(query.trim().toLowerCase()));
  const sortValue = (r: AnalysisRating) => sort === "sor" ? r.sorRank ?? null : sort === "sos_played" ? sosRanks.get(r.team)?.played ?? null : sort === "sos_remaining" ? sosRanks.get(r.team)?.remaining ?? null : sort === "sos_full" ? sosRanks.get(r.team)?.full ?? null : r[ratingField[sort]];
  const visible = [...eligible].sort((a, b) => {
    const av = sortValue(a); const bv = sortValue(b);
    if (av === null || bv === null) return Number(av === null) - Number(bv === null);
    return (dir === "asc" ? av - bv : bv - av) || a.team.localeCompare(b.team);
  });
  const teams = [team, compare].filter(Boolean);
  const selectedRows = teams.map((name) => current.ratings.find((row) => row.team === name)!);

  function change(values: Record<string, string | null>, navigate = false) {
    const url = searchParamsUrl("/teams", (next) => {
      next.set("season", String(season));
      for (const [key, value] of Object.entries(values)) if (value === null || value === "") next.delete(key); else next.set(key, value);
    });
    if (navigate) router.push(url, { scroll: false });
    else window.history.replaceState(null, "", url);
  }
  function chooseSort(value: RatingsSort) {
    change({ sort: value, dir: sort === value ? dir === "asc" ? "desc" : "asc" : bestFirstDirection(value) });
  }
  function header(value: RatingsSort) {
    return <th key={value} scope="col" aria-sort={sort === value ? dir === "asc" ? "ascending" : "descending" : "none"} className={CELL}><button className="min-h-11 rounded font-semibold focus-visible:outline-2 focus-visible:outline-accent" onClick={() => chooseSort(value)} aria-label={`Sort by ${SORT_LABEL[value]}`}>{SORT_LABEL[value]}{sort === value && <span aria-hidden> {dir === "asc" ? "↑" : "↓"}</span>}</button></th>;
  }
  const periodControl = <label className="flex min-w-0 flex-col gap-1 text-xs font-semibold text-ink-muted">Rating period<select id="rating-period" value={current.period.id} onChange={(e) => change({ period: e.target.value }, true)} className={CONTROL}>{!timeline.some((p) => p.id === current.period.id) && <option value={current.period.id}>{current.period.label}</option>}{timeline.map((p) => <option key={p.id} value={p.id}>{p.label}</option>)}</select></label>;
  const teamControls = <div className="grid gap-3 sm:grid-cols-2">{["team", "compare"].map((key, index) => <label key={key} className="flex min-w-0 flex-col gap-1 text-sm font-semibold">{index === 0 ? "First team" : "Second team"}<select className={CONTROL} aria-label={index === 0 ? "First team" : "Second team"} value={index === 0 ? team : compare} onChange={(e) => change({ [key]: e.target.value || null, ...(e.target.value === (index === 0 ? compare : team) ? { [index === 0 ? "compare" : "team"]: null } : {}) })}><option value="">Choose a team</option>{[...current.ratings].sort((a, b) => a.team.localeCompare(b.team)).map((row) => <option key={row.team}>{row.team}</option>)}</select></label>)}</div>;
  const trendControls = <div className="flex flex-wrap gap-3"><SegmentedControl label="Rating component" value={metric} options={METRICS} onChange={(value) => change({ metric: value })} /><SegmentedControl label="Trend measure" value={measure} options={MEASURES} onChange={(value) => change({ measure: value })} /></div>;
  const filteredSelections = teams.filter((name) => !eligible.some((r) => r.team === name));

  return <div className="space-y-6">
    <div className="flex flex-col gap-4 border-b border-line pb-5 lg:flex-row lg:items-end lg:justify-between"><nav aria-label="Team analysis views" className="flex flex-wrap gap-1">{VIEWS.map((item) => <button key={item.value} type="button" aria-current={item.value === view ? "page" : undefined} onClick={() => change({ view: item.value }, true)} className={`min-h-11 rounded-lg px-3 py-2 text-sm font-semibold ${item.value === view ? "bg-ink text-surface-card" : "text-ink-muted hover:bg-surface-inset"}`}>{item.label}</button>)}</nav>{periodControl}</div>
    <p className="text-sm text-ink-muted">{current.period.label} · {current.ratings.length} teams · National ranks stay fixed when you filter.</p>
    <div className="flex flex-col gap-3 sm:flex-row sm:items-end"><SearchField id="rating-search" label="Search teams" value={query} onChange={(value) => change({ q: value || null })} placeholder="Search teams…" clearLabel="Clear search" className="min-w-0 flex-1" /><label className="flex min-w-0 flex-col gap-1 text-xs font-semibold text-ink-muted">Conference<select className={CONTROL} data-testid="conference-filter" aria-label="Filter by conference" value={conference} onChange={(e) => change({ conf: e.target.value })}><option value="all">All FBS</option><option value="p4">Power Four + Notre Dame</option>{confOptions.map((c) => <option key={c}>{c}</option>)}</select></label></div>
    {unrecognized.length > 0 && <Notice tone="warn">{unrecognized.map((value) => `“${value}”`).join(" and ")} {unrecognized.length === 1 ? "is not a team in this period’s ratings" : "are not teams in this period’s ratings"}, so {unrecognized.length === 1 ? "it was" : "they were"} ignored.</Notice>}
    {filteredSelections.length > 0 && <p role="status" className="text-sm text-ink-muted">Selected outside these filters: {filteredSelections.join(", ")}. Your comparison is preserved.</p>}
    {current.ratings.length === 0 ? <Notice tone="empty">No certified ratings are available for this period.</Notice> : <>
      {view === "rankings" && <>
        <div className="flex flex-wrap items-center justify-between gap-3"><SegmentedControl label="Ranking columns" value={group} options={[{ value: "strength", label: "Strength" }, { value: "resume", label: "Résumé & schedule" }]} onChange={(value) => change({ group: value, sort: value === "strength" ? "overall" : "sor", dir: value === "strength" ? "desc" : "asc" })} /><label className="text-sm text-ink-muted">Sort by <select id="rating-sort" className={CONTROL} value={sort} onChange={(e) => chooseSort(e.target.value as RatingsSort)}>{(group === "strength" ? ["overall", "offense", "defense"] : ["sor", "sos_played", "sos_remaining", "sos_full"]).map((value) => <option key={value} value={value}>{SORT_LABEL[value as RatingsSort]}</option>)}</select></label></div>
        {visible.length === 0 ? <Notice tone="empty"><p>No teams match these filters.</p><button className="min-h-11 text-accent-ink" onClick={() => change({ q: null, conf: null })}>Clear filters</button></Notice> : <>
          <div className="hidden overflow-x-auto rounded-xl border border-line sm:block"><table className="w-full text-sm"><caption className="sr-only">{season} {current.period.label} team {group === "strength" ? "strength" : "résumé and schedule"} rankings</caption><thead className="bg-surface-inset text-xs text-ink-muted"><tr><th className={CELL}>Rank</th><th className="px-3 py-3 text-left">Team</th>{group === "strength" ? <>{header("overall")}{header("offense")}{header("defense")}<th className={CELL}>Weekly change</th><th className={CELL}>Rank movement</th></> : <><th className={CELL}>FBS W-L</th>{header("sor")}<th className={CELL} title="Wins above an average FBS team on the same schedule">WAA</th>{header("sos_played")}{header("sos_remaining")}{header("sos_full")}</>}</tr></thead><tbody className="divide-y divide-line">{visible.map((row) => <tr key={row.team}><td className={CELL}>{group === "strength" ? ranks[(sort in ratingField ? sort : "overall") as RatingMetric].get(row.team) ?? "—" : rankText(sortValue(row))}</td><th scope="row" className="px-3 py-3 text-left"><Link href={teamHref(row.team)} className="inline-flex min-h-11 items-center gap-2 font-semibold hover:underline"><TeamLogo name={row.team} px={24} />{row.team}</Link></th>{group === "strength" ? <><td className={CELL}>{signed(row.overallRating)}</td><td className={CELL}>{signed(row.offenseRating)}</td><td className={CELL}>{signed(row.defenseRating)}</td><td className={CELL}>{signed(movement.get(row.team)?.change)}</td><td className={CELL}>{signed(movement.get(row.team)?.rankChange, 0)}</td></> : <><td className={CELL}>{record(row)}</td><td className={CELL} title={`SOR ${number(row.sor, 1)}`}>{rankText(row.sorRank)}</td><td className={CELL}>{signed(row.waa, 1)}</td>{(["played", "remaining", "full"] as const).map((key) => <td className={CELL} key={key}>{rankText(sosRanks.get(row.team)?.[key])}</td>)}</>}</tr>)}</tbody></table></div>
          <ul aria-label="Team ratings list" className="space-y-3 sm:hidden">{visible.map((row) => <li key={row.team} className="rounded-xl border border-line bg-surface-card p-4"><Link href={teamHref(row.team)} className="flex min-h-11 items-center gap-2 font-semibold"><span className="text-sm text-ink-muted">{rankText(group === "strength" ? ranks[(sort in ratingField ? sort : "overall") as RatingMetric].get(row.team) : sortValue(row))}</span><TeamLogo name={row.team} px={24} /><span className="min-w-0 break-words">{row.team}</span></Link><dl className="mt-3 grid grid-cols-3 gap-3 text-sm">{(group === "strength" ? [["Overall", signed(row.overallRating)], ["Offense", signed(row.offenseRating)], ["Defense", signed(row.defenseRating)], ["Weekly change", signed(movement.get(row.team)?.change)], ["Rank movement", signed(movement.get(row.team)?.rankChange, 0)]] : [["FBS W-L", record(row)], ["SOR", rankText(row.sorRank)], ["WAA", signed(row.waa, 1)], ["SOS played", rankText(sosRanks.get(row.team)?.played)], ["SOS remaining", rankText(sosRanks.get(row.team)?.remaining)], ["SOS full", rankText(sosRanks.get(row.team)?.full)]]).map(([label, value]) => <div key={label}><dt className="text-xs text-ink-muted">{label}</dt><dd className="mt-1 font-mono">{value}</dd></div>)}</dl></li>)}</ul>
        </>}
        <p className="max-w-3xl text-xs leading-relaxed text-ink-muted">Weekly change compares consecutive certified weeks; a dash means that comparison is unavailable. Positive rank movement means improvement. SOR ranks résumé (1 is strongest); SOS ranks difficulty (1 is hardest). WAA is wins above an average FBS team on the same schedule. FCS games are excluded from résumé measures.</p>
      </>}
      {(view === "trends" || view === "compare") && <>{teamControls}{view === "compare" && <ComparisonTable rows={selectedRows} ranks={ranks} sosRanks={sosRanks} />}{trendControls}<RatingTimeline history={history} teams={teams} metric={metric} measure={measure} /></>}
      {view === "resume" && <ResumeView rows={eligible} extent={current.ratings.map((r) => r.overallRating)} population={current.ratings.length} selected={selected} onSelect={(value) => change({ team: value })} compareHref={(name) => `/teams?${new URLSearchParams({ season: String(season), period: current.period.id, view: "compare", team: name })}`} />}
    </>}
    <details className="border-t border-line pt-4 text-sm text-ink-muted"><summary className="min-h-11 cursor-pointer font-semibold text-ink">How to read these ratings</summary><p className="mt-2 max-w-3xl leading-relaxed">Offense and defense are standardized possession-efficiency ratings; higher is better for both. Zero is the model’s historical reference level, not necessarily this week’s average. A rating difference is not a point spread. The forecast bridge converts ratings into game margins and totals.</p><p className="mt-2"><Link href="/model/method" className="inline-flex min-h-11 min-w-11 items-center text-accent-ink hover:underline">Read the methodology</Link></p></details>
  </div>;
}

function ComparisonTable({ rows, ranks, sosRanks }: { rows: AnalysisRating[]; ranks: Record<RatingMetric, Map<string, number>>; sosRanks: ReturnType<typeof rankSosByTeam> }) {
  if (!rows.length) return <Notice tone="empty">Choose up to two teams to compare the same certified period.</Notice>;
  const fields: { label: string; value: (row: AnalysisRating) => string }[] = [
    ...(["overall", "offense", "defense"] as const).map((metric) => ({ label: `${metric[0].toUpperCase()}${metric.slice(1)}`, value: (row: AnalysisRating) => `${signed(row[ratingField[metric]])} (${rankText(ranks[metric].get(row.team))})` })),
    { label: "FBS record", value: record }, { label: "Strength of record", value: (r) => rankText(r.sorRank) }, { label: "Wins above average", value: (r) => signed(r.waa, 1) },
    { label: "SOS played", value: (r) => rankText(sosRanks.get(r.team)?.played) }, { label: "SOS remaining", value: (r) => rankText(sosRanks.get(r.team)?.remaining) }, { label: "SOS full", value: (r) => rankText(sosRanks.get(r.team)?.full) },
  ];
  return <div className="overflow-x-auto rounded-xl border border-line"><table className="w-full text-sm"><caption className="sr-only">Team comparison for the selected certified period</caption><thead className="bg-surface-inset"><tr><th className="px-3 py-3 text-left">Measure</th>{rows.map((r) => <th key={r.team} className="px-3 py-3"><Link href={teamHref(r.team)} className="text-accent-ink hover:underline">{r.team}</Link></th>)}</tr></thead><tbody className="divide-y divide-line">{fields.map((field) => <tr key={field.label}><th className="px-3 py-3 text-left font-medium">{field.label}</th>{rows.map((r) => <td key={r.team} className="px-3 py-3 text-center tabular-nums">{field.value(r)}</td>)}</tr>)}</tbody></table><p className="px-3 py-3 text-xs text-ink-muted">A dash means this measure is unavailable for the selected period.</p></div>;
}

function ResumeView({ rows, extent, population, selected, onSelect, compareHref }: { rows: AnalysisRating[]; extent: number[]; population: number; selected: string; onSelect: (name: string) => void; compareHref: (name: string) => string }) {
  const points = rows.filter((r) => r.sorRank != null && Number.isFinite(r.sorRank));
  const selectedRow = points.find((r) => r.team === selected);
  // The horizontal scale spans every team in the period, so filtering never rescales the axis.
  const min = Math.min(-2, ...extent); const max = Math.max(2, ...extent);
  const x = (n: number) => 60 + (n - min) / (max - min) * 660;
  const y = (n: number) => 30 + (n - 1) / Math.max(1, population - 1) * 260;
  return <section aria-labelledby="resume-heading" className="space-y-4"><div><h2 id="resume-heading" className="text-xl font-semibold">Strength vs résumé</h2><p className="mt-1 text-sm text-ink-muted">Right: higher overall rating. Up: stronger strength-of-record rank. {points.length} of {rows.length} filtered teams have both measures.</p></div>{points.length ? <svg viewBox="0 0 760 345" role="group" aria-label="Strength versus résumé scatterplot" className="w-full rounded-xl border border-line bg-surface-card"><line x1="60" x2="720" y1="290" y2="290" stroke="var(--line-strong)" /><line x1="60" x2="60" y1="30" y2="290" stroke="var(--line-strong)" /><text x="390" y="330" textAnchor="middle" fill="var(--ink-muted)" fontSize="13">Overall rating →</text><text x="16" y="160" textAnchor="middle" transform="rotate(-90 16 160)" fill="var(--ink-muted)" fontSize="13">Stronger résumé ↑</text><text x="48" y="35" textAnchor="end" fill="var(--ink-muted)" fontSize="12">#1</text><text x="48" y="290" textAnchor="end" fill="var(--ink-muted)" fontSize="12">#{population}</text>{[min, 0, max].map((n) => <text key={n} x={x(n)} y="310" textAnchor="middle" fill="var(--ink-muted)" fontSize="12">{n.toFixed(1)}</text>)}{points.map((r) => <g key={r.team} role="button" tabIndex={0} aria-label={`${r.team}: overall ${number(r.overallRating)}, SOR rank ${r.sorRank}`} onClick={() => onSelect(r.team)} onKeyDown={(event) => { if (event.key === "Enter" || event.key === " ") { event.preventDefault(); onSelect(r.team); } }} className="cursor-pointer outline-offset-4"><circle cx={x(r.overallRating)} cy={y(r.sorRank!)} r={r.team === selected ? 9 : 6} fill={r.team === selected ? "var(--accent)" : "var(--ink-muted)"} opacity={selected && r.team !== selected ? 0.35 : 0.85} /><title>{r.team}</title></g>)}</svg> : <Notice tone="empty">Strength-of-record comparisons are not available for these teams in this period.</Notice>}
    {selectedRow && <div className="rounded-xl border border-line bg-surface-inset p-4" role="status"><h3 className="font-semibold">{selectedRow.team}</h3><p className="mt-1 text-sm">Overall {signed(selectedRow.overallRating)} · SOR {rankText(selectedRow.sorRank)} · score {number(selectedRow.sor, 1)} · FBS {record(selectedRow)} · {selectedRow.completedGames ?? "—"} completed FBS games</p><div className="mt-2 flex gap-4 text-sm"><Link href={teamHref(selectedRow.team)} className="min-h-11 content-center text-accent-ink">Team profile</Link><Link href={compareHref(selectedRow.team)} className="min-h-11 content-center text-accent-ink">Compare</Link></div></div>}
    <details className="rounded-xl border border-line p-4"><summary className="min-h-11 cursor-pointer font-semibold">Show as table</summary><div className="overflow-x-auto"><table className="w-full text-sm"><thead><tr><th className="px-3 py-3 text-left">Team</th><th className={CELL}>Overall</th><th className={CELL}>SOR rank</th><th className={CELL}>SOR score</th><th className={CELL}>FBS W-L</th><th className={CELL}>FBS games</th></tr></thead><tbody>{[...points].sort((a, b) => a.sorRank! - b.sorRank!).map((r) => <tr key={r.team} className="border-t border-line"><th className="px-3 py-3 text-left"><Link href={teamHref(r.team)} className="text-accent-ink">{r.team}</Link></th><td className={CELL}>{signed(r.overallRating)}</td><td className={CELL}>{rankText(r.sorRank)}</td><td className={CELL}>{number(r.sor, 1)}</td><td className={CELL}>{record(r)}</td><td className={CELL}>{r.completedGames ?? "—"}</td></tr>)}</tbody></table></div></details>
  </section>;
}
