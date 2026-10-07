export type SectionResult<T> =
  | { status: "ok"; value: T }
  | { status: "unavailable" };

/**
 * Load the replay and prospective Performance sections independently.
 *
 * The prospective loader fails closed (it throws on an unknown receipt or
 * incomplete coverage), and that must hide only its own section, not the
 * replay record beside it.
 */
export async function loadPerformanceSections<R, P>(
  loadReplay: () => Promise<R>,
  loadProspective: () => Promise<P>,
  onError: (section: "replay" | "prospective", error: unknown) => void = () => {},
): Promise<{ replay: SectionResult<R>; prospective: SectionResult<P> }> {
  const settle = async <T>(
    section: "replay" | "prospective",
    load: () => Promise<T>,
  ): Promise<SectionResult<T>> => {
    try {
      return { status: "ok", value: await load() };
    } catch (error) {
      onError(section, error);
      return { status: "unavailable" };
    }
  };
  const [replay, prospective] = await Promise.all([
    settle("replay", loadReplay),
    settle("prospective", loadProspective),
  ]);
  return { replay, prospective };
}
