export type SectionResult<T> =
  | { status: "ok"; value: T }
  | { status: "unavailable" };

/** Load the selected cumulative record, hiding it if its query fails. */
export async function loadPerformanceRecord<T>(
  load: () => Promise<T>,
  onError: (error: unknown) => void = () => {},
): Promise<SectionResult<T>> {
  try {
    return { status: "ok", value: await load() };
  } catch (error) {
    onError(error);
    return { status: "unavailable" };
  }
}
