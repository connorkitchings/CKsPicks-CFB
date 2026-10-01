const ET = "America/New_York";

/** Deterministic Eastern-time formatting so server and client render the same text. */
export function kickoffTime(d: Date): string {
  return d.toLocaleTimeString("en-US", {
    hour: "numeric",
    minute: "2-digit",
    timeZone: ET,
  });
}

export function dayLabel(d: Date): string {
  return d.toLocaleDateString("en-US", {
    weekday: "long",
    month: "short",
    day: "numeric",
    timeZone: ET,
  });
}

export function stamp(d: Date): string {
  return `${d.toLocaleString("en-US", {
    month: "short",
    day: "numeric",
    hour: "numeric",
    minute: "2-digit",
    timeZone: ET,
  })} ET`;
}

/** "Sat, Oct 3" in Eastern time. */
export function dayShort(d: Date): string {
  return d.toLocaleDateString("en-US", {
    weekday: "short",
    month: "short",
    day: "numeric",
    timeZone: ET,
  });
}
