/**
 * Builds a URL from the live `window.location.search`, never from a render-time snapshot, so two
 * quick updates in a row both survive. Client-only: call it from event handlers.
 */
export function searchParamsUrl(pathname: string, edit: (params: URLSearchParams) => void): string {
  const next = new URLSearchParams(window.location.search);
  edit(next);
  const query = next.toString();
  return query ? `${pathname}?${query}` : pathname;
}

/** Applies `edit` to the live query string in place, without navigating. */
export function replaceSearchParams(pathname: string, edit: (params: URLSearchParams) => void): void {
  window.history.replaceState(null, "", searchParamsUrl(pathname, edit));
}
