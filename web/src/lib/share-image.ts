/**
 * Pure rules for the prepared share image kept between the render step and the second tap
 * (browsers that only share inside a fresh user gesture).
 */

/** Everything that determines the pixels and the name of a prepared image. */
export type ShareImageIdentity = {
  /** Caller-supplied fingerprint of the card content (filters, highlighted team, metric, week, side...). */
  contentKey: string;
  filename: string;
  title: string;
  width: number;
  height: number;
  /** Explicit background, or "" when the card's computed background is used. */
  background: string;
  theme: "light" | "dark";
};

export type PreparedShareImage<F> = { identity: ShareImageIdentity; file: F };

export function sameShareImageIdentity(a: ShareImageIdentity, b: ShareImageIdentity): boolean {
  return (
    a.contentKey === b.contentKey &&
    a.filename === b.filename &&
    a.title === b.title &&
    a.width === b.width &&
    a.height === b.height &&
    a.background === b.background &&
    a.theme === b.theme
  );
}

/** The prepared file when it still matches the current inputs, otherwise null (it must be re-rendered). */
export function reusablePreparedImage<F>(prepared: PreparedShareImage<F> | null, current: ShareImageIdentity): F | null {
  return prepared && sameShareImageIdentity(prepared.identity, current) ? prepared.file : null;
}

/** The user dismissed the share sheet: not a failure, nothing to fall back to. */
export function isShareCancellation(error: unknown): boolean {
  return typeof error === "object" && error !== null && (error as { name?: unknown }).name === "AbortError";
}
