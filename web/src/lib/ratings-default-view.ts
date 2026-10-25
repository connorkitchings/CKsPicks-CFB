/** True when the ratings controls are at the page's defaults (nothing to flag as filtered). */
export function isDefaultView({ conference, sort, period, defaultPeriod }: {
  conference: string;
  sort: string;
  period: string;
  defaultPeriod: string;
}): boolean {
  return conference === "all" && sort === "overall" && period === defaultPeriod;
}
